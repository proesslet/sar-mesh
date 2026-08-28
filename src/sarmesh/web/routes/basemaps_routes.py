"""Basemap packs: what is available, which is serving, and the tiles themselves.

No shared prefix on the router: these routes span /api/basemap, /api/basemaps
and /tiles
"""

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from sarmesh.services.basemaps import (
    MAX_TILES,
    check_bulk_allowed,
    count_tiles,
    deepest_zoom_within,
    validate_template,
)
from sarmesh.storage.database import Database
from sarmesh.web.dependencies import Basemaps, Db, Downloader, OptionalBasemaps
from sarmesh.web.schemas import (
    BasemapArea,
    BasemapDownload,
    BasemapSelect,
    OnlineSource,
)
from sarmesh.web.tiles import (
    BASEMAP_SETTING,
    PARTIAL_SUFFIX,
    BasemapLibrary,
    BasemapPack,
    read_metadata,
)

logger = logging.getLogger(__name__)

ONLINE_URL_SETTING = "online_tile_url"
ONLINE_ENABLED_SETTING = "online_tile_enabled"
DEFAULT_ONLINE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
DEFAULT_ONLINE_ATTRIBUTION = "© OpenStreetMap contributors"

router = APIRouter(tags=["basemaps"])


########################## The active pack ##########################


@router.get("/api/basemap")
def basemap(basemaps: OptionalBasemaps) -> dict[str, Any]:
    store = basemaps.store if basemaps is not None else None

    if basemaps is None or store is None:
        return {"available": False, "revision": 0}

    meta = store.metadata()

    return {
        "available": True,
        "name": meta.get("name"),
        "minzoom": _as_int(meta.get("minzoom")),
        "maxzoom": _as_int(meta.get("maxzoom")),
        "bounds": meta.get("bounds"),
        "format": meta.get("format", "png"),
        # Changes on every swap so the client can bust Leaflet's tile cache;
        # the tile URLs themselves are identical between packs.
        "revision": basemaps.revision,
    }


@router.get("/tiles/{z}/{x}/{y}")
def tile(z: int, x: int, y: str, basemaps: OptionalBasemaps) -> Response:
    tile_store = basemaps.store if basemaps is not None else None

    if tile_store is None:
        raise HTTPException(404, "No basemap configured")

    # Leaflet requests "{y}.png", so y arrives as a string and is parsed here;
    # typing it as int would make FastAPI reject the request with a 422 before
    # this handler ever runs.
    try:
        row = int(y.split(".")[0])
    except ValueError as error:
        raise HTTPException(404, "Malformed tile coordinate") from error

    data = tile_store.get_tile(z, x, row)

    if data is None:
        raise HTTPException(404, "Tile not found")

    return Response(data, media_type="image/png")


########################## The library ##########################


@router.get("/api/basemaps")
def list_basemaps(database: Db, basemaps: OptionalBasemaps) -> dict[str, Any]:
    return _library_json(database, basemaps)


@router.post("/api/basemaps/online")
def set_online_source(
    body: OnlineSource, database: Db, basemaps: OptionalBasemaps
) -> dict[str, Any]:
    try:
        validate_template(body.url_template)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error

    # Stored only when it differs from the default, so an operator who never
    # touches it keeps following the default if that ever changes.
    database.settings.set(
        ONLINE_URL_SETTING,
        None if body.url_template == DEFAULT_ONLINE_URL else body.url_template,
    )
    database.settings.set(ONLINE_ENABLED_SETTING, "1" if body.enabled else "0")

    return _library_json(database, basemaps)


@router.post("/api/basemaps/select")
def select_basemap(
    body: BasemapSelect, database: Db, basemaps: Basemaps
) -> dict[str, Any]:
    try:
        basemaps.select(body.name)
    except KeyError as error:
        raise HTTPException(404, f"No basemap pack named {body.name}") from error

    database.settings.set(BASEMAP_SETTING, body.name)
    logger.info("Basemap set to %s", body.name or "none")

    return _library_json(database, basemaps)


@router.put("/api/basemaps/{name}")
async def upload_basemap(
    name: str, request: Request, database: Db, basemaps: Basemaps
) -> dict[str, Any]:
    """Import an MBTiles pack by streaming its bytes into the library.

    The raw body is used rather than a multipart form so the file never has to
    be buffered
    """
    try:
        destination = basemaps.import_path(name)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error

    if destination.exists():
        raise HTTPException(409, f"A pack named {name} is already imported")

    # Written under a temporary name so an aborted upload cannot leave a
    # truncated file that looks like a usable pack.
    partial = destination.with_name(destination.name + PARTIAL_SUFFIX)

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)

        with partial.open("wb") as handle:
            async for chunk in request.stream():
                handle.write(chunk)
    except OSError as error:
        _discard(partial)
        raise HTTPException(500, f"Could not write the pack: {error}") from error
    except Exception:
        _discard(partial)
        raise

    # Validated only once the bytes are on disk: an MBTiles file is a SQLite
    # database, so there is nothing meaningful to check until it is complete
    # and openable.
    if read_metadata(partial) is None:
        _discard(partial)
        raise HTTPException(400, f"{name} is not a readable MBTiles pack")

    partial.replace(destination)
    logger.info("Imported basemap pack %s", destination)

    return _library_json(database, basemaps)


########################## Downloading ##########################


@router.post("/api/basemaps/estimate")
def estimate_download(body: BasemapArea) -> dict[str, Any]:
    """How many tiles an area comes to, before committing to fetching them.

    Zoom level is exponential and the difference between a sensible request and
    an impossible one is two clicks, so the operator gets the number first.
    """
    area = body.bounds()
    tiles = count_tiles(area, body.min_zoom, body.max_zoom)
    within = tiles <= MAX_TILES

    return {
        "tiles": tiles,
        "limit": MAX_TILES,
        "within_limit": within,
        # Only worth computing when the answer is "no": it tells the operator
        # what would work instead of leaving them to bisect.
        "suggested_max_zoom": None
        if within
        else deepest_zoom_within(area, body.min_zoom, MAX_TILES),
    }


@router.post("/api/basemaps/download", status_code=202)
def start_download(
    body: BasemapDownload, basemaps: Basemaps, downloads: Downloader
) -> dict[str, Any]:
    name = body.name if body.name.endswith(".mbtiles") else f"{body.name}.mbtiles"

    try:
        destination = basemaps.import_path(name)
        validate_template(body.url_template)
        check_bulk_allowed(body.url_template)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error

    if destination.exists():
        raise HTTPException(409, f"A pack named {name} already exists")

    try:
        progress = downloads.start(
            destination=destination,
            name=name,
            template=body.url_template,
            bounds=body.bounds(),
            min_zoom=body.min_zoom,
            max_zoom=body.max_zoom,
        )
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(409, str(error)) from error

    logger.info("Downloading basemap %s (%d tiles)", name, progress.total)

    return asdict(progress)


@router.get("/api/basemaps/download")
def download_status(downloads: Downloader) -> dict[str, Any] | None:
    progress = downloads.progress

    return asdict(progress) if progress is not None else None


@router.post("/api/basemaps/download/cancel")
def cancel_download(downloads: Downloader) -> dict[str, Any] | None:
    downloads.cancel()
    progress = downloads.progress

    return asdict(progress) if progress is not None else None


########################## Payload helpers ##########################


def _library_json(
    database: Database, basemaps: BasemapLibrary | None
) -> dict[str, Any]:
    """The whole library, which is what every mutating route returns.

    Returned rather than a bare acknowledgement so the caller cannot show a
    list that disagrees with what is actually serving.
    """
    if basemaps is None:
        return {
            "directory": None,
            "active": None,
            "revision": 0,
            "packs": [],
            "online": _online_json(database),
        }

    active = basemaps.active_name

    return {
        "directory": str(basemaps.directory),
        "active": active,
        "revision": basemaps.revision,
        "packs": [_pack_json(p, active) for p in basemaps.packs()],
        "online": _online_json(database),
    }


def _online_json(database: Database) -> dict[str, Any]:
    stored = database.settings.get(ONLINE_URL_SETTING)
    enabled = database.settings.get(ONLINE_ENABLED_SETTING)
    url = stored or DEFAULT_ONLINE_URL

    try:
        check_bulk_allowed(url)
        bulk_allowed = True
    except ValueError:
        bulk_allowed = False

    return {
        "url_template": url,
        "bulk_allowed": bulk_allowed,
        "enabled": enabled != "0",
        "attribution": DEFAULT_ONLINE_ATTRIBUTION if not stored else None,
    }


def _pack_json(pack: BasemapPack, active: str | None) -> dict[str, Any]:
    meta = pack.metadata or {}

    return {
        "name": pack.name,
        "path": str(pack.path),
        "size_bytes": pack.size_bytes,
        "active": pack.name == active,
        # False for a file that is not an openable MBTiles pack. It stays in
        # the list so a bad import is visible rather than mysteriously absent.
        "readable": pack.metadata is not None,
        "title": meta.get("name"),
        "minzoom": _as_int(meta.get("minzoom")),
        "maxzoom": _as_int(meta.get("maxzoom")),
        "bounds": meta.get("bounds"),
    }


def _as_int(value: str | None) -> int | None:
    """MBTiles metadata values are text, and a hand-built pack may hold junk."""
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def _discard(path: Path) -> None:
    """Remove a partial upload, without masking the error that caused it."""
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        logger.warning("Could not remove the partial upload %s: %s", path, error)

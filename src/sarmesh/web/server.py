import asyncio
import json
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sarmesh.core.events import PositionBroadcaster
from sarmesh.services.basemaps import (
    MAX_TILES,
    BasemapDownloader,
    Bounds,
    check_bulk_allowed,
    count_tiles,
    deepest_zoom_within,
    validate_template,
)
from sarmesh.storage.database import Database
from sarmesh.storage.paths import is_frozen, log_path, user_data_dir
from sarmesh.web.tiles import (
    PARTIAL_SUFFIX,
    BasemapLibrary,
    BasemapPack,
    read_metadata,
)

STATIC_DIR = Path(__file__).parent / "static"

# Sent when a client first connects and every 15s thereafter, so an idle mesh
# is distinguishable from a dead connection and proxies do not time the stream
# out during quiet periods.
HEARTBEAT_SECONDS = 15.0

# The database key the chosen basemap is remembered under, so a pack picked in
# settings is still serving after a restart.
BASEMAP_SETTING = "basemap"

# The online map shown behind the offline packs, so an operator can see where
# they are while choosing an area to download.
ONLINE_URL_SETTING = "online_tile_url"
ONLINE_ENABLED_SETTING = "online_tile_enabled"

# Standard OpenStreetMap. Fine to view -- that is ordinary map browsing -- but
# bulk downloading from it is refused; see NO_BULK_DOWNLOAD_HOSTS.
DEFAULT_ONLINE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
DEFAULT_ONLINE_ATTRIBUTION = "© OpenStreetMap contributors"

# Uploads are streamed to disk in chunks rather than buffered: a pack is
# routinely gigabytes, and holding one in memory on a Pi would fail outright.
UPLOAD_CHUNK_BYTES = 1024 * 1024

# The log is read for display, so the tail is capped at something a browser can
# render. The full file is on disk for anyone who needs more.
MAX_LOG_LINES = 2000
DEFAULT_LOG_LINES = 200

logger = logging.getLogger(__name__)


class TeamCreate(BaseModel):
    name: str = Field(min_length=1)
    personnel_count: int = Field(default=1, ge=0)


class TrackerCreate(BaseModel):
    node_id: str = Field(min_length=1)
    label: str = Field(min_length=1)


class IncidentCreate(BaseModel):
    name: str = Field(min_length=1)


class IncidentUpdate(BaseModel):
    name: str = Field(min_length=1)


class BasemapSelect(BaseModel):
    # None turns the basemap off, which is a legitimate choice: positions still
    # plot without one, and a wrong pack is worse than no pack.
    name: str | None = None


class OnlineSource(BaseModel):
    url_template: str = Field(min_length=1)
    enabled: bool


class BasemapArea(BaseModel):
    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)
    min_zoom: int = Field(ge=0, le=22)
    max_zoom: int = Field(ge=0, le=22)

    def bounds(self) -> Bounds:
        return Bounds(
            west=self.west, south=self.south, east=self.east, north=self.north
        ).normalised()


class BasemapDownload(BasemapArea):
    name: str = Field(min_length=1)
    # The tile server to fetch from. Supplied by the operator because no source
    # can be assumed to permit bulk downloading on a search team's behalf.
    url_template: str = Field(min_length=1)


class AssignmentCreate(BaseModel):
    incident_id: str = Field(min_length=1)
    tracker_node_id: str = Field(min_length=1)
    team_id: str = Field(min_length=1)


def create_app(
    database: Database,
    broadcaster: PositionBroadcaster,
    basemaps: BasemapLibrary | None = None,
    downloader: BasemapDownloader | None = None,
) -> FastAPI:
    downloads = downloader if downloader is not None else BasemapDownloader()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        # The broadcaster needs the serving loop to hand positions over from
        # the radio thread, and it only exists once the server is running.
        broadcaster.bind_loop(asyncio.get_running_loop())
        yield

    app = FastAPI(title="SARMesh", lifespan=lifespan)

    ########################## Incidents ##########################

    @app.get("/api/incidents")
    def list_incidents() -> list[dict[str, Any]]:
        return [_incident_json(i) for i in database.get_all_incidents()]

    @app.get("/api/incidents/active")
    def active_incident() -> dict[str, Any] | None:
        incident = database.get_active_incident()
        return _incident_json(incident) if incident else None

    @app.post("/api/incidents", status_code=201)
    def create_incident(body: IncidentCreate) -> dict[str, Any]:
        return _incident_json(database.create_incident(name=body.name))

    @app.patch("/api/incidents/{incident_id}")
    def update_incident(incident_id: str, body: IncidentUpdate) -> dict[str, Any]:
        if database.get_incident(incident_id) is None:
            raise HTTPException(404, f"No incident {incident_id}")

        updated = database.update_incident(incident_id, name=body.name)

        if updated is None:
            raise HTTPException(404, f"No incident {incident_id}")

        return _incident_json(updated)

    @app.post("/api/incidents/{incident_id}/end")
    def end_incident(incident_id: str) -> dict[str, Any]:
        incident = database.get_incident(incident_id)

        if incident is None:
            raise HTTPException(404, f"No incident {incident_id}")

        # Ending twice would move the end time of an incident that is already
        # closed, rewriting a record the operator relies on.
        if incident.ended_at is not None:
            raise HTTPException(409, f"Incident {incident.name} has already ended")

        database.end_incident(incident_id, ended_at=datetime.now(UTC))
        ended = database.get_incident(incident_id)

        if ended is None:
            raise HTTPException(404, f"No incident {incident_id}")

        return _incident_json(ended)

    ########################## Teams ##########################

    def _team_json(team: Any, counts: dict[str, int]) -> dict[str, Any]:
        # The count is what explains why a team cannot be deleted, so it is
        # carried alongside the team rather than looked up separately.
        return {**asdict(team), "tracker_count": counts.get(team.id, 0)}

    def _assignment_counts() -> dict[str, int]:
        counts: dict[str, int] = {}

        for assignment in database.get_active_assignments():
            counts[assignment.team_id] = counts.get(assignment.team_id, 0) + 1

        return counts

    @app.get("/api/teams")
    def list_teams() -> list[dict[str, Any]]:
        counts = _assignment_counts()
        return [_team_json(t, counts) for t in database.get_all_teams()]

    @app.delete("/api/teams/{team_id}")
    def delete_team(team_id: str) -> list[dict[str, Any]]:
        """Remove a team, unless it is currently holding trackers."""
        team = database.get_team(team_id)

        if team is None:
            raise HTTPException(404, f"No team {team_id}")

        held = [
            a.tracker_node_id
            for a in database.get_active_assignments()
            if a.team_id == team_id
        ]

        if held:
            raise HTTPException(
                409,
                f"{team.name} still has {len(held)} tracker(s) assigned. "
                "Unassign them first, or their positions stop being attributed "
                "to anyone.",
            )

        database.delete_team(team_id)
        logger.info("Deleted team %s (%s)", team.name, team_id)

        counts = _assignment_counts()
        return [_team_json(t, counts) for t in database.get_all_teams()]

    @app.post("/api/teams", status_code=201)
    def create_team(body: TeamCreate) -> dict[str, Any]:
        team = database.create_team(
            name=body.name,
            personnel_count=body.personnel_count,
        )
        return asdict(team)

    ########################## Trackers ##########################

    def _tracker_json(tracker: Any) -> dict[str, Any]:
        assignment = database.get_active_assignment(tracker.node_id)
        payload: dict[str, Any] = {**asdict(tracker), "assignment": None}

        if assignment is None:
            return payload

        team = database.get_team(assignment.team_id)
        incident = database.get_incident(assignment.incident_id)

        # Named rather than left as ids: this is what stops a tracker being
        # deleted, so the operator has to be told which team is holding it.
        payload["assignment"] = {
            "incident_id": assignment.incident_id,
            "incident_name": incident.name if incident else None,
            "team_id": assignment.team_id,
            "team_name": team.name if team else None,
        }
        return payload

    @app.get("/api/trackers")
    def list_trackers() -> list[dict[str, Any]]:
        return [_tracker_json(t) for t in database.get_all_trackers()]

    @app.get("/api/trackers/unregistered")
    def unregistered_nodes() -> list[dict[str, Any]]:
        """Nodes heard on the mesh that have no tracker record yet.

        Positions are stored for every node that beacons, but only registered
        trackers appear anywhere in the UI. Without this an operator has to
        know a node's hex id by heart to add it, which is not something anyone
        does in the field.
        """
        known = {t.node_id for t in database.get_all_trackers()}

        return [
            {
                "node_id": position.node_id,
                "node_num": position.node_num,
                "last_seen_at": position.received_at.isoformat(),
            }
            for position in database.list_latest_positions()
            if position.node_id not in known
        ]

    @app.post("/api/trackers", status_code=201)
    def create_tracker(body: TrackerCreate) -> dict[str, Any]:
        if database.get_tracker(body.node_id) is not None:
            raise HTTPException(409, f"Tracker {body.node_id} already exists")

        tracker = database.create_tracker(node_id=body.node_id, label=body.label)
        return asdict(tracker)

    @app.delete("/api/trackers/{node_id}")
    def delete_tracker(node_id: str) -> list[dict[str, Any]]:
        """Remove a tracker, unless a team is currently carrying it.

        Returns the remaining trackers rather than an empty 204, so the caller
        cannot show a list that disagrees with the database.
        """
        if database.get_tracker(node_id) is None:
            raise HTTPException(404, f"No tracker {node_id}")

        assignment = database.get_active_assignment(node_id)

        if assignment is not None:
            team = database.get_team(assignment.team_id)
            held_by = team.name if team else assignment.team_id
            raise HTTPException(
                409,
                f"{node_id} is assigned to {held_by}. Unassign it before "
                "deleting, or the team's positions stop being attributed to "
                "anyone.",
            )

        # Recorded positions are deliberately left in place: they belong to the
        # incident that was being run, not to the tracker record, and an
        # after-action review still needs them.
        database.delete_tracker(node_id)
        logger.info("Deleted tracker %s", node_id)

        return [_tracker_json(t) for t in database.get_all_trackers()]

    @app.post("/api/assignments", status_code=201)
    def create_assignment(body: AssignmentCreate) -> dict[str, Any]:
        # Checked rather than trusted: nothing in the schema stops a stale
        # dropdown naming a team that has since been deleted, and an assignment
        # pointing at a row that does not exist is invisible until an operator
        # wonders why a tracker never shows up.
        if database.get_incident(body.incident_id) is None:
            raise HTTPException(404, f"No incident {body.incident_id}")

        if database.get_tracker(body.tracker_node_id) is None:
            raise HTTPException(404, f"No tracker {body.tracker_node_id}")

        team = database.get_team(body.team_id)

        if team is None:
            raise HTTPException(404, f"No team {body.team_id}")

        existing = database.get_active_assignment(body.tracker_node_id)

        if existing is not None:
            # Assigning over the top would leave the old assignment open and
            # unreachable, the same way a second active incident would. Moving
            # a tracker between teams is an unassign followed by an assign.
            held_by = database.get_team(existing.team_id)
            raise HTTPException(
                409,
                f"{body.tracker_node_id} is already assigned to "
                f"{held_by.name if held_by else existing.team_id}. "
                "Unassign it first.",
            )

        assignment = database.assign_tracker(
            incident_id=body.incident_id,
            tracker_node_id=body.tracker_node_id,
            team_id=body.team_id,
        )
        logger.info("Assigned %s to %s", body.tracker_node_id, team.name)

        payload = asdict(assignment)
        payload["assigned_at"] = assignment.assigned_at.isoformat()
        payload["unassigned_at"] = None
        return payload

    @app.delete("/api/assignments/{node_id}")
    def delete_assignment(node_id: str) -> list[dict[str, Any]]:
        """Release a tracker from whatever team is holding it.

        Returns the trackers, since their assignment state is what the caller
        is showing.
        """
        if database.get_active_assignment(node_id) is None:
            raise HTTPException(404, f"{node_id} is not assigned to anything")

        database.unassign_tracker(node_id, unassigned_at=datetime.now(UTC))
        logger.info("Unassigned %s", node_id)

        return [_tracker_json(t) for t in database.get_all_trackers()]

    ########################## Live status ##########################

    @app.get("/api/status")
    def status(incident_id: str | None = None) -> list[dict[str, Any]]:
        if incident_id is None:
            incident = database.get_active_incident()
            if incident is None:
                return []
            incident_id = incident.id

        return [
            _status_json(s)
            for s in database.list_incident_tracker_statuses(incident_id)
        ]

    @app.get("/events")
    async def events() -> StreamingResponse:
        queue = broadcaster.subscribe()

        async def stream() -> AsyncGenerator[str, None]:
            try:
                yield ": connected\n\n"
                while True:
                    try:
                        payload = await asyncio.wait_for(
                            queue.get(), timeout=HEARTBEAT_SECONDS
                        )
                    except TimeoutError:
                        yield ": heartbeat\n\n"
                        continue

                    yield f"event: position\ndata: {json.dumps(payload)}\n\n"
            finally:
                broadcaster.unsubscribe(queue)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    ########################## Basemap ##########################

    @app.get("/api/basemap")
    def basemap() -> dict[str, Any]:
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
            # Changes on every swap so the client can bust Leaflet's tile
            # cache; the tile URLs themselves are identical between packs.
            "revision": basemaps.revision,
        }

    def _online_json() -> dict[str, Any]:
        stored = database.get_setting(ONLINE_URL_SETTING)
        enabled = database.get_setting(ONLINE_ENABLED_SETTING)
        url = stored or DEFAULT_ONLINE_URL

        try:
            check_bulk_allowed(url)
            bulk_allowed = True
        except ValueError:
            # Viewable but not downloadable. Reported so the download form can
            # decline to offer this URL rather than pre-filling one that is
            # rejected the moment the operator presses Download.
            bulk_allowed = False

        return {
            "url_template": url,
            "bulk_allowed": bulk_allowed,
            # On by default: a new install has no packs, and an operator staring
            # at an empty grey rectangle cannot tell a working map from a
            # broken one, let alone choose an area to download.
            "enabled": enabled != "0",
            "attribution": DEFAULT_ONLINE_ATTRIBUTION if not stored else None,
        }

    # The library payload is what the map reads its online source from, so the
    # helper above has to exist before any route returns it.

    @app.get("/api/basemaps")
    def list_basemaps() -> dict[str, Any]:
        if basemaps is None:
            return {
                "directory": None,
                "active": None,
                "revision": 0,
                "packs": [],
                "online": _online_json(),
            }

        active = basemaps.active_name
        return {
            "directory": str(basemaps.directory),
            "active": active,
            "revision": basemaps.revision,
            "packs": [_pack_json(p, active) for p in basemaps.packs()],
            "online": _online_json(),
        }

    @app.post("/api/basemaps/online")
    def set_online_source(body: OnlineSource) -> dict[str, Any]:
        try:
            validate_template(body.url_template)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error

        # Stored only when it differs from the default, so an operator who
        # never touches it keeps following the default if that ever changes.
        database.set_setting(
            ONLINE_URL_SETTING,
            None if body.url_template == DEFAULT_ONLINE_URL else body.url_template,
        )
        database.set_setting(ONLINE_ENABLED_SETTING, "1" if body.enabled else "0")

        return list_basemaps()

    @app.post("/api/basemaps/select")
    def select_basemap(body: BasemapSelect) -> dict[str, Any]:
        if basemaps is None:
            raise HTTPException(404, "No basemap library configured")

        try:
            basemaps.select(body.name)
        except KeyError as error:
            raise HTTPException(404, f"No basemap pack named {body.name}") from error

        database.set_setting(BASEMAP_SETTING, body.name)
        logger.info("Basemap set to %s", body.name or "none")

        return list_basemaps()

    @app.put("/api/basemaps/{name}")
    async def upload_basemap(name: str, request: Request) -> dict[str, Any]:
        """Import an MBTiles pack by streaming its bytes into the library.

        The raw body is used rather than a multipart form so the file never has
        to be buffered -- packs are large enough that the difference decides
        whether an import succeeds on a Pi.
        """
        if basemaps is None:
            raise HTTPException(404, "No basemap library configured")

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

        # Validated only once the bytes are on disk: an MBTiles file is a
        # SQLite database, so there is nothing meaningful to check until it is
        # complete and openable.
        if read_metadata(partial) is None:
            _discard(partial)
            raise HTTPException(400, f"{name} is not a readable MBTiles pack")

        partial.replace(destination)
        logger.info("Imported basemap pack %s", destination)

        return list_basemaps()

    @app.post("/api/basemaps/estimate")
    def estimate_download(body: BasemapArea) -> dict[str, Any]:
        """How many tiles an area comes to, before committing to fetching them.

        Zoom level is exponential and the difference between a sensible request
        and an impossible one is two clicks, so the operator gets the number
        first.
        """
        area = body.bounds()
        tiles = count_tiles(area, body.min_zoom, body.max_zoom)
        within = tiles <= MAX_TILES

        return {
            "tiles": tiles,
            "limit": MAX_TILES,
            "within_limit": within,
            # Only worth computing when the answer is "no": it tells the
            # operator what would work instead of leaving them to bisect.
            "suggested_max_zoom": None
            if within
            else deepest_zoom_within(area, body.min_zoom, MAX_TILES),
        }

    @app.post("/api/basemaps/download", status_code=202)
    def start_download(body: BasemapDownload) -> dict[str, Any]:
        if basemaps is None:
            raise HTTPException(404, "No basemap library configured")

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

    @app.get("/api/basemaps/download")
    def download_status() -> dict[str, Any] | None:
        progress = downloads.progress
        return asdict(progress) if progress is not None else None

    @app.post("/api/basemaps/download/cancel")
    def cancel_download() -> dict[str, Any] | None:
        downloads.cancel()
        progress = downloads.progress
        return asdict(progress) if progress is not None else None

    @app.get("/tiles/{z}/{x}/{y}")
    def tile(z: int, x: int, y: str) -> Response:
        tile_store = basemaps.store if basemaps is not None else None

        if tile_store is None:
            raise HTTPException(404, "No basemap configured")

        # Leaflet requests "{y}.png", so y arrives as a string and is parsed
        # here; typing it as int would make FastAPI reject the request with a
        # 422 before this handler ever runs.
        try:
            row = int(y.split(".")[0])
        except ValueError as error:
            raise HTTPException(404, "Malformed tile coordinate") from error

        data = tile_store.get_tile(z, x, row)

        if data is None:
            raise HTTPException(404, "Tile not found")

        return Response(data, media_type="image/png")

    ########################## Diagnostics ##########################

    @app.get("/api/diagnostics")
    def diagnostics() -> dict[str, Any]:
        """Where SARMesh is keeping things, for an operator with no console."""
        return {
            "frozen": is_frozen(),
            "data_dir": str(user_data_dir()),
            "database": _file_json(database.path),
            "log": _file_json(log_path()),
            "basemap_dir": _file_json(
                basemaps.directory if basemaps is not None else None
            ),
        }

    @app.get("/api/diagnostics/log")
    def read_log(lines: int = DEFAULT_LOG_LINES) -> dict[str, Any]:
        path = log_path()
        requested = max(1, min(lines, MAX_LOG_LINES))

        try:
            tail = _tail(path, requested)
        except FileNotFoundError:
            # Nothing has been logged yet, which is not an error worth a 404 --
            # the panel should say the log is empty, not that it failed.
            return {"path": str(path), "exists": False, "lines": []}
        except OSError as error:
            raise HTTPException(500, f"Could not read the log: {error}") from error

        return {"path": str(path), "exists": True, "lines": tail}

    ########################## Frontend ##########################

    if STATIC_DIR.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=STATIC_DIR / "assets"),
            name="assets",
        )

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(STATIC_DIR / "index.html")

    return app


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


def _file_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None

    try:
        size: int | None = path.stat().st_size
    except OSError:
        # Missing, or on a directory whose stat says nothing useful. Either way
        # the path is still worth reporting -- it is the answer to "where would
        # this have been written?"
        size = None

    return {"path": str(path), "exists": path.exists(), "size_bytes": size}


def _as_int(value: str | None) -> int | None:
    """MBTiles metadata values are text, and a hand-built pack may hold junk."""
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def _tail(path: Path, lines: int) -> list[str]:
    """The last `lines` lines of a file, read without loading all of it.

    The log rotates at 1 MB, so reading it whole would nearly always be fine --
    but "nearly always" is not a property worth relying on for a file an
    operator reaches for when something has already gone wrong.
    """
    block = 8192
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        remaining = handle.tell()
        chunks: list[bytes] = []
        found = 0

        while remaining > 0 and found <= lines:
            step = min(block, remaining)
            remaining -= step
            handle.seek(remaining)
            chunk = handle.read(step)
            chunks.append(chunk)
            found += chunk.count(b"\n")

    text = b"".join(reversed(chunks)).decode("utf-8", errors="replace")
    return text.splitlines()[-lines:]


def _discard(path: Path) -> None:
    """Remove a partial upload, without masking the error that caused it."""
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        logger.warning("Could not remove the partial upload %s: %s", path, error)


def _incident_json(incident: Any) -> dict[str, Any]:
    payload = asdict(incident)
    payload["started_at"] = incident.started_at.isoformat()
    payload["ended_at"] = incident.ended_at.isoformat() if incident.ended_at else None
    return payload


def _status_json(status: Any) -> dict[str, Any]:
    position = status.position

    return {
        "tracker": asdict(status.tracker),
        "team": asdict(status.team) if status.team else None,
        "position": {
            **asdict(position),
            "received_at": position.received_at.isoformat(),
        }
        if position
        else None,
        "last_seen_at": status.last_seen_at.isoformat()
        if status.last_seen_at
        else None,
    }

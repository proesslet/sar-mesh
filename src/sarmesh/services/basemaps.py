"""Building an offline basemap pack by fetching tiles from a tile server.

The tile source is supplied by the operator rather than built in. There is no
universal server a search team may hammer, and OpenStreetMap's tile policy
prohibits bulk downloading outright, so the URL template belongs to whoever
is running the search and has the right to fetch from it.

Downloads run on a worker pool because a pack is thousands of small requests,
and are deliberately modest about concurrency: the far end is usually someone
else's server, and finishing a minute sooner is not worth being throttled.
"""

import logging
import math
import re
import sqlite3
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

USER_AGENT = "SARMesh/0.1 (+offline search and rescue basemap import)"

# Tile URLs commonly spread load across a.., b.., c.. hostnames via {s}.
# Leaflet expands it for the map preview, so the downloader has to as well --
# left literal it produces the hostname "{s}.example.com", which fails every
# request with an error that does not obviously point back to the URL.
SUBDOMAINS = ("a", "b", "c")

# Placeholders substituted before a request goes out. {r} marks the retina
# variant; SARMesh stores plain tiles, so it resolves to nothing.
KNOWN_PLACEHOLDERS = ("{z}", "{x}", "{y}", "{s}", "{r}")

# Kept low on purpose: the operator is fetching from a third party, and a
# search team getting rate-limited mid-preparation is worse than a slow pack.
WORKERS = 4
TIMEOUT_SECONDS = 20.0
RETRIES = 2

# A refusal rather than a warning. Zoom 16 over a county is already hundreds of
# thousands of tiles, and the failure mode without a cap is a download that
# looks like it is working for hours before filling the disk.
MAX_TILES = 200_000

# Web Mercator cannot represent the poles; this is the standard cutoff.
MAX_LATITUDE = 85.0511

# Browsing these in the map preview is ordinary usage; pulling a pack off them
# is what their tile usage policy exists to prevent, and the consequence lands
# on the team as a banned IP at the worst possible moment. Refused with an
# explanation rather than left as a trap.
NO_BULK_DOWNLOAD_HOSTS = (
    "tile.openstreetmap.org",
    "tile.osm.org",
    "tile.openstreetmap.de",
    "tiles.openstreetmap.org",
)


@dataclass(frozen=True)
class Bounds:
    west: float
    south: float
    east: float
    north: float

    def normalised(self) -> "Bounds":
        return Bounds(
            west=min(self.west, self.east),
            south=max(min(self.south, self.north), -MAX_LATITUDE),
            east=max(self.west, self.east),
            north=min(max(self.south, self.north), MAX_LATITUDE),
        )


@dataclass(frozen=True)
class DownloadProgress:
    """A snapshot of the running (or last finished) download."""

    name: str
    state: str  # running | done | cancelled | failed
    total: int
    completed: int
    failed: int
    error: str | None = None
    # Why the most recent tile failed. Surfaced while the download is still
    # running: a wrong URL otherwise looks exactly like a stalled one, and the
    # operator finds out only when the whole thing gives up at the end.
    last_error: str | None = None

    @property
    def finished(self) -> bool:
        return self.state != "running"


def tile_bounds(bounds: Bounds, zoom: int) -> tuple[int, int, int, int]:
    """The inclusive x/y tile range covering these bounds at this zoom."""
    scale = 2**zoom

    def x_of(longitude: float) -> int:
        return int((longitude + 180.0) / 360.0 * scale)

    def y_of(latitude: float) -> int:
        radians = math.radians(latitude)
        fraction = (1.0 - math.asinh(math.tan(radians)) / math.pi) / 2.0
        return int(fraction * scale)

    limit = scale - 1
    # y counts down from the north, so the north edge gives the smaller index.
    return (
        max(0, min(limit, x_of(bounds.west))),
        max(0, min(limit, y_of(bounds.north))),
        max(0, min(limit, x_of(bounds.east))),
        max(0, min(limit, y_of(bounds.south))),
    )


def count_tiles(bounds: Bounds, min_zoom: int, max_zoom: int) -> int:
    """How many tiles this area and zoom range comes to."""
    total = 0

    for zoom in range(min_zoom, max_zoom + 1):
        x0, y0, x1, y1 = tile_bounds(bounds, zoom)
        total += (x1 - x0 + 1) * (y1 - y0 + 1)

    return total


def deepest_zoom_within(bounds: Bounds, min_zoom: int, limit: int) -> int | None:
    """The highest max-zoom for this area that still fits under `limit`.

    "Too many tiles, lower the zoom" leaves the operator guessing by how much,
    and every guess costs another round trip. This answers it directly.
    """
    if count_tiles(bounds, min_zoom, min_zoom) > limit:
        return None

    deepest = min_zoom

    for zoom in range(min_zoom + 1, 23):
        if count_tiles(bounds, min_zoom, zoom) > limit:
            break

        deepest = zoom

    return deepest


def expand_template(template: str, zoom: int, x: int, y: int) -> str:
    """Turn a tile URL template into the URL for one tile."""
    url = (
        template.replace("{z}", str(zoom))
        .replace("{x}", str(x))
        .replace("{y}", str(y))
        .replace("{r}", "")
    )

    if "{s}" in url:
        # Spread deterministically, the way Leaflet does, so the same tile
        # always comes from the same host and stays cacheable.
        url = url.replace("{s}", SUBDOMAINS[(x + y) % len(SUBDOMAINS)])

    return url


def validate_template(template: str) -> None:
    """Reject a tile URL that cannot be fetched from, before any work starts."""
    for placeholder in ("{z}", "{x}", "{y}"):
        if placeholder not in template:
            raise ValueError(f"The tile URL must contain {placeholder}")

    # Checked against an expanded URL: {s} belongs to the hostname, and an
    # unexpanded one parses as a host that could never resolve.
    scheme = urlparse(expand_template(template, 0, 0, 0)).scheme.lower()

    # Anything else (file:, ftp:) is either not fetchable or is a way to
    # read the local disk through a field the operator typed into.
    if scheme not in ("http", "https"):
        raise ValueError("The tile URL must be an http:// or https:// address")

    # A placeholder we do not substitute ({apikey}, {quadkey}, a typo) would
    # otherwise be sent literally and fail every single tile. Caught here, when
    # it can still be pointed at the field that caused it.
    leftover = re.findall(r"\{[^}]*\}", expand_template(template, 0, 0, 0))

    if leftover:
        known = ", ".join(KNOWN_PLACEHOLDERS)
        raise ValueError(
            f"The tile URL has a placeholder SARMesh cannot fill in: "
            f"{leftover[0]}. Supported placeholders are {known}; anything else "
            "such as an API key, has to be written out in full."
        )


def check_bulk_allowed(template: str) -> None:
    """Refuse to bulk-download from a source whose terms forbid it."""
    # Expanded first so a {s} placeholder does not hide the real hostname.
    host = (urlparse(expand_template(template, 0, 0, 0)).hostname or "").lower()

    for blocked in NO_BULK_DOWNLOAD_HOSTS:
        if host == blocked or host.endswith(f".{blocked}"):
            raise ValueError(
                f"{host} does not permit bulk tile downloads, and doing it "
                "risks getting this network blocked. Use your own tile server "
                "or a provider whose terms allow it. Viewing the online map "
                "still works."
            )


class BasemapDownloader:
    """Runs at most one pack download at a time, in the background.

    One at a time is a deliberate limit rather than a simplification: the
    machine is a field laptop on a shared uplink, and two downloads competing
    would make both slower and neither easier to reason about.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._progress: DownloadProgress | None = None
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def progress(self) -> DownloadProgress | None:
        with self._lock:
            return self._progress

    def cancel(self) -> None:
        self._cancel.set()

    def start(
        self,
        destination: Path,
        name: str,
        template: str,
        bounds: Bounds,
        min_zoom: int,
        max_zoom: int,
    ) -> DownloadProgress:
        """Begin a download, returning its initial progress.

        Raises RuntimeError if one is already running, or ValueError if the
        request is malformed or too large to be sensible.
        """
        validate_template(template)

        if min_zoom < 0 or max_zoom > 22 or min_zoom > max_zoom:
            raise ValueError("The zoom range must be between 0 and 22")

        area = bounds.normalised()
        total = count_tiles(area, min_zoom, max_zoom)

        if total == 0:
            raise ValueError("That area contains no tiles")

        if total > MAX_TILES:
            raise ValueError(
                f"That area needs {total:,} tiles, over the {MAX_TILES:,} limit. "
                "Reduce the maximum zoom or select a smaller area."
            )

        with self._lock:
            if self._progress is not None and not self._progress.finished:
                raise RuntimeError("A basemap download is already running")

            self._cancel = threading.Event()
            self._progress = DownloadProgress(
                name=name, state="running", total=total, completed=0, failed=0
            )
            progress = self._progress

        self._thread = threading.Thread(
            target=self._run,
            args=(destination, name, template, area, min_zoom, max_zoom),
            daemon=True,
            name="basemap-download",
        )
        self._thread.start()

        return progress

    def _update(self, **changes: object) -> None:
        with self._lock:
            if self._progress is not None:
                self._progress = replace(self._progress, **changes)  # type: ignore[arg-type]

    def _run(
        self,
        destination: Path,
        name: str,
        template: str,
        bounds: Bounds,
        min_zoom: int,
        max_zoom: int,
    ) -> None:
        partial = destination.with_name(destination.name + ".partial")
        writer_lock = threading.Lock()
        completed = 0
        failed = 0
        last_error: str | None = None

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            partial.unlink(missing_ok=True)
            connection = _open_pack(partial, name, bounds, min_zoom, max_zoom)
        except (OSError, sqlite3.Error) as error:
            logger.exception("Could not start the basemap download")
            self._update(state="failed", error=str(error))
            return

        def fetch(job: tuple[int, int, int]) -> tuple[bool, str | None]:
            # Already-queued work drains without touching the network once a
            # cancel arrives, instead of finishing the whole window first.
            if self._cancel.is_set():
                return False, None

            zoom, x, y = job
            data, reason = _get_tile(template, zoom, x, y)

            if data is None:
                return False, reason

            # MBTiles rows are TMS, counted from the bottom.
            flipped = (2**zoom - 1) - y

            with writer_lock:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO tiles
                    (zoom_level, tile_column, tile_row, tile_data)
                    VALUES (?, ?, ?, ?)
                    """,
                    (zoom, x, flipped, data),
                )

            return True, None

        jobs = _jobs(bounds, min_zoom, max_zoom, self._cancel)

        try:
            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                # Submitted a window at a time rather than through pool.map,
                # which queues every job up front: that both holds a future per
                # tile in memory and makes cancelling useless, because the work
                # is already committed to the pool by the time it is asked to
                # stop.
                in_flight: set[Future[tuple[bool, str | None]]] = set()

                while True:
                    while len(in_flight) < WORKERS * 4:
                        job = next(jobs, None)

                        if job is None:
                            break

                        in_flight.add(pool.submit(fetch, job))

                    if not in_flight:
                        break

                    done, in_flight = wait(in_flight, return_when=FIRST_COMPLETED)

                    for future in done:
                        ok, reason = future.result()

                        if ok:
                            completed += 1
                        else:
                            failed += 1

                            if reason is not None:
                                last_error = reason

                    # Reported every batch, not every few hundred tiles: a
                    # progress bar that sits at zero for the first minute of a
                    # download is indistinguishable from one that is broken.
                    self._update(
                        completed=completed, failed=failed, last_error=last_error
                    )

                    # Committing periodically keeps a long download's work on
                    # disk, so a crash at tile 90,000 does not throw all of it
                    # away.
                    if (completed + failed) % 500 < len(done):
                        with writer_lock:
                            connection.commit()

            with writer_lock:
                connection.commit()
        # Broad on purpose: whatever went wrong, the operator has to be told
        # rather than left watching a progress bar that stopped moving.
        except Exception as error:
            logger.exception("Basemap download failed")
            connection.close()
            partial.unlink(missing_ok=True)
            self._update(
                state="failed", completed=completed, failed=failed, error=str(error)
            )
            return

        connection.close()

        if self._cancel.is_set():
            partial.unlink(missing_ok=True)
            self._update(state="cancelled", completed=completed, failed=failed)
            logger.info("Basemap download cancelled after %d tiles", completed)
            return

        if completed == 0:
            partial.unlink(missing_ok=True)
            self._update(
                state="failed",
                completed=completed,
                failed=failed,
                error=(
                    f"No tiles could be fetched: {last_error}"
                    if last_error
                    else "No tiles could be fetched. Check the tile URL."
                ),
            )
            return

        partial.replace(destination)
        self._update(state="done", completed=completed, failed=failed)
        logger.info(
            "Basemap %s downloaded: %d tiles, %d missing", name, completed, failed
        )


def _jobs(
    bounds: Bounds, min_zoom: int, max_zoom: int, cancel: threading.Event
) -> Iterator[tuple[int, int, int]]:
    """Yield every tile coordinate to fetch, stopping early on cancel."""
    for zoom in range(min_zoom, max_zoom + 1):
        x0, y0, x1, y1 = tile_bounds(bounds, zoom)

        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                if cancel.is_set():
                    return

                yield (zoom, x, y)


def _get_tile(
    template: str, zoom: int, x: int, y: int
) -> tuple[bytes | None, str | None]:
    """Fetch one tile, returning its bytes or the reason it could not be had.

    The reason is carried back rather than logged and dropped: "every tile is
    failing because the host does not resolve" is the single most useful thing
    to put in front of an operator watching a download that is going nowhere.
    """
    request = urllib.request.Request(
        expand_template(template, zoom, x, y), headers={"User-Agent": USER_AGENT}
    )

    for attempt in range(RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return response.read(), None
        except urllib.error.HTTPError as error:
            # A 404 is a real answer, meaning no tile at this zoom, so it is
            # so there is nothing to retry, and it is not worth reporting as a
            # fault: coverage gaps at the edges of an area are normal.
            if error.code == 404:
                return None, None

            if attempt == RETRIES:
                reason = f"HTTP {error.code} {error.reason}"
                logger.debug("Tile %d/%d/%d failed: %s", zoom, x, y, reason)
                return None, reason
        except urllib.error.URLError as error:
            if attempt == RETRIES:
                reason = str(error.reason)
                logger.debug("Tile %d/%d/%d failed: %s", zoom, x, y, reason)
                return None, reason
        except OSError as error:
            if attempt == RETRIES:
                logger.debug("Tile %d/%d/%d failed: %s", zoom, x, y, error)
                return None, str(error)

    return None, None


def _open_pack(
    path: Path, name: str, bounds: Bounds, min_zoom: int, max_zoom: int
) -> sqlite3.Connection:
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata (name TEXT, value TEXT);
        CREATE TABLE IF NOT EXISTS tiles (
            zoom_level INTEGER,
            tile_column INTEGER,
            tile_row INTEGER,
            tile_data BLOB
        );
        CREATE UNIQUE INDEX IF NOT EXISTS tile_index
            ON tiles (zoom_level, tile_column, tile_row);
        """
    )
    connection.executemany(
        "INSERT INTO metadata (name, value) VALUES (?, ?)",
        [
            ("name", name),
            ("format", "png"),
            ("type", "baselayer"),
            ("version", "1.0.0"),
            ("minzoom", str(min_zoom)),
            ("maxzoom", str(max_zoom)),
            (
                "bounds",
                f"{bounds.west},{bounds.south},{bounds.east},{bounds.north}",
            ),
        ],
    )
    connection.commit()
    return connection

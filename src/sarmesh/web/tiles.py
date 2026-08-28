import logging
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

MBTILES_SUFFIX = ".mbtiles"

# Written to a temporary name and renamed into place, so an interrupted import
# never leaves a half-written file looking like a usable pack.
PARTIAL_SUFFIX = ".partial"

logger = logging.getLogger(__name__)


class TileStore:
    """Reads raster tiles from an MBTiles pack so basemaps work offline.

    MBTiles stores rows in TMS order, where y is counted from the bottom,
    while Leaflet requests XYZ tiles counted from the top. The flip in
    get_tile is what reconciles the two.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._connection: sqlite3.Connection | None = None
        self._closed = False

    def _connect(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(
                f"file:{self.path}?mode=ro",
                uri=True,
                check_same_thread=False,
            )
        return self._connection

    def get_tile(self, z: int, x: int, y: int) -> bytes | None:
        flipped = (2**z - 1) - y

        with self._lock:
            # A tile request that raced a basemap swap can arrive after close.
            # Without this the connection would simply be reopened, quietly
            # resurrecting a store the library has already discarded.
            if self._closed:
                return None

            cursor = self._connect().execute(
                """
                SELECT tile_data FROM tiles
                WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?
                """,
                (z, x, flipped),
            )
            row = cursor.fetchone()

        return row[0] if row is not None else None

    def metadata(self) -> dict[str, str]:
        with self._lock:
            if self._closed:
                return {}

            cursor = self._connect().execute("SELECT name, value FROM metadata")
            return {name: value for name, value in cursor.fetchall()}

    def close(self) -> None:
        with self._lock:
            self._closed = True

            if self._connection is not None:
                self._connection.close()
                self._connection = None


@dataclass(frozen=True)
class BasemapPack:
    """One MBTiles file the operator can serve the map from."""

    name: str
    path: Path
    size_bytes: int
    # None when the file is not a readable MBTiles pack -- it is still listed,
    # because a corrupt or truncated download is something the operator needs
    # to see rather than something that should silently vanish from the list.
    metadata: dict[str, str] | None


class BasemapLibrary:
    """The basemap packs available, and which one /tiles is serving.

    A pack is chosen while the app is running, so the TileStore behind the tile
    route has to be swappable rather than fixed at startup. Selection always
    goes through the enumerated pack list instead of joining a caller-supplied
    name onto a directory, which is what keeps a crafted name from reaching a
    file outside the library.
    """

    def __init__(self, directory: Path, pinned: Path | None = None) -> None:
        self.directory = directory
        # A --basemap path may point anywhere on disk. It is carried alongside
        # the directory so the command-line flag and the in-app picker agree on
        # what is available.
        self.pinned = pinned

        self._lock = threading.Lock()
        self._store: TileStore | None = None
        self._active: str | None = None
        # Bumped on every swap so the frontend can force Leaflet to refetch.
        # Tile URLs are otherwise identical between packs, and the browser
        # would keep serving the previous pack's tiles from cache.
        self._revision = 0

    ########################## Enumeration ##########################

    def packs(self) -> list[BasemapPack]:
        found: dict[str, BasemapPack] = {}

        if self.pinned is not None and self.pinned.is_file():
            found[self.pinned.name] = _describe(self.pinned)

        if self.directory.is_dir():
            for path in sorted(self.directory.glob(f"*{MBTILES_SUFFIX}")):
                # On a name collision the pinned pack wins: it is the one the
                # operator named explicitly on the command line.
                if path.name not in found:
                    found[path.name] = _describe(path)

        return list(found.values())

    def find(self, name: str) -> BasemapPack | None:
        return next((pack for pack in self.packs() if pack.name == name), None)

    @property
    def active_name(self) -> str | None:
        with self._lock:
            return self._active

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    @property
    def store(self) -> TileStore | None:
        with self._lock:
            return self._store

    ########################## Selection ##########################

    def select(self, name: str | None) -> None:
        """Serve tiles from the named pack, or from none at all.

        Raises KeyError if no pack by that name is in the library.
        """
        target: Path | None = None

        if name is not None:
            pack = self.find(name)

            if pack is None:
                raise KeyError(name)

            target = pack.path

        with self._lock:
            if name == self._active:
                return

            previous = self._store
            self._store = TileStore(target) if target is not None else None
            self._active = name
            self._revision += 1

        # Closed outside the lock: close() waits on any tile read still in
        # flight, and holding the library lock for that would stall every other
        # caller behind a swap.
        if previous is not None:
            previous.close()

    def select_default(self, saved: str | None) -> None:
        """Choose what to serve at startup.

        An explicit --basemap wins, because it was asked for on this run. Then
        the pack chosen in a previous session, if it is still there -- a pack
        deleted between runs must not stop the app from starting.
        """
        if self.pinned is not None and self.pinned.is_file():
            self.select(self.pinned.name)
            return

        if saved is not None and self.find(saved) is not None:
            self.select(saved)
            return

        if saved is not None:
            logger.warning("Previously selected basemap %s is missing", saved)

    ########################## Import ##########################

    def import_path(self, name: str) -> Path:
        """Where an uploaded pack of this name should be written.

        Raises ValueError for a name that is not a plain MBTiles filename. The
        resolved-parent check is belt and braces behind that: a name reaching
        outside the library directory must never produce a writable path, no
        matter what the string sanitising missed.
        """
        if not name.endswith(MBTILES_SUFFIX) or len(name) <= len(MBTILES_SUFFIX):
            raise ValueError(f"A basemap pack must be a *{MBTILES_SUFFIX} file")

        if name != Path(name).name or name.startswith("."):
            raise ValueError("A basemap pack name must be a plain filename")

        directory = self.directory.resolve()
        path = (directory / name).resolve()

        if path.parent != directory:
            raise ValueError("A basemap pack name must be a plain filename")

        return path

    def close(self) -> None:
        with self._lock:
            store = self._store
            self._store = None
            self._active = None

        if store is not None:
            store.close()


def read_metadata(path: Path) -> dict[str, str] | None:
    """Read an MBTiles pack's metadata table, or None if it is unreadable."""
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None

    try:
        cursor = connection.execute("SELECT name, value FROM metadata")
        return {name: value for name, value in cursor.fetchall()}
    except sqlite3.Error:
        # Not an MBTiles file, or a truncated one. Reported as unreadable
        # rather than raised: listing the packs must not fail because one of
        # them is bad.
        return None
    finally:
        connection.close()


def _describe(path: Path) -> BasemapPack:
    try:
        size = path.stat().st_size
    except OSError:
        size = 0

    return BasemapPack(
        name=path.name,
        path=path,
        size_bytes=size,
        metadata=read_metadata(path),
    )

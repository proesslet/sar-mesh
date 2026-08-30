import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from sarmesh import __version__
from sarmesh.storage.paths import is_frozen, log_path, user_data_dir
from sarmesh.web.dependencies import Db, OptionalBasemaps
from sarmesh.web.schemas import DiagnosticsOut, FileLocationOut, LogTailOut

# The log is read for display, so the tail is capped at something a browser can
# render. The full file is on disk for anyone who needs more.
MAX_LOG_LINES = 2000
DEFAULT_LOG_LINES = 200

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("")
def diagnostics(database: Db, basemaps: OptionalBasemaps) -> DiagnosticsOut:
    """Where SARMesh is keeping things, for an operator with no console."""
    return DiagnosticsOut(
        frozen=is_frozen(),
        version=__version__,
        data_dir=str(user_data_dir()),
        database=_file_location(database.path),
        log=_file_location(log_path()),
        basemap_dir=_file_location(basemaps.directory) if basemaps else None,
    )


@router.get("/log")
def read_log(lines: int = DEFAULT_LOG_LINES) -> LogTailOut:
    path = log_path()
    requested = max(1, min(lines, MAX_LOG_LINES))

    try:
        tail = _tail(path, requested)
    except FileNotFoundError:
        # Nothing logged yet. The panel should say the log is empty rather
        # than that it failed, so this is not a 404.
        return LogTailOut(path=str(path), exists=False, lines=[])
    except OSError as error:
        raise HTTPException(500, f"Could not read the log: {error}") from error

    return LogTailOut(path=str(path), exists=True, lines=tail)


def _file_location(path: Path) -> FileLocationOut:
    try:
        size: int | None = path.stat().st_size
    except OSError:
        # Missing, or a directory whose stat says nothing useful. The path is
        # still worth reporting: it answers "where would this have gone?"
        size = None

    return FileLocationOut(path=str(path), exists=path.exists(), size_bytes=size)


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

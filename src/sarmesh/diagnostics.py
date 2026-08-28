"""Telling the operator something went wrong, from a process with no console.

The bundle is built windowed, so on Windows it has no stdout at all and a
double-clicked macOS .app has none worth reading. Anything printed in those
builds is simply lost, which is why every diagnostic also goes to a rotating
file, and why a fatal error gets a dialog: otherwise a failed start is
indistinguishable from nothing happening.
"""

import contextlib
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from sarmesh.storage.paths import is_frozen, log_path

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

# An incident can run for days on a Pi. Three 1 MB files keep the tail of a
# long deployment without ever growing without bound on an SD card.
MAX_BYTES = 1_000_000
BACKUP_COUNT = 3

logger = logging.getLogger(__name__)


def configure_logging(level: int = logging.INFO) -> Path:
    """Send logging to the log file, and to the console if there is one.

    Returns the log file's path so callers can point an operator at it.
    """
    path = log_path()
    root = logging.getLogger()
    root.setLevel(level)

    # Idempotent: both the frozen entry point and the CLI callback call this,
    # and a second call must not double every line.
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(LOG_FORMAT)
    file_error: OSError | None = None

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError as error:
        # A read-only or unwritable home must not stop the app from starting --
        # an operator with no log is still better off than one with no app.
        file_error = error
    else:
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # None in a windowed build; adding a StreamHandler for it would raise.
    if sys.stderr is not None:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    # Every map pan is a burst of tile requests, so per-request logging would
    # bury the events that matter. Errors still propagate to the root logger.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    if file_error is not None:
        logger.warning("Could not open the log file at %s: %s", path, file_error)

    return path


def report_fatal_error(message: str) -> None:
    """Put a fatal error where the operator will actually see it."""
    logger.error(message)

    if sys.stderr is not None:
        print(message, file=sys.stderr)

    # Only a windowed build needs the dialog. Started from a terminal, the
    # message above has already been seen and a modal box is just in the way.
    if not is_frozen():
        return

    try:
        from sarmesh.desktop import show_error
    except ImportError:
        # Qt is what failed, so there is nothing left to show a dialog with.
        return

    detail = f"{message}\n\nDetails are in:\n{log_path()}"

    # A dialog is the last thing tried on a path that is already failing; it
    # must not replace the real error with a Qt one.
    with contextlib.suppress(Exception):
        show_error(detail)

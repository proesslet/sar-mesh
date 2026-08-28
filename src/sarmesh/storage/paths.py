"""Where SARMesh keeps its data on disk.

A double-clicked bundle inherits a useless working directory: the filesystem
root on macOS, the shortcut's target on Windows. A frozen build therefore
writes to the per-user data directory, while a source checkout keeps the cwd.
SARMESH_DB overrides both, which is how a build is pointed at an incident
database on removable media.
"""

import os
import sys
from pathlib import Path

DATABASE_NAME = "sarmesh.db"
LOG_NAME = "sarmesh.log"
BASEMAP_DIR_NAME = "basemaps"

# Windows and macOS put a display name in their data directories; XDG expects a
# lowercase one.
WINDOWS_APP_DIR = "SARMesh"
MACOS_APP_DIR = "SARMesh"
XDG_APP_DIR = "sarmesh"


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle rather than a checkout."""
    return getattr(sys, "frozen", False)


def user_data_dir() -> Path:
    """The per-user directory a packaged SARMesh stores data in."""
    if sys.platform == "win32":
        base = _base_dir("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        return base / WINDOWS_APP_DIR

    if sys.platform == "darwin":
        # macOS has no environment override; the location is fixed by convention.
        return Path.home() / "Library" / "Application Support" / MACOS_APP_DIR

    base = _base_dir("XDG_DATA_HOME", Path.home() / ".local" / "share")
    return base / XDG_APP_DIR


def default_database_path() -> Path:
    """The database every command uses unless told otherwise."""
    override = os.environ.get("SARMESH_DB")

    if override:
        return Path(override).expanduser()

    if is_frozen():
        return user_data_dir() / DATABASE_NAME

    return Path(DATABASE_NAME)


def log_path() -> Path:
    """Where diagnostics are written.

    Always the user data directory, source checkout included. The question a
    log has to answer is "the app did not start, why?", which is easiest when
    the file is in one fixed place.
    """
    return user_data_dir() / LOG_NAME


def basemap_dir() -> Path:
    """Where offline basemap packs are kept.

    Like the log this defaults to the user data directory rather than the
    working one: a pack is reusable across incidents and routinely several
    gigabytes, so it should not be copied around with a checkout.

    SARMESH_BASEMAP_DIR overrides it, which is how a deployment points at packs
    on removable media without moving the database too.
    """
    override = os.environ.get("SARMESH_BASEMAP_DIR")

    if override:
        return Path(override).expanduser()

    return user_data_dir() / BASEMAP_DIR_NAME


def _base_dir(variable: str, fallback: Path) -> Path:
    value = os.environ.get(variable)

    if not value:
        return fallback

    path = Path(value)

    # The XDG spec requires an absolute path and says to ignore a relative one.
    # The same guard stops a malformed LOCALAPPDATA from silently writing the
    # database into the working directory, which is the bug this module exists
    # to prevent.
    if not path.is_absolute():
        return fallback

    return path

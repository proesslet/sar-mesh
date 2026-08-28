"""Where SARMesh keeps its data on disk.

A packaged app is launched by double-clicking, so its working directory is
whatever the OS happened to hand it -- the filesystem root for a macOS .app
bundle, the shortcut's target on Windows. Resolving the database against that
would scatter incident data across directories, or fail outright on a
read-only path, so a frozen build writes to the per-user data directory
instead. Running from source keeps the working directory, which is what a
development checkout wants.

SARMESH_DB overrides both. It is the way to point a build at a specific
database -- an incident kept on removable media, say -- and because every
command reads it, the CLI and the app stay in agreement.
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

    Unlike the database this is always the user data directory, source checkout
    included. A log is a diagnostic rather than incident data, and the one
    question it has to answer -- "the app did not start, why?" -- is easiest to
    answer when the file is in a fixed place instead of wherever the app
    happened to be launched from.
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

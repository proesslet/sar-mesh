"""Offline search and rescue personnel tracking over mesh radio networks."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sarmesh")
except PackageNotFoundError:
    # No installed distribution to read metadata from. That happens in a frozen
    # build unless the packaging step is told to carry the metadata along, so
    # the About panel says "unknown" rather than reporting a version that would
    # quietly go stale.
    __version__ = "unknown"

__all__ = ["__version__"]

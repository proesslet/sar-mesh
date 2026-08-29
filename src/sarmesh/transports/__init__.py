"""Sources of live positions.

The app takes whichever transport it is handed, so a development simulator can
stand in for a radio without anything downstream knowing the difference.
"""

from collections.abc import Callable
from typing import Protocol

from sarmesh.core.models import TrackerPosition

PositionHandler = Callable[[TrackerPosition], None]


class Transport(Protocol):
    """Anything that can feed positions into the tracking service."""

    def start(self) -> None:
        """Begin delivering positions, or raise ConnectionError."""
        ...

    def stop(self) -> None:
        """Stop delivering. Called on shutdown, including after a failed start."""
        ...


TransportFactory = Callable[[PositionHandler], Transport]

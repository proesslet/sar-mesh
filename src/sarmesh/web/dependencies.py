"""Wiring between the app's collaborators and the route modules.

The objects a route needs are put on `app.state` by create_app and pulled back
out here, so no route has to be defined inside a closure to reach them.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from sarmesh.core.events import PositionBroadcaster
from sarmesh.services.basemaps import BasemapDownloader
from sarmesh.storage.database import Database
from sarmesh.web.tiles import BasemapLibrary


def get_database(request: Request) -> Database:
    database: Database = request.app.state.database
    return database


def get_broadcaster(request: Request) -> PositionBroadcaster:
    broadcaster: PositionBroadcaster = request.app.state.broadcaster
    return broadcaster


def get_downloader(request: Request) -> BasemapDownloader:
    downloader: BasemapDownloader = request.app.state.downloader
    return downloader


def get_basemaps(request: Request) -> BasemapLibrary | None:
    # None when create_app was given no library, which is the case in tests
    # and for a headless run with no packs.
    library: BasemapLibrary | None = request.app.state.basemaps
    return library


def require_basemaps(
    basemaps: Annotated[BasemapLibrary | None, Depends(get_basemaps)],
) -> BasemapLibrary:
    """The library, 404ing when there is none.

    Routes that only read fall back to an empty payload and take the optional
    form; routes that mutate take this one instead.
    """
    if basemaps is None:
        raise HTTPException(404, "No basemap library configured")

    return basemaps


# Aliases, so a handler signature reads as `database: Db` rather than carrying
# the full Annotated spelling on every route.
Db = Annotated[Database, Depends(get_database)]
Broadcaster = Annotated[PositionBroadcaster, Depends(get_broadcaster)]
Downloader = Annotated[BasemapDownloader, Depends(get_downloader)]
OptionalBasemaps = Annotated[BasemapLibrary | None, Depends(get_basemaps)]
Basemaps = Annotated[BasemapLibrary, Depends(require_basemaps)]

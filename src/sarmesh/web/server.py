"""Builds the FastAPI application: wiring, lifespan, and the static frontend.

Every route lives in a module under `routes/`. The collaborators they need are
put on `app.state` here and pulled back out by `dependencies`, so no handler
has to be nested in a closure to reach the database or the radio broadcaster.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sarmesh.core.events import PositionBroadcaster
from sarmesh.services.basemaps import BasemapDownloader
from sarmesh.storage.database import Database
from sarmesh.web.routes import (
    assignments,
    basemaps_routes,
    diagnostics,
    events,
    incidents,
    nodes,
    radio,
    teams,
    trackers,
    tracks,
)
from sarmesh.web.tiles import BasemapLibrary

STATIC_DIR = Path(__file__).parent / "static"

ROUTERS: tuple[APIRouter, ...] = (
    incidents.router,
    teams.router,
    trackers.router,
    assignments.router,
    events.router,
    nodes.router,
    radio.router,
    tracks.router,
    basemaps_routes.router,
    diagnostics.router,
)


def create_app(
    database: Database,
    broadcaster: PositionBroadcaster,
    basemaps: BasemapLibrary | None = None,
    downloader: BasemapDownloader | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        # The broadcaster needs the serving loop to hand positions over from
        # the radio thread, and it only exists once the server is running.
        broadcaster.bind_loop(asyncio.get_running_loop())
        yield

    app = FastAPI(title="SARMesh", lifespan=lifespan)

    app.state.database = database
    app.state.broadcaster = broadcaster
    app.state.basemaps = basemaps
    app.state.downloader = downloader if downloader is not None else BasemapDownloader()
    app.state.radio = None

    for router in ROUTERS:
        app.include_router(router)

    _mount_frontend(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the compiled UI, when there is one.

    Absent in a source checkout that has not run `npm run build`, which is a
    working state: the API still answers the Vite dev server's proxy.
    """
    if not STATIC_DIR.is_dir():
        return

    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

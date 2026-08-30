"""The live view: a snapshot of where everyone is, and the stream of updates.

Both halves live here because they answer the same question. /api/status is
what the map draws on load, /events is what keeps it current.
"""

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from sarmesh.web import views
from sarmesh.web.dependencies import Broadcaster, Db
from sarmesh.web.schemas import TrackerStatusOut

# Sent after this long with no positions, so an idle mesh is distinguishable
# from a dead connection and proxies do not time the stream out.
HEARTBEAT_SECONDS = 15.0

router = APIRouter(tags=["live"])


@router.get("/api/status")
def status(database: Db, incident_id: str | None = None) -> list[TrackerStatusOut]:
    resolved = views.resolve_incident(database, incident_id)

    if resolved is None:
        return []

    return views.list_statuses(database, resolved)


@router.get("/events")
async def events(broadcaster: Broadcaster) -> StreamingResponse:
    queue = broadcaster.subscribe()

    async def stream() -> AsyncGenerator[str, None]:
        try:
            yield ": connected\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(
                        queue.get(), timeout=HEARTBEAT_SECONDS
                    )
                except TimeoutError:
                    yield ": heartbeat\n\n"
                    continue

                yield f"event: position\ndata: {json.dumps(payload)}\n\n"
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

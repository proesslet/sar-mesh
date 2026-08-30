"""Where each tracker has been, as opposed to where it is now.

The trail is what shows which ground a team has actually covered, and it is
what an after-action review reads.
"""

from datetime import datetime

from fastapi import APIRouter, Query

from sarmesh.storage.repositories.positions import MAX_TRACK_POINTS
from sarmesh.web import views
from sarmesh.web.dependencies import Db
from sarmesh.web.schemas import TrackOut

router = APIRouter(prefix="/api/tracks", tags=["tracks"])


@router.get("")
def tracks(
    database: Db,
    incident_id: str | None = None,
    since: datetime | None = None,
    limit: int = Query(default=MAX_TRACK_POINTS, ge=1, le=10_000),
) -> list[TrackOut]:
    """Every assigned tracker's trail, oldest fix first.

    `since` is an absolute time rather than a duration, because the useful
    question is often "since this incident started" rather than "in the last
    four hours", and only the caller knows which it meant.
    """
    resolved = views.resolve_incident(database, incident_id)

    if resolved is None:
        return []

    return views.list_tracks(database, resolved, since=since, limit=limit)

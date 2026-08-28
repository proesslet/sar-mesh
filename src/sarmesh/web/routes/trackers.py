import logging

from fastapi import APIRouter, HTTPException

from sarmesh.web import views
from sarmesh.web.dependencies import Db
from sarmesh.web.schemas import (
    TrackerCreate,
    TrackerOut,
    TrackerUpdate,
    UnregisteredNodeOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trackers", tags=["trackers"])


@router.get("")
def list_trackers(database: Db) -> list[TrackerOut]:
    return views.list_trackers(database)


# Before "/{node_id}": FastAPI matches in declaration order.
@router.get("/unregistered")
def unregistered_nodes(database: Db) -> list[UnregisteredNodeOut]:
    """Nodes heard on the mesh that have no tracker record yet.

    Positions are stored for every node that beacons, but only registered
    trackers appear anywhere in the UI. Without this an operator has to know a
    node's hex id by heart to add it, which is not something anyone does in the
    field.
    """
    known = {t.node_id for t in database.trackers.list()}

    return [
        UnregisteredNodeOut(
            node_id=position.node_id,
            node_num=position.node_num,
            last_seen_at=position.received_at,
        )
        for position in database.positions.latest_per_node()
        if position.node_id not in known
    ]


@router.post("", status_code=201)
def create_tracker(body: TrackerCreate, database: Db) -> TrackerOut:
    if database.trackers.get(body.node_id) is not None:
        raise HTTPException(409, f"Tracker {body.node_id} already exists")

    tracker = database.trackers.create(node_id=body.node_id, label=body.label)

    return TrackerOut.model_validate(tracker)


@router.delete("/{node_id}")
def delete_tracker(node_id: str, database: Db) -> list[TrackerOut]:
    """Remove a tracker, unless a team is currently carrying it.

    Returns the remaining trackers rather than an empty 204, so the caller
    cannot show a list that disagrees with the database.
    """
    if database.trackers.get(node_id) is None:
        raise HTTPException(404, f"No tracker {node_id}")

    assignment = database.assignments.active_for(node_id)

    if assignment is not None:
        team = database.teams.get(assignment.team_id)
        held_by = team.name if team else assignment.team_id
        raise HTTPException(
            409,
            f"{node_id} is assigned to {held_by}. Unassign it before "
            "deleting, or the team's positions stop being attributed to "
            "anyone.",
        )

    # Recorded positions are deliberately left in place: they belong to the
    # incident that was being run, not to the tracker record, and an
    # after-action review still needs them.
    database.trackers.delete(node_id)
    logger.info("Deleted tracker %s", node_id)

    return views.list_trackers(database)


@router.patch("/{node_id}")
def update_tracker(node_id: str, body: TrackerUpdate, database: Db) -> TrackerOut:
    if database.trackers.get(node_id) is None:
        raise HTTPException(404, f"No tracker {node_id}")

    updated = database.trackers.update(node_id, label=body.label)

    if updated is None:
        raise HTTPException(404, f"No tracker {node_id}")

    # Renaming does not release the tracker, so its assignment has to be
    # carried through rather than dropped.
    return views.describe_tracker(database, updated)

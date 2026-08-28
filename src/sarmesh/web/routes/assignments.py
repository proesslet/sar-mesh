import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from sarmesh.web import views
from sarmesh.web.dependencies import Db
from sarmesh.web.schemas import AssignmentCreate, AssignmentOut, TrackerOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assignments", tags=["assignments"])


@router.post("", status_code=201)
def create_assignment(body: AssignmentCreate, database: Db) -> AssignmentOut:
    if database.incidents.get(body.incident_id) is None:
        raise HTTPException(404, f"No incident {body.incident_id}")

    if database.trackers.get(body.tracker_node_id) is None:
        raise HTTPException(404, f"No tracker {body.tracker_node_id}")

    team = database.teams.get(body.team_id)

    if team is None:
        raise HTTPException(404, f"No team {body.team_id}")

    existing = database.assignments.active_for(body.tracker_node_id)

    if existing is not None:
        held_by = database.teams.get(existing.team_id)
        raise HTTPException(
            409,
            f"{body.tracker_node_id} is already assigned to "
            f"{held_by.name if held_by else existing.team_id}. "
            "Unassign it first.",
        )

    assignment = database.assignments.create(
        incident_id=body.incident_id,
        tracker_node_id=body.tracker_node_id,
        team_id=body.team_id,
    )
    logger.info("Assigned %s to %s", body.tracker_node_id, team.name)

    return AssignmentOut.model_validate(assignment)


@router.delete("/{node_id}")
def delete_assignment(node_id: str, database: Db) -> list[TrackerOut]:
    """Release a tracker from whatever team is holding it.

    Returns the trackers, since their assignment state is what the caller is
    showing.
    """
    if database.assignments.active_for(node_id) is None:
        raise HTTPException(404, f"{node_id} is not assigned to anything")

    database.assignments.release(node_id, unassigned_at=datetime.now(UTC))
    logger.info("Unassigned %s", node_id)

    return views.list_trackers(database)

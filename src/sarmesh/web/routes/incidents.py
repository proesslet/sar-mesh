from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from sarmesh.web.dependencies import Db
from sarmesh.web.schemas import IncidentCreate, IncidentOut, IncidentUpdate

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("")
def list_incidents(database: Db) -> list[IncidentOut]:
    return [IncidentOut.model_validate(i) for i in database.incidents.list()]


# Before "/{incident_id}": FastAPI matches in declaration order.
@router.get("/active")
def active_incident(database: Db) -> IncidentOut | None:
    incident = database.incidents.active()

    return IncidentOut.model_validate(incident) if incident else None


@router.post("", status_code=201)
def create_incident(body: IncidentCreate, database: Db) -> IncidentOut:
    return IncidentOut.model_validate(database.incidents.create(name=body.name))


@router.patch("/{incident_id}")
def update_incident(
    incident_id: str, body: IncidentUpdate, database: Db
) -> IncidentOut:
    if database.incidents.get(incident_id) is None:
        raise HTTPException(404, f"No incident {incident_id}")

    updated = database.incidents.update(incident_id, name=body.name)

    if updated is None:
        raise HTTPException(404, f"No incident {incident_id}")

    return IncidentOut.model_validate(updated)


@router.post("/{incident_id}/end")
def end_incident(incident_id: str, database: Db) -> IncidentOut:
    incident = database.incidents.get(incident_id)

    if incident is None:
        raise HTTPException(404, f"No incident {incident_id}")

    # Ending twice would move the end time of an incident that is already
    # closed, rewriting a record the operator relies on.
    if incident.ended_at is not None:
        raise HTTPException(409, f"Incident {incident.name} has already ended")

    # Released before the incident closes. An assignment outliving its incident
    # keeps stamping incoming positions with a closed one, and blocks the
    # tracker from joining the next search.
    closed_at = datetime.now(UTC)

    for assignment in database.assignments.active_for_incident(incident_id):
        database.assignments.release(
            assignment.tracker_node_id, unassigned_at=closed_at
        )

    database.incidents.end(incident_id, ended_at=closed_at)
    ended = database.incidents.get(incident_id)

    if ended is None:
        raise HTTPException(404, f"No incident {incident_id}")

    return IncidentOut.model_validate(ended)

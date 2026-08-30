"""Every node heard on the mesh, not just the ones working this incident.

/api/status answers "where are my teams". This answers "what else is out
there", which is what an operator needs in order to spot a tracker that is
beaconing but has not been assigned to anyone yet.
"""

from fastapi import APIRouter

from sarmesh.web import views
from sarmesh.web.dependencies import Db
from sarmesh.web.schemas import NodeOut

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


@router.get("")
def nodes(database: Db, incident_id: str | None = None) -> list[NodeOut]:
    resolved = views.resolve_incident(database, incident_id)

    if resolved is None:
        return []

    return views.list_nodes(database, resolved)

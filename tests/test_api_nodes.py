"""/api/nodes -- everything heard on the mesh, not just this incident's teams.

The point of this endpoint is the node that is beaconing but has not been given
to anyone yet, so the cases here are mostly about what it must NOT leave out.
"""

from datetime import UTC, datetime, timedelta

from conftest import make_position
from fastapi.testclient import TestClient

from sarmesh.storage.database import Database


def test_nodes_are_empty_with_no_active_incident(client: TestClient) -> None:
    response = client.get("/api/nodes")

    assert response.status_code == 200
    assert response.json() == []


def test_nodes_include_a_node_with_no_tracker_record(
    client: TestClient, database: Database, incident_id: str
) -> None:
    """A stranger on the mesh is exactly what this is for, so it has to be
    plotted even though nothing has been registered for it."""
    database.positions.save(
        make_position("!stranger", received_at=datetime.now(UTC)), incident_id=None
    )

    [node] = client.get("/api/nodes").json()

    assert node["node_id"] == "!stranger"
    assert node["label"] is None
    assert node["team"] is None
    assert node["position"]["latitude"] == 44.4280


def test_nodes_name_a_registered_tracker(
    client: TestClient, database: Database, incident_id: str, node_id: str
) -> None:
    """Registered but unassigned: it has a label but no team, and /api/status
    would leave it out entirely."""
    database.positions.save(
        make_position(node_id, received_at=datetime.now(UTC)), incident_id=None
    )

    [node] = client.get("/api/nodes").json()

    assert node["label"] == "Alpha 1"
    assert node["team"] is None


def test_nodes_carry_the_team_of_a_tracker_on_this_incident(
    client: TestClient, database: Database, assigned_tracker: str
) -> None:
    assignment = database.assignments.active_for(assigned_tracker)
    assert assignment is not None
    database.positions.save(
        make_position(assigned_tracker, received_at=datetime.now(UTC)),
        incident_id=assignment.incident_id,
    )

    [node] = client.get("/api/nodes").json()

    assert node["team"]["name"] == "Team Alpha"


def test_nodes_omit_the_team_of_a_tracker_on_another_incident(
    client: TestClient, database: Database, incident_id: str, node_id: str
) -> None:
    """A tracker out on someone else's callout is worth plotting, but it is not
    one of ours and must not be coloured as if it were."""
    other = database.incidents.create("Someone else's search")
    database.assignments.create(other.id, node_id, "their-team")
    database.positions.save(
        make_position(node_id, received_at=datetime.now(UTC)), incident_id=other.id
    )

    [node] = client.get("/api/nodes", params={"incident_id": incident_id}).json()

    assert node["node_id"] == node_id
    assert node["team"] is None


def test_nodes_exclude_a_node_not_heard_for_a_month(
    client: TestClient, database: Database, incident_id: str
) -> None:
    """Positions are never pruned, so without the bound a laptop reused across
    searches shows months of stale nodes standing still."""
    incident = database.incidents.get(incident_id)
    assert incident is not None
    database.positions.save(
        make_position(
            "!lastmonth", received_at=incident.started_at - timedelta(days=30)
        ),
        incident_id=None,
    )

    assert client.get("/api/nodes").json() == []


def test_nodes_include_one_heard_just_before_the_incident_opened(
    client: TestClient, database: Database, incident_id: str
) -> None:
    """A node beaconing while the operator was still naming the incident is
    exactly the one they are about to assign, and it may not beacon again for
    several minutes."""
    incident = database.incidents.get(incident_id)
    assert incident is not None
    database.positions.save(
        make_position(
            "!early", received_at=incident.started_at - timedelta(minutes=10)
        ),
        incident_id=None,
    )

    [node] = client.get("/api/nodes").json()

    assert node["node_id"] == "!early"


def test_nodes_show_only_the_newest_beacon_per_node(
    client: TestClient, database: Database, incident_id: str
) -> None:
    base = datetime.now(UTC)

    for step, latitude in enumerate((1.0, 2.0, 3.0)):
        database.positions.save(
            make_position(
                "!walker",
                latitude=latitude,
                received_at=base + timedelta(minutes=step),
            ),
            incident_id=None,
        )

    [node] = client.get("/api/nodes").json()

    assert node["position"]["latitude"] == 3.0

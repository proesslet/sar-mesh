"""/api/assignments

Every existence check here is load-bearing: an assignment naming an incident,
team or node that does not exist silently attributes positions to nothing, and
nothing downstream notices.
"""

from fastapi.testclient import TestClient

from sarmesh.storage.database import Database


def body(incident_id: str, node_id: str, team_id: str) -> dict[str, str]:
    return {
        "incident_id": incident_id,
        "tracker_node_id": node_id,
        "team_id": team_id,
    }


def test_create_returns_an_open_assignment(
    client: TestClient, incident_id: str, team_id: str, node_id: str
) -> None:
    response = client.post("/api/assignments", json=body(incident_id, node_id, team_id))

    assert response.status_code == 201
    assert response.json()["incident_id"] == incident_id
    assert response.json()["team_id"] == team_id
    assert response.json()["unassigned_at"] is None


def test_unknown_incident_is_404(
    client: TestClient, team_id: str, node_id: str
) -> None:
    response = client.post("/api/assignments", json=body("nope", node_id, team_id))

    assert response.status_code == 404
    assert "incident" in response.json()["detail"]


def test_unknown_tracker_is_404(
    client: TestClient, incident_id: str, team_id: str
) -> None:
    response = client.post("/api/assignments", json=body(incident_id, "!nope", team_id))

    assert response.status_code == 404
    assert "tracker" in response.json()["detail"]


def test_unknown_team_is_404(
    client: TestClient, incident_id: str, node_id: str
) -> None:
    response = client.post("/api/assignments", json=body(incident_id, node_id, "nope"))

    assert response.status_code == 404
    assert "team" in response.json()["detail"]


def test_a_rejected_assignment_is_not_recorded(
    client: TestClient, database: Database, team_id: str, node_id: str
) -> None:
    client.post("/api/assignments", json=body("nope", node_id, team_id))

    assert database.assignments.list_active() == []


def test_double_assignment_is_409(
    client: TestClient, incident_id: str, team_id: str, assigned_tracker: str
) -> None:
    """Two active assignments for one tracker make "which team is this?"
    ambiguous, and active_for would answer with whichever sorted first."""
    other = client.post("/api/teams", json={"name": "Team Bravo"}).json()["id"]

    response = client.post(
        "/api/assignments", json=body(incident_id, assigned_tracker, other)
    )

    assert response.status_code == 409
    assert "Team Alpha" in response.json()["detail"]


def test_a_tracker_cannot_be_assigned_to_two_incidents(
    client: TestClient, database: Database, team_id: str, assigned_tracker: str
) -> None:
    second = client.post("/api/incidents", json={"name": "Second"}).json()["id"]

    response = client.post(
        "/api/assignments", json=body(second, assigned_tracker, team_id)
    )

    assert response.status_code == 409
    assert len(database.assignments.list_active()) == 1


def test_delete_releases_the_tracker(
    client: TestClient, database: Database, assigned_tracker: str
) -> None:
    response = client.delete(f"/api/assignments/{assigned_tracker}")

    assert response.status_code == 200
    assert database.assignments.active_for(assigned_tracker) is None


def test_delete_returns_the_trackers_with_their_new_state(
    client: TestClient, assigned_tracker: str
) -> None:
    trackers = client.delete(f"/api/assignments/{assigned_tracker}").json()

    assert [tracker["assignment"] for tracker in trackers] == [None]


def test_delete_an_unassigned_tracker_is_404(client: TestClient, node_id: str) -> None:
    assert client.delete(f"/api/assignments/{node_id}").status_code == 404


def test_a_released_tracker_can_be_reassigned(
    client: TestClient, incident_id: str, team_id: str, assigned_tracker: str
) -> None:
    client.delete(f"/api/assignments/{assigned_tracker}")

    response = client.post(
        "/api/assignments", json=body(incident_id, assigned_tracker, team_id)
    )

    assert response.status_code == 201

"""/api/trackers"""

from conftest import make_position
from fastapi.testclient import TestClient

from sarmesh.storage.database import Database


def test_create_returns_an_unassigned_tracker(client: TestClient) -> None:
    response = client.post(
        "/api/trackers", json={"node_id": "!aabbccdd", "label": "Alpha 1"}
    )

    assert response.status_code == 201
    assert response.json() == {
        "node_id": "!aabbccdd",
        "label": "Alpha 1",
        "assignment": None,
    }


def test_duplicate_node_id_is_409(client: TestClient, node_id: str) -> None:
    """A raw sqlite3.IntegrityError traceback is not an operator-facing error."""
    response = client.post(
        "/api/trackers", json={"node_id": node_id, "label": "Alpha 2"}
    )

    assert response.status_code == 409


def test_list_names_the_holding_team_and_incident(
    client: TestClient, incident_id: str, team_id: str, assigned_tracker: str
) -> None:
    """Bare ids are what the operator would otherwise have to decode by hand."""
    [tracker] = client.get("/api/trackers").json()

    assert tracker["assignment"] == {
        "incident_id": incident_id,
        "incident_name": "Test Incident",
        "team_id": team_id,
        "team_name": "Team Alpha",
    }


def test_update_only_changes_the_label(client: TestClient, node_id: str) -> None:
    response = client.patch(f"/api/trackers/{node_id}", json={"label": "Bravo 1"})

    assert response.status_code == 200
    assert response.json()["label"] == "Bravo 1"
    assert response.json()["node_id"] == node_id


def test_update_carries_the_assignment_through(
    client: TestClient, assigned_tracker: str
) -> None:
    """Renaming does not release the tracker."""
    response = client.patch(
        f"/api/trackers/{assigned_tracker}", json={"label": "Bravo 1"}
    )

    assert response.json()["assignment"] is not None


def test_update_unknown_tracker_is_404(client: TestClient) -> None:
    assert client.patch("/api/trackers/nope", json={"label": "x"}).status_code == 404


def test_delete_returns_the_remaining_trackers(
    client: TestClient, node_id: str
) -> None:
    client.post("/api/trackers", json={"node_id": "!11223344", "label": "Alpha 2"})

    response = client.delete(f"/api/trackers/{node_id}")

    assert response.status_code == 200
    assert [tracker["node_id"] for tracker in response.json()] == ["!11223344"]


def test_delete_is_blocked_while_assigned(
    client: TestClient, assigned_tracker: str
) -> None:
    response = client.delete(f"/api/trackers/{assigned_tracker}")

    assert response.status_code == 409
    assert "Team Alpha" in response.json()["detail"]


def test_delete_keeps_recorded_positions(
    client: TestClient, database: Database, node_id: str
) -> None:
    """Positions belong to the incident that was run, not to the tracker
    record; an after-action review still needs them."""
    database.positions.save(make_position(node_id), incident_id="inc")

    client.delete(f"/api/trackers/{node_id}")

    assert database.positions.latest_for_node(node_id, "inc") is not None


def test_delete_unknown_tracker_is_404(client: TestClient) -> None:
    assert client.delete("/api/trackers/nope").status_code == 404


########################## Unregistered nodes ##########################


def test_unregistered_lists_nodes_with_no_tracker_record(
    client: TestClient, database: Database
) -> None:
    """Without this an operator has to know a node's hex id by heart."""
    database.positions.save(make_position("!deadbeef"), incident_id=None)

    response = client.get("/api/trackers/unregistered")

    assert response.status_code == 200
    assert [node["node_id"] for node in response.json()] == ["!deadbeef"]


def test_unregistered_excludes_registered_trackers(
    client: TestClient, database: Database, node_id: str
) -> None:
    database.positions.save(make_position(node_id), incident_id=None)

    assert client.get("/api/trackers/unregistered").json() == []


def test_unregistered_reports_the_last_time_the_node_was_heard(
    client: TestClient, database: Database
) -> None:
    database.positions.save(make_position("!deadbeef"), incident_id=None)

    [node] = client.get("/api/trackers/unregistered").json()

    assert node["last_seen_at"] == "2026-08-28T12:00:00Z"
    assert node["node_num"] == 0xAABBCCDD

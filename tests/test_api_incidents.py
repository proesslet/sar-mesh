"""/api/incidents"""

from fastapi.testclient import TestClient

from sarmesh.storage.database import Database


def test_create_returns_an_open_incident(client: TestClient) -> None:
    response = client.post("/api/incidents", json={"name": "Ridgeline"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Ridgeline"
    assert body["ended_at"] is None
    assert body["id"]


def test_create_rejects_a_missing_name(client: TestClient) -> None:
    assert client.post("/api/incidents", json={}).status_code == 422


def test_active_is_null_with_no_incidents(client: TestClient) -> None:
    response = client.get("/api/incidents/active")

    assert response.status_code == 200
    assert response.json() is None


def test_rename(client: TestClient, incident_id: str) -> None:
    response = client.patch(
        f"/api/incidents/{incident_id}", json={"name": "Ridgeline North"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Ridgeline North"


def test_rename_unknown_incident_is_404(client: TestClient) -> None:
    assert client.patch("/api/incidents/nope", json={"name": "x"}).status_code == 404


def test_end_closes_the_incident(client: TestClient, incident_id: str) -> None:
    response = client.post(f"/api/incidents/{incident_id}/end")

    assert response.status_code == 200
    assert response.json()["ended_at"] is not None
    assert client.get("/api/incidents/active").json() is None


def test_end_releases_every_assignment(
    client: TestClient, database: Database, incident_id: str, assigned_tracker: str
) -> None:
    """An assignment outliving its incident keeps stamping incoming positions
    with a closed search, and blocks the tracker from joining the next one."""
    client.post(f"/api/incidents/{incident_id}/end")

    assert database.assignments.active_for(assigned_tracker) is None
    assert database.assignments.list_active() == []


def test_end_does_not_touch_another_incident(
    client: TestClient, database: Database, team_id: str, node_id: str
) -> None:
    keep = client.post("/api/incidents", json={"name": "Keep"}).json()["id"]
    close = client.post("/api/incidents", json={"name": "Close"}).json()["id"]
    client.post(
        "/api/assignments",
        json={"incident_id": keep, "tracker_node_id": node_id, "team_id": team_id},
    )

    client.post(f"/api/incidents/{close}/end")

    active = database.assignments.active_for(node_id)
    assert active is not None
    assert active.incident_id == keep


def test_ending_twice_is_409(client: TestClient, incident_id: str) -> None:
    """Rewriting the end time of a closed incident destroys a record the
    operator relies on."""
    client.post(f"/api/incidents/{incident_id}/end")

    response = client.post(f"/api/incidents/{incident_id}/end")

    assert response.status_code == 409


def test_end_unknown_incident_is_404(client: TestClient) -> None:
    assert client.post("/api/incidents/nope/end").status_code == 404

"""/api/teams"""

from fastapi.testclient import TestClient


def test_create_returns_a_team_holding_nothing(client: TestClient) -> None:
    response = client.post(
        "/api/teams", json={"name": "Team Alpha", "personnel_count": 3}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Team Alpha"
    assert body["personnel_count"] == 3
    assert body["tracker_count"] == 0


def test_personnel_count_defaults_to_one(client: TestClient) -> None:
    response = client.post("/api/teams", json={"name": "Team Alpha"})

    assert response.json()["personnel_count"] == 1


def test_create_rejects_a_negative_personnel_count(client: TestClient) -> None:
    response = client.post(
        "/api/teams", json={"name": "Team Alpha", "personnel_count": -1}
    )

    assert response.status_code == 422


def test_tracker_count_reflects_active_assignments(
    client: TestClient, team_id: str, assigned_tracker: str
) -> None:
    teams = client.get("/api/teams").json()

    assert [team["tracker_count"] for team in teams if team["id"] == team_id] == [1]


def test_tracker_count_drops_when_the_tracker_is_released(
    client: TestClient, team_id: str, assigned_tracker: str
) -> None:
    client.delete(f"/api/assignments/{assigned_tracker}")

    teams = client.get("/api/teams").json()

    assert [team["tracker_count"] for team in teams if team["id"] == team_id] == [0]


def test_update_leaves_omitted_fields_alone(client: TestClient, team_id: str) -> None:
    response = client.patch(f"/api/teams/{team_id}", json={"name": "Team Bravo"})

    assert response.status_code == 200
    assert response.json()["name"] == "Team Bravo"
    assert response.json()["personnel_count"] == 3


def test_update_keeps_the_tracker_count(
    client: TestClient, team_id: str, assigned_tracker: str
) -> None:
    """A rename does not release anything, so the count cannot be assumed 0."""
    response = client.patch(f"/api/teams/{team_id}", json={"name": "Team Bravo"})

    assert response.json()["tracker_count"] == 1


def test_update_unknown_team_is_404(client: TestClient) -> None:
    assert client.patch("/api/teams/nope", json={"name": "x"}).status_code == 404


def test_delete_returns_the_remaining_teams(client: TestClient, team_id: str) -> None:
    """Not a 204: the caller must not be able to show a list that disagrees
    with the database."""
    client.post("/api/teams", json={"name": "Team Bravo"})

    response = client.delete(f"/api/teams/{team_id}")

    assert response.status_code == 200
    assert [team["name"] for team in response.json()] == ["Team Bravo"]


def test_delete_is_blocked_while_holding_a_tracker(
    client: TestClient, team_id: str, assigned_tracker: str
) -> None:
    """Deleting would leave the tracker's positions attributed to nobody."""
    response = client.delete(f"/api/teams/{team_id}")

    assert response.status_code == 409
    assert "Team Alpha" in response.json()["detail"]
    assert len(client.get("/api/teams").json()) == 1


def test_delete_is_allowed_once_the_tracker_is_released(
    client: TestClient, team_id: str, assigned_tracker: str
) -> None:
    client.delete(f"/api/assignments/{assigned_tracker}")

    assert client.delete(f"/api/teams/{team_id}").status_code == 200
    assert client.get("/api/teams").json() == []


def test_delete_unknown_team_is_404(client: TestClient) -> None:
    assert client.delete("/api/teams/nope").status_code == 404

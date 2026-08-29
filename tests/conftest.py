"""Fixtures shared by every test.

Each test gets its own SQLite file under tmp_path rather than an in-memory
database: the app opens one connection with check_same_thread=False and relies
on WAL, and ":memory:" behaves differently enough on both counts that a passing
test would not say much about the real thing.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sarmesh.core.events import PositionBroadcaster
from sarmesh.core.models import TrackerPosition
from sarmesh.storage.database import Database
from sarmesh.web.server import create_app


@pytest.fixture
def anyio_backend() -> str:
    """Run `@pytest.mark.anyio` tests on asyncio only, as the app does."""
    return "asyncio"


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "sarmesh.db"


@pytest.fixture
def database(database_path: Path) -> Iterator[Database]:
    db = Database(database_path)
    db.migrate()

    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def broadcaster() -> PositionBroadcaster:
    return PositionBroadcaster()


@pytest.fixture
def client(
    database: Database, broadcaster: PositionBroadcaster
) -> Iterator[TestClient]:
    """The API with no basemap library, which is a supported configuration."""
    app = create_app(database, broadcaster)

    # The context manager is what runs the lifespan, and the lifespan is what
    # binds the broadcaster to the serving loop.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def incident_id(client: TestClient) -> str:
    response = client.post("/api/incidents", json={"name": "Test Incident"})
    assert response.status_code == 201
    incident: str = response.json()["id"]
    return incident


@pytest.fixture
def team_id(client: TestClient) -> str:
    response = client.post(
        "/api/teams", json={"name": "Team Alpha", "personnel_count": 3}
    )
    assert response.status_code == 201
    team: str = response.json()["id"]
    return team


@pytest.fixture
def node_id(client: TestClient) -> str:
    response = client.post(
        "/api/trackers", json={"node_id": "!aabbccdd", "label": "Alpha 1"}
    )
    assert response.status_code == 201
    node: str = response.json()["node_id"]
    return node


@pytest.fixture
def assigned_tracker(
    client: TestClient, incident_id: str, team_id: str, node_id: str
) -> str:
    """A registered tracker, assigned to a team working an open incident."""
    response = client.post(
        "/api/assignments",
        json={
            "incident_id": incident_id,
            "tracker_node_id": node_id,
            "team_id": team_id,
        },
    )
    assert response.status_code == 201
    return node_id


def make_position(
    node_id: str = "!aabbccdd",
    *,
    node_num: int = 0xAABBCCDD,
    latitude: float = 44.4280,
    longitude: float = -110.5885,
    received_at: datetime | None = None,
    satellites: int | None = 9,
    precision_bits: int | None = 32,
    rssi: int | None = -95,
    snr: float | None = 5.25,
) -> TrackerPosition:
    """A position with plausible defaults, for tests that vary one field."""
    return TrackerPosition(
        node_id=node_id,
        node_num=node_num,
        latitude=latitude,
        longitude=longitude,
        received_at=received_at or datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
        satellites=satellites,
        precision_bits=precision_bits,
        rssi=rssi,
        snr=snr,
    )

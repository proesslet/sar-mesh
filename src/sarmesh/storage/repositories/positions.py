from sarmesh.core.models import TrackerPosition
from sarmesh.storage import mappers
from sarmesh.storage.repositories.base import Repository


class PositionRepository(Repository):
    def save(self, position: TrackerPosition, incident_id: str | None = None) -> None:
        """Record a beacon, stamped with the incident it belongs to.

        incident_id is None for a node that is not assigned to anything. The
        position is still kept, it just is not attributed to a search.
        """
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO positions (
                    incident_id, node_id, node_num, latitude, longitude,
                    received_at, satellites, precision_bits, rssi, snr
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident_id,
                    position.node_id,
                    position.node_num,
                    position.latitude,
                    position.longitude,
                    position.received_at.isoformat(),
                    position.satellites,
                    position.precision_bits,
                    position.rssi,
                    position.snr,
                ),
            )

    def latest_for_node(self, node_id: str, incident_id: str) -> TrackerPosition | None:
        """The most recent beacon from a node during one incident."""
        with self._transaction() as connection:
            row = connection.execute(
                """
                SELECT node_id, node_num, latitude, longitude, received_at,
                       satellites, precision_bits, rssi, snr
                FROM positions
                WHERE node_id = ? AND incident_id = ?
                ORDER BY received_at DESC LIMIT 1
                """,
                (node_id, incident_id),
            ).fetchone()

        return mappers.position(row) if row else None

    def latest_per_node(self) -> list[TrackerPosition]:
        """The most recent beacon from every node ever heard.

        Unfiltered by incident on purpose: this is what finds nodes with no
        tracker record yet, and an unregistered node is not assigned to
        anything. The id tiebreak matters because rxTime is whole seconds, so
        two beacons in the same second would otherwise both come back.
        """
        with self._transaction() as connection:
            rows = connection.execute(
                """
                SELECT node_id, node_num, latitude, longitude, received_at,
                       satellites, precision_bits, rssi, snr
                FROM positions p1
                WHERE received_at = (
                    SELECT MAX(received_at) FROM positions p2
                    WHERE p1.node_id = p2.node_id
                ) AND id = (
                    SELECT MAX(id) FROM positions p3
                    WHERE p1.node_id = p3.node_id AND p1.received_at = p3.received_at
                )
                """
            ).fetchall()

        return [mappers.position(row) for row in rows]

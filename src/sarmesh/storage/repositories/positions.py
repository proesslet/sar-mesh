from datetime import UTC, datetime

from sarmesh.core.models import TrackerPosition
from sarmesh.storage import mappers
from sarmesh.storage.repositories.base import Repository

# Fixes kept per node in one track. The map draws a trail, not a dataset: past
# a thousand points the polyline is denser than the screen it is drawn on, and
# the payload is the only thing still growing. The newest are kept, so what
# falls off is the oldest end of the trail rather than the last hour.
MAX_TRACK_POINTS = 1000

# received_at is stored as ISO-8601 text and compared lexically, so the empty
# string is a lower bound below every stored value. That keeps "no lower bound"
# from needing a second version of the query.
NO_LOWER_BOUND = ""


def _lower_bound(since: datetime | None) -> str:
    """`since` as a string that sorts correctly against stored timestamps.

    Normalised to UTC first: the same instant written with a +02:00 offset
    sorts after one written as +00:00, so comparing the raw isoformat would
    silently drop fixes near the boundary.
    """
    if since is None:
        return NO_LOWER_BOUND

    return since.astimezone(UTC).isoformat()


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

    def latest_per_node(self, since: datetime | None = None) -> list[TrackerPosition]:
        """The most recent beacon from every node ever heard.

        Unfiltered by incident on purpose: this is what finds nodes with no
        tracker record yet, and an unregistered node is not assigned to
        anything. The id tiebreak matters because rxTime is whole seconds, so
        two beacons in the same second would otherwise both come back.

        `since` drops nodes whose newest beacon is older than it. The bound is
        on the winning row rather than inside the subqueries, so it means "not
        heard since" rather than "heard before, then quiet".
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
                ) AND received_at >= ?
                """,
                (_lower_bound(since),),
            ).fetchall()

        return [mappers.position(row) for row in rows]

    def history_for_incident(
        self,
        incident_id: str,
        since: datetime | None = None,
        limit_per_node: int = MAX_TRACK_POINTS,
    ) -> dict[str, list[TrackerPosition]]:
        """Every beacon recorded against one incident, grouped by node.

        Each node's fixes come back oldest first, which is the order a trail is
        drawn in. Capped per node rather than across the whole answer, so one
        chatty radio cannot crowd the rest of the search out of it.

        One statement rather than a query per tracker: this is still a
        single-table read, and a loop would take the shared connection lock
        once for every node on the search.
        """
        with self._transaction() as connection:
            rows = connection.execute(
                """
                SELECT node_id, node_num, latitude, longitude, received_at,
                       satellites, precision_bits, rssi, snr
                FROM (
                    SELECT *, ROW_NUMBER() OVER (
                        PARTITION BY node_id ORDER BY received_at DESC, id DESC
                    ) AS recency
                    FROM positions
                    WHERE incident_id = ? AND received_at >= ?
                )
                WHERE recency <= ?
                ORDER BY node_id, received_at, id
                """,
                (incident_id, _lower_bound(since), limit_per_node),
            ).fetchall()

        tracks: dict[str, list[TrackerPosition]] = {}

        for row in rows:
            tracks.setdefault(row["node_id"], []).append(mappers.position(row))

        return tracks

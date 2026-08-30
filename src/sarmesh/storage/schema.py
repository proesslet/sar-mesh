"""Schema migrations, indexed by SQLite's user_version.

Entries are appended only, never reordered, removed or edited once released.
Each is a tuple of statements rather than one script, because executescript
commits before it runs and would break the atomicity of applying a migration
and stamping its version together.
"""

MIGRATIONS: tuple[tuple[str, ...], ...] = (
    (  # 1: the initial schema
        """
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT,
            node_id TEXT NOT NULL,
            node_num INTEGER NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            received_at TEXT NOT NULL,
            satellites INTEGER,
            precision_bits INTEGER,
            rssi INTEGER,
            snr REAL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT
        )""",
        """
        CREATE TABLE IF NOT EXISTS trackers (
            node_id TEXT PRIMARY KEY,
            label TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS teams (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            personnel_count INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS tracker_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            tracker_node_id TEXT NOT NULL,
            team_id TEXT NOT NULL,
            assigned_at TEXT NOT NULL,
            unassigned_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """,
    ),
    (  # 2: indexes on the tables read on every request
        """
        CREATE INDEX IF NOT EXISTS ix_positions_node_received
        ON positions (node_id, received_at DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_assignments_active
        ON tracker_assignments (tracker_node_id, unassigned_at)
        """,
    ),
    (  # 3: the index a track query reads
        # Migration 2's index leads on node_id, so a query selecting a whole
        # incident's history cannot seek with it and scans the table instead.
        # This one leads on incident_id and carries the ordering with it.
        """
        CREATE INDEX IF NOT EXISTS ix_positions_incident_node_received
        ON positions (incident_id, node_id, received_at)
        """,
    ),
)

import sqlite3
from pathlib import Path

from sarmesh.core.models import TrackerPosition


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                """
            )

    def save_position(self, position: TrackerPosition) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO positions (
                    node_id,
                    node_num,
                    latitude,
                    longitude,
                    received_at,
                    satellites,
                    precision_bits,
                    rssi,
                    snr
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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
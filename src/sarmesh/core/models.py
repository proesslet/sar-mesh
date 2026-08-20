from dataclasses import dataclass
from datetime import datetime

@dataclass
class TrackerPosition:
    node_id: str
    node_num: int
    latitude: float
    longitude: float
    received_at: datetime

    satellites: int | None = None
    precision_bits: int | None = None
    rssi: int | None = None
    snr: float | None = None
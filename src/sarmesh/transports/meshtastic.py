import time
from datetime import UTC, datetime

import meshtastic.serial_interface
from pubsub import pub

from sarmesh.core.models import TrackerPosition


class MeshtasticTransport:
    def __init__(self, on_position) -> None:
        self.on_position = on_position
        self.interface = None

    def start(self) -> None:
        pub.subscribe(
            self._on_position,
            "meshtastic.receive.position",
        )

        print("Connecting to Meshtastic node...")

        self.interface = meshtastic.serial_interface.SerialInterface()

        print("Connected.")

    def run(self) -> None:
        self.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.stop()

    def stop(self) -> None:
        if self.interface is not None:
            self.interface.close()

    def _on_position(self, packet, interface) -> None:
        position = packet["decoded"]["position"]

        tracker_position = TrackerPosition(
            node_id=packet["fromId"],
            node_num=packet["from"],
            latitude=position["latitude"],
            longitude=position["longitude"],
            received_at=datetime.fromtimestamp(
                packet["rxTime"],
                tz=UTC,
            ),
            satellites=position.get("satsInView"),
            precision_bits=position.get("precisionBits"),
            rssi=packet.get("rxRssi"),
            snr=packet.get("rxSnr"),
        )

        self.on_position(tracker_position)

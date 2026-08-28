import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import meshtastic.serial_interface
import meshtastic.tcp_interface
from meshtastic.mesh_interface import MeshInterface
from pubsub import pub

from sarmesh.core.models import TrackerPosition

PositionHandler = Callable[[TrackerPosition], None]

logger = logging.getLogger(__name__)

Packet = dict[str, Any]

POSITION_TOPIC = "meshtastic.receive.position"


class MeshtasticTransport:
    def __init__(
        self,
        on_position: PositionHandler,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        self.on_position = on_position
        self.host = host
        self.port = port
        self.interface: MeshInterface | None = None
        logger.info("Initializing Meshtastic transport...")

    def start(self) -> None:
        logger.info("Starting Meshtastic transport...")

        pub.subscribe(
            self._on_position,
            POSITION_TOPIC,
        )

        if self.host is not None:
            interface = self._connect_tcp()
        else:
            interface = self._connect_serial()

        self.interface = interface

        logger.info("Connected to Meshtastic node: %s", interface.myInfo)

    def _connect_serial(self) -> MeshInterface:
        logger.info("Connecting to Meshtastic node over USB serial...")

        interface = meshtastic.serial_interface.SerialInterface()

        # With no serial device attached, SerialInterface.__init__ prints a
        # message about falling back to TCP and returns early without ever
        # calling StreamInterface.__init__ -- it does not actually make that
        # TCP connection; the library's own CLI does it separately. The object
        # it hands back has no reader thread and silently receives nothing, so
        # refuse it rather than reporting a connection we do not have.
        #
        # StreamInterface.__init__ always sets `stream` (to None for TCP), so
        # its total absence is what marks a half-constructed interface.
        if not hasattr(interface, "stream"):
            raise ConnectionError(
                "No Meshtastic serial device detected. Connect a node over "
                "USB, or pass --host to reach one over the network."
            )

        return interface

    def _connect_tcp(self) -> MeshInterface:
        port = self.port or meshtastic.tcp_interface.DEFAULT_TCP_PORT

        logger.info("Connecting to Meshtastic node at %s:%s...", self.host, port)

        try:
            return meshtastic.tcp_interface.TCPInterface(
                hostname=self.host,
                portNumber=port,
            )
        except OSError as error:
            logger.error(
                "Could not reach Meshtastic node at %s:%s: %s", self.host, port, error
            )
            raise ConnectionError(
                f"Could not reach Meshtastic node at {self.host}:{port}: {error}"
            ) from error

    def run(self) -> None:
        self.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\nShutting down...")
        finally:
            self.stop()

    def stop(self) -> None:
        pub.unsubscribe(
            self._on_position,
            POSITION_TOPIC,
        )
        logger.info("Stopping Meshtastic transport...")

        if self.interface is None:
            return

        # A half-constructed SerialInterface has no stream attribute and its
        # close() raises AttributeError, which would mask the real failure
        # behind a traceback during shutdown.
        if not hasattr(self.interface, "stream"):
            return

        self.interface.close()

    def _on_position(self, packet: Packet, interface: MeshInterface) -> None:
        position = (packet.get("decoded") or {}).get("position") or {}

        node_id = packet.get("fromId")
        node_num = packet.get("from")
        latitude = position.get("latitude")
        longitude = position.get("longitude")

        # A node without a GPS fix still beacons POSITION_APP carrying only a
        # timestamp, and locally-generated packets can omit fromId. Drop those
        # quietly rather than raising out of the pubsub callback.
        if node_id is None or node_num is None:
            return

        if latitude is None or longitude is None:
            return

        tracker_position = TrackerPosition(
            node_id=node_id,
            node_num=node_num,
            latitude=latitude,
            longitude=longitude,
            received_at=self._received_at(packet),
            satellites=position.get("satsInView"),
            precision_bits=position.get("precisionBits"),
            rssi=packet.get("rxRssi"),
            snr=packet.get("rxSnr"),
        )

        self.on_position(tracker_position)

    @staticmethod
    def _received_at(packet: Packet) -> datetime:
        # rxTime is the receiving node's clock, which reads 0 until the node
        # syncs time; fall back to local time instead of recording 1970.
        rx_time = packet.get("rxTime")

        if not rx_time:
            return datetime.now(UTC)

        return datetime.fromtimestamp(rx_time, tz=UTC)

import logging
import time
from datetime import UTC, datetime
from typing import Any

import meshtastic.serial_interface
import meshtastic.tcp_interface
from meshtastic.mesh_interface import MeshInterface
from meshtastic.protobuf import config_pb2, mesh_pb2
from pubsub import pub

from sarmesh.core.models import RadioInfo, TrackerPosition
from sarmesh.transports import PositionHandler

logger = logging.getLogger(__name__)

Packet = dict[str, Any]

POSITION_TOPIC = "meshtastic.receive.position"


class RadioUnavailable(RuntimeError):
    """Asked something of the node while no node was connected."""


def _enum_name(enum: Any, value: int) -> str:
    """A protobuf enum's label, falling back to the raw number.

    Firmware newer than the bundled protobufs reports values this library has
    no name for, and Name() raises on those. A number an operator can look up
    beats a 500.
    """
    try:
        name: str = enum.Name(value)
    except ValueError:
        return str(value)

    return name


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

        # pubsub holds listeners weakly, so positions keep arriving only while
        # something else holds a reference to this transport. Drop it and the
        # stream stops silently, with no error anywhere.
        pub.subscribe(self._on_position, POSITION_TOPIC)

        if self.host is not None:
            interface = self._connect_tcp()
        else:
            interface = self._connect_serial()

        self.interface = interface

        logger.info("Connected to Meshtastic node: %s", interface.myInfo)
        logger.info(interface.getShortName())

    def _connect_serial(self) -> MeshInterface:
        logger.info("Connecting to Meshtastic node over USB serial...")

        interface = meshtastic.serial_interface.SerialInterface()

        # With no serial device attached, SerialInterface.__init__ prints a
        # message about falling back to TCP and returns early without ever
        # calling StreamInterface.__init__. It does not actually make that
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

    def node_info(self) -> RadioInfo:
        """What the attached node says about itself.

        Everything here is served out of the config the library downloaded
        during start(), so this neither blocks nor puts anything on the air.
        """
        interface = self.interface

        if interface is None:
            raise RadioUnavailable("No Meshtastic node is connected")

        user = interface.getMyUser() or {}
        metadata = interface.metadata
        my_info = interface.myInfo

        return RadioInfo(
            node_id=user.get("id"),
            node_num=my_info.my_node_num if my_info is not None else None,
            long_name=user.get("longName"),
            short_name=user.get("shortName"),
            hardware=(
                _enum_name(mesh_pb2.HardwareModel, metadata.hw_model)
                if metadata is not None
                else None
            ),
            firmware_version=metadata.firmware_version if metadata is not None else None,
            role=(
                _enum_name(config_pb2.Config.DeviceConfig.Role, metadata.role)
                if metadata is not None
                else None
            ),
            # The reader thread adds to this dict as nodes are heard. len() on a
            # dict being mutated is safe; iterating it would not be.
            node_count=len(interface.nodes or {}),
        )

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

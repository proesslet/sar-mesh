"""Decoding a Meshtastic position packet.

Only the parsing half is covered: everything above it needs a real radio.
`_on_position` is called directly rather than through pubsub, since what
matters is which packets produce a TrackerPosition and which are dropped.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from sarmesh.core.models import TrackerPosition
from sarmesh.transports.meshtastic import MeshtasticTransport


def packet(**position: Any) -> dict[str, Any]:
    """A well-formed position packet, with the position fields overridable."""
    return {
        "fromId": "!aabbccdd",
        "from": 0xAABBCCDD,
        "rxRssi": -95,
        "rxSnr": 5.25,
        "rxTime": 1787918400,  # 2026-08-28T12:00:00Z
        "decoded": {
            "position": {
                "latitude": 44.4280,
                "longitude": -110.5885,
                "satsInView": 9,
                "precisionBits": 32,
                **position,
            }
        },
    }


@pytest.fixture
def received() -> list[TrackerPosition]:
    return []


@pytest.fixture
def transport(received: list[TrackerPosition]) -> MeshtasticTransport:
    # Never started, so nothing touches a serial port or pubsub.
    return MeshtasticTransport(on_position=received.append)


def test_a_full_packet_is_decoded(
    transport: MeshtasticTransport, received: list[TrackerPosition]
) -> None:
    transport._on_position(packet(), interface=None)  # type: ignore[arg-type]

    assert received == [
        TrackerPosition(
            node_id="!aabbccdd",
            node_num=0xAABBCCDD,
            latitude=44.4280,
            longitude=-110.5885,
            received_at=datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
            satellites=9,
            precision_bits=32,
            rssi=-95,
            snr=5.25,
        )
    ]


def test_optional_signal_fields_may_be_absent(
    transport: MeshtasticTransport, received: list[TrackerPosition]
) -> None:
    raw = packet()
    del raw["rxRssi"]
    del raw["rxSnr"]
    raw["decoded"]["position"].pop("satsInView")
    raw["decoded"]["position"].pop("precisionBits")

    transport._on_position(raw, interface=None)  # type: ignore[arg-type]

    assert len(received) == 1
    assert received[0].rssi is None
    assert received[0].snr is None
    assert received[0].satellites is None
    assert received[0].precision_bits is None


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda raw: raw.pop("fromId"), id="no fromId"),
        pytest.param(lambda raw: raw.pop("from"), id="no from"),
        pytest.param(
            lambda raw: raw["decoded"]["position"].pop("latitude"), id="no latitude"
        ),
        pytest.param(
            lambda raw: raw["decoded"]["position"].pop("longitude"), id="no longitude"
        ),
        pytest.param(lambda raw: raw.update(decoded={}), id="no position"),
        pytest.param(lambda raw: raw.update(decoded=None), id="decoded is None"),
        pytest.param(
            lambda raw: raw.update(decoded={"position": None}), id="position is None"
        ),
        pytest.param(lambda raw: raw.clear(), id="empty packet"),
    ],
)
def test_incomplete_packets_are_dropped(
    transport: MeshtasticTransport,
    received: list[TrackerPosition],
    mutate: Any,
) -> None:
    """A node without a fix still beacons POSITION_APP. Raising out of the
    pubsub callback would take the reader thread down with it."""
    raw = packet()
    mutate(raw)

    transport._on_position(raw, interface=None)  # type: ignore[arg-type]

    assert received == []


def test_zero_rx_time_falls_back_to_now(
    transport: MeshtasticTransport, received: list[TrackerPosition]
) -> None:
    """An unsynced node reports rxTime 0; recording 1970 would sort it to the
    bottom of every query and show the tracker as permanently stale."""
    before = datetime.now(UTC)

    transport._on_position(packet() | {"rxTime": 0}, interface=None)  # type: ignore[arg-type]

    assert len(received) == 1
    assert before <= received[0].received_at <= datetime.now(UTC)


def test_missing_rx_time_falls_back_to_now(
    transport: MeshtasticTransport, received: list[TrackerPosition]
) -> None:
    raw = packet()
    del raw["rxTime"]
    before = datetime.now(UTC)

    transport._on_position(raw, interface=None)  # type: ignore[arg-type]

    assert len(received) == 1
    assert before <= received[0].received_at <= datetime.now(UTC)


def test_rx_time_is_interpreted_as_utc(
    transport: MeshtasticTransport, received: list[TrackerPosition]
) -> None:
    """A naive local-time datetime here silently shifts every timestamp by the
    operator's offset, which is invisible until an after-action review."""
    transport._on_position(packet(), interface=None)  # type: ignore[arg-type]

    assert received[0].received_at.tzinfo is not None
    assert received[0].received_at.utcoffset() == datetime.now(UTC).utcoffset()

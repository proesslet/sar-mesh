#!/usr/bin/env python
"""Run SARMesh against a simulated mesh instead of a radio.

Development tool. It launches the ordinary app -- same server, same UI, same
database -- with the Meshtastic transport swapped for a generator that walks
imaginary trackers around a map and feeds their positions through the real
ingest path. Everything downstream is unchanged, so what the map draws is what
it would draw for real nodes.

    uv run python scripts/simulate_incident.py --seed

Create an incident, add teams and trackers, and assign them in the UI as usual.
Assigned trackers start beaconing within one interval; unassigning one stops it.
`--seed` skips that by creating a demo incident, teams and trackers up front.

Writes to sarmesh-sim.db in the working directory, not the real database. Pass
`--db sarmesh.db` to drive the real one instead.
"""

import argparse
import logging
import math
import random
import sys
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# Importable from a source checkout without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sarmesh.app import DesktopApp
from sarmesh.core.models import TrackerPosition
from sarmesh.storage.database import Database
from sarmesh.transports import PositionHandler

logger = logging.getLogger("simulate")

# Old Faithful. Somewhere with terrain, and far from anywhere a stray beacon
# would be mistaken for a real one.
DEFAULT_CENTRE = (44.4280, -110.5885)

METRES_PER_DEGREE = 111_320.0

# What the demo data looks like: one team per pattern, so every movement style
# is on the map at once.
DEMO_TEAMS = (
    ("Team Alpha", 3, "grid"),
    ("Team Bravo", 2, "wander"),
    ("Team Charlie", 4, "spiral"),
    ("Command", 2, "static"),
)

PATTERNS = ("grid", "wander", "spiral", "static")


########################## Geometry ##########################


def offset(
    latitude: float, longitude: float, bearing: float, metres: float
) -> tuple[float, float]:
    """Move a point `metres` along `bearing` radians, 0 being north.

    Flat-earth approximation. Over the few kilometres a search covers the error
    is centimetres, and a proper geodesic would not change a single pixel.
    """
    delta_lat = metres * math.cos(bearing) / METRES_PER_DEGREE
    delta_lon = (
        metres
        * math.sin(bearing)
        / (METRES_PER_DEGREE * math.cos(math.radians(latitude)))
    )

    return latitude + delta_lat, longitude + delta_lon


def distance(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> float:
    """Metres between two nearby points."""
    mean_latitude = math.radians((from_lat + to_lat) / 2)

    return math.hypot(
        (to_lat - from_lat) * METRES_PER_DEGREE,
        (to_lon - from_lon) * METRES_PER_DEGREE * math.cos(mean_latitude),
    )


def node_num_of(node_id: str) -> int:
    """The integer a Meshtastic node id encodes.

    Real ids are "!" plus eight hex digits. A tracker added by hand may not be,
    so anything else falls back to a stable hash of the string.
    """
    try:
        return int(node_id.lstrip("!"), 16)
    except ValueError:
        return abs(hash(node_id)) % 0xFFFFFFFF


########################## Movement ##########################


@dataclass
class Walker:
    """One imaginary tracker, and where it is going next."""

    node_id: str
    label: str
    pattern: str
    latitude: float
    longitude: float
    speed: float
    random: random.Random

    bearing: float = 0.0
    # Metres left on the current leg, for the patterns that walk legs.
    leg_remaining: float = 0.0
    leg_length: float = 120.0
    legs_walked: int = 0
    # Ticks left in a signal blackout. Non-zero means the node is behind
    # terrain and nothing it sends is heard.
    silent_ticks: int = 0
    history: list[tuple[float, float]] = field(default_factory=list)

    def step(self, seconds: float) -> None:
        """Advance by one beacon interval."""
        if self.pattern == "static":
            # A command post still drifts a few metres: GPS noise is what makes
            # a stationary marker look alive rather than frozen.
            self.latitude, self.longitude = offset(
                self.latitude,
                self.longitude,
                self.random.uniform(0, math.tau),
                self.random.uniform(0, 3),
            )
            return

        metres = self.speed * seconds

        if self.pattern == "wander":
            # A drunkard's walk with momentum: heading nudges rather than
            # jumping, so the track reads as someone picking a line.
            self.bearing += self.random.gauss(0, 0.35)
        else:
            self._advance_leg(metres)

        self.latitude, self.longitude = offset(
            self.latitude, self.longitude, self.bearing, metres
        )

    def _advance_leg(self, metres: float) -> None:
        """Turn at the end of a leg, for the patterns that walk a shape."""
        if self.leg_remaining > 0:
            self.leg_remaining -= metres
            return

        self.legs_walked += 1

        if self.pattern == "spiral":
            # An expanding square: turn 90 degrees every leg, and lengthen
            # every second one.
            self.bearing += math.pi / 2
            self.leg_remaining = self.leg_length * (1 + self.legs_walked // 2)
            return

        # A grid search: long legs up and back, joined by a short cross leg.
        if self.legs_walked % 2:
            self.bearing += math.pi / 2
            self.leg_remaining = 40.0
        else:
            self.bearing += math.pi / 2
            self.leg_remaining = self.leg_length


class SimulatedMesh:
    """A transport that invents positions instead of listening to a radio.

    Trackers are discovered from the database on every tick rather than fixed
    at startup, so assigning one in the UI starts it moving and unassigning it
    stops it, with no restart.
    """

    def __init__(
        self,
        on_position: PositionHandler,
        *,
        database_path: Path,
        centre: tuple[float, float],
        interval: float,
        speed: float,
        spread: float,
        loss: float,
        dropouts: bool,
        ghosts: int,
        seed: int | None,
    ) -> None:
        self.on_position = on_position
        self.database_path = database_path
        self.centre = centre
        self.interval = interval
        self.speed = speed
        self.spread = spread
        self.loss = loss
        self.dropouts = dropouts
        self.ghosts = ghosts

        self.random = random.Random(seed)
        self.walkers: dict[str, Walker] = {}

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # Its own connection: the simulator stands outside the app, the way a
        # radio does, and only ever reads.
        self._database: Database | None = None

    ########################## Transport protocol ##########################

    def start(self) -> None:
        self._database = Database(self.database_path)
        self._thread = threading.Thread(target=self._run, daemon=True, name="sim")
        self._thread.start()

        logger.info(
            "Simulating a mesh around %.5f, %.5f every %.0fs",
            *self.centre,
            self.interval,
        )

    def stop(self) -> None:
        self._stop.set()

        if self._thread is not None:
            self._thread.join(timeout=self.interval + 1)

        if self._database is not None:
            self._database.close()

    ########################## The loop ##########################

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                # A simulator that dies silently looks exactly like a mesh with
                # nothing on it, which is the most confusing failure available.
                logger.exception("Simulation tick failed")

            self._stop.wait(self.interval)

    def _tick(self) -> None:
        for walker in self._current_walkers():
            walker.step(self.interval)

            if self._is_heard(walker):
                self.on_position(self._beacon(walker))

    def _current_walkers(self) -> list[Walker]:
        """The trackers assigned to the open incident, plus any ghosts.

        Re-read every tick: an operator assigning a tracker in the UI expects
        it to appear, and a restart to see it would defeat the point.
        """
        assert self._database is not None

        incident = self._database.incidents.active()
        assigned: list[tuple[str, str]] = []

        if incident is not None:
            for assignment in self._database.assignments.active_for_incident(
                incident.id
            ):
                tracker = self._database.trackers.get(assignment.tracker_node_id)

                if tracker is not None:
                    assigned.append((tracker.node_id, tracker.label))

        # Nodes heard on the mesh with no tracker record, so the UI's
        # "unregistered nodes" list has something in it.
        assigned += [
            (f"!9000000{index}", f"Unknown node {index + 1}")
            for index in range(self.ghosts)
        ]

        live = {node_id for node_id, _ in assigned}

        # A tracker released mid-run stops beaconing, and is forgotten so that
        # reassigning it later starts from a fresh position rather than
        # teleporting back to where it was dropped.
        for gone in set(self.walkers) - live:
            del self.walkers[gone]
            logger.info("%s stopped beaconing", gone)

        for node_id, label in assigned:
            if node_id not in self.walkers:
                self.walkers[node_id] = self._spawn(node_id, label)
                logger.info("%s (%s) started beaconing", label, node_id)

        return list(self.walkers.values())

    def _spawn(self, node_id: str, label: str) -> Walker:
        """Place a newly assigned tracker, resuming where it was last seen."""
        latitude, longitude = self._starting_point(node_id)

        return Walker(
            node_id=node_id,
            label=label,
            pattern=self._pattern_for(label),
            latitude=latitude,
            longitude=longitude,
            speed=self.speed * self.random.uniform(0.7, 1.3),
            random=random.Random(self.random.random()),
            bearing=self.random.uniform(0, math.tau),
            leg_length=self.random.uniform(80, 200),
        )

    def _starting_point(self, node_id: str) -> tuple[float, float]:
        assert self._database is not None

        incident = self._database.incidents.active()

        if incident is not None:
            last = self._database.positions.latest_for_node(node_id, incident.id)

            # Continuing from the last known fix keeps a restarted simulation
            # from jumping every team back to the staging area.
            if last is not None:
                return last.latitude, last.longitude

        return offset(
            *self.centre,
            self.random.uniform(0, math.tau),
            self.random.uniform(0, self.spread),
        )

    def _pattern_for(self, label: str) -> str:
        """Match the demo teams' patterns, and vary anything else.

        Seeded trackers are labelled "Alpha 1" after team "Team Alpha", so both
        spellings have to match for a hand-made tracker to land on the pattern
        its team was given.
        """
        for name, _, pattern in DEMO_TEAMS:
            if label.startswith((name, name.split()[-1])):
                return pattern

        return self.random.choice(PATTERNS)

    def _is_heard(self, walker: Walker) -> bool:
        """Whether this beacon makes it back to the base node.

        Both failure modes are worth having. A dropped packet is the normal
        case and should barely show; a blackout is what makes a tracker go
        stale on the map, which is the thing hardest to test for real.
        """
        if walker.silent_ticks > 0:
            walker.silent_ticks -= 1
            return False

        if self.dropouts and self.random.random() < 0.01:
            walker.silent_ticks = self.random.randint(4, 12)
            logger.info(
                "%s lost behind terrain for %d beacons",
                walker.label,
                walker.silent_ticks,
            )
            return False

        return self.random.random() >= self.loss

    def _beacon(self, walker: Walker) -> TrackerPosition:
        metres = distance(*self.centre, walker.latitude, walker.longitude)

        # A rough LoRa link budget: strong at the staging area, marginal a few
        # kilometres out. Enough for the UI to have something plausible to show.
        rssi = -60 - 20 * math.log10(max(metres, 10) / 10)
        snr = 12 - 15 * math.log10(max(metres, 50) / 50)

        logger.info(
            "%-14s %s  %.5f, %.5f  %ddBm",
            walker.label,
            walker.node_id,
            walker.latitude,
            walker.longitude,
            round(rssi),
        )

        return TrackerPosition(
            node_id=walker.node_id,
            node_num=node_num_of(walker.node_id),
            latitude=round(walker.latitude, 6),
            longitude=round(walker.longitude, 6),
            received_at=datetime.now(UTC),
            satellites=self.random.randint(4, 12),
            precision_bits=32,
            rssi=max(-125, min(-30, round(rssi + self.random.gauss(0, 4)))),
            snr=round(max(-20.0, min(12.0, snr + self.random.gauss(0, 1.5))), 2),
        )


########################## Demo data ##########################


def seed_demo_incident(database: Database, trackers_per_team: int) -> None:
    """Create an incident with teams and assigned trackers, if none is open.

    Skipped when an incident is already running, so re-running the simulator
    against the same database does not pile up duplicates.
    """
    if database.incidents.active() is not None:
        logger.info("An incident is already open; not seeding demo data")
        return

    incident = database.incidents.create("Simulated Incident")
    logger.info("Created incident %s", incident.name)

    node_number = 0

    for team_name, personnel, _ in DEMO_TEAMS:
        team = database.teams.create(team_name, personnel_count=personnel)

        for index in range(trackers_per_team):
            node_number += 1
            node_id = f"!51000{node_number:03x}"
            # "Team Alpha" -> "Alpha 1", which is what a radio call sounds like.
            label = f"{team_name.split()[-1]} {index + 1}"

            if database.trackers.get(node_id) is None:
                database.trackers.create(node_id, label)

            database.assignments.create(incident.id, node_id, team.id)

        logger.info("Created %s with %d trackers", team.name, trackers_per_team)


########################## Entry point ##########################


def parse_centre(value: str) -> tuple[float, float]:
    try:
        latitude, longitude = (float(part) for part in value.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("--centre takes LAT,LON") from None

    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise argparse.ArgumentTypeError("--centre is out of range")

    return latitude, longitude


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=Path("sarmesh-sim.db"),
        help="Database to run against (default: sarmesh-sim.db, not the real one)",
    )
    parser.add_argument(
        "--centre",
        "--center",
        type=parse_centre,
        default=DEFAULT_CENTRE,
        metavar="LAT,LON",
        help="Where the search is happening (default: %(default)s)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=10.0,
        help="Seconds between beacons (default: %(default)s)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.1,
        help="Metres per second on foot, before per-tracker variation "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--spread",
        type=float,
        default=400.0,
        help="Metres to scatter trackers around the centre (default: %(default)s)",
    )
    parser.add_argument(
        "--loss",
        type=float,
        default=0.08,
        help="Fraction of beacons dropped in transit (default: %(default)s)",
    )
    parser.add_argument(
        "--no-dropouts",
        dest="dropouts",
        action="store_false",
        help="Do not take trackers off the air for minutes at a time",
    )
    parser.add_argument(
        "--ghosts",
        type=int,
        default=0,
        help="Unregistered nodes to beacon, for the unregistered-nodes list "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Create a demo incident with teams and assigned trackers",
    )
    parser.add_argument(
        "--trackers-per-team",
        type=int,
        default=2,
        help="Trackers per team when seeding (default: %(default)s)",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=None,
        help="Fix the random seed so a run is reproducible",
    )
    parser.add_argument(
        "--basemap",
        type=Path,
        default=None,
        help="MBTiles file to serve as the offline basemap",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=None,
        help="Port for the local UI server",
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Serve only and print the URL; do not open a native window",
    )

    args = parser.parse_args(argv)

    if not 0 <= args.loss < 1:
        parser.error("--loss must be between 0 and 1")

    if args.interval <= 0:
        parser.error("--interval must be positive")

    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.seed:
        database = Database(args.db)
        database.migrate()

        try:
            seed_demo_incident(database, args.trackers_per_team)
        finally:
            database.close()

    def build(on_position: PositionHandler) -> SimulatedMesh:
        return SimulatedMesh(
            on_position,
            database_path=args.db,
            centre=args.centre,
            interval=args.interval,
            speed=args.speed,
            spread=args.spread,
            loss=args.loss,
            dropouts=args.dropouts,
            ghosts=args.ghosts,
            seed=args.random_seed,
        )

    app = DesktopApp(
        database_path=args.db,
        port=args.http_port,
        basemap=args.basemap,
        transport_factory=build,
    )

    logger.info("Simulating against %s", args.db)

    try:
        app.run(window=not args.browser)
    except ConnectionError as error:
        logger.error("%s", error)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

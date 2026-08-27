# SARMesh

Offline search and rescue personnel tracking over mesh radio networks.

SARMesh listens to a [Meshtastic](https://meshtastic.org/) mesh, records position
beacons from field trackers, and attributes them to the teams working an incident.
It runs entirely off-grid - no internet, no cloud, no cell coverage required. State
lives in a single local SQLite file.

> **Status: early development.** The ingest pipeline and data model work end to end.
> Reporting, live status output, and a map view are not built yet.

## How it works

A tracker is any Meshtastic node carried by field personnel. Nodes broadcast
position packets over LoRa; a node connected by USB to the machine running SARMesh
acts as the receiver.

```
field trackers  ──LoRa──>  base node  ──USB──>  SARMesh  ──>  sarmesh.db
```

Each incoming position is stamped with the incident the tracker is currently
assigned to, so a single mesh can serve consecutive operations without the logs
running together.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A Meshtastic device connected over USB serial, plus one or more tracker nodes
  on the same channel

## Install

```bash
uv sync
```

## Usage

All commands write to `sarmesh.db` in the current working directory, creating it on
first use.

### 1. Open an incident

```bash
uv run sarmesh incident create "Bear Creek Search"
# Created incident 6f2a... : Bear Creek Search
```

Note the incident ID — assignments are made against it.

### 2. Register teams

```bash
uv run sarmesh team create "Alpha" --personnel 4
uv run sarmesh team create "Bravo" -p 2
```

### 3. Register trackers

The node ID is the Meshtastic identifier, including the leading `!`.

```bash
uv run sarmesh tracker add '!f0b50c58' "Alpha Lead"
```

### 4. Assign trackers to teams

```bash
uv run sarmesh tracker assign '!f0b50c58' <team-id> <incident-id>
```

### 5. Start recording

```bash
uv run sarmesh run
```

Connects to the Meshtastic node attached over USB and logs every position it
hears until `Ctrl-C`. To reach a node over the network instead:

```bash
uv run sarmesh run --host 192.168.1.50     # --port defaults to 4403
```

If no node can be reached, `run` exits with an error rather than starting.
Note that the `meshtastic` library prints "No Serial Meshtastic device
detected, attempting TCP connection on localhost" when probing finds no serial
port — despite the wording it does **not** attempt that connection, so use
`--host` explicitly.

## Data model

| Entity              | Purpose                                                             |
| ------------------- | ------------------------------------------------------------------- |
| `Incident`          | A single operation, with start and optional end time                |
| `Team`              | A named field team and its personnel count                          |
| `Tracker`           | A Meshtastic node identified by `node_id`, with a human label       |
| `TrackerAssignment` | Binds a tracker to a team for an incident, for a time window        |
| `TrackerPosition`   | One received beacon: lat/lon, timestamp, sats, precision, RSSI, SNR |
| `TrackerStatus`     | Derived view — a tracker with its team, latest position, last seen  |

Assignments are historical: a tracker is unassigned by stamping `unassigned_at`
rather than deleting the row, so an incident's attribution can be reconstructed
after the fact.

## Layout

```
src/sarmesh/
├── cli.py                  Typer CLI — incident / team / tracker / run
├── core/
│   ├── models.py           Dataclasses for every entity
│   └── registry.py         In-memory latest-position cache
├── services/
│   └── tracking.py         Ingest: resolve assignment, persist position
├── storage/
│   └── database.py         SQLite persistence layer
└── transports/
    └── meshtastic.py       Serial + pubsub listener, packet -> TrackerPosition
```

The transport layer is deliberately thin and depends only on `core.models`, so a
second transport (TCP, BLE, replay from a capture) can be added without touching
the services or storage layers.

## Development

```bash
uv run ruff check .      # lint
uv run ruff format .     # format
uv run mypy src          # type check
uv run pytest            # tests
```

`research/rawposition.txt` holds a captured POSITION_APP packet, useful as a
reference for the fields the transport parses.

## Roadmap

- [ ] Status and reporting commands (`incident status`, position history export)
- [ ] Validation on assignment (unknown IDs currently accepted silently)
- [ ] Configurable database path
- [ ] Stale-tracker alerting when a node stops beaconing
- [ ] Map / GPX export for incident debriefs

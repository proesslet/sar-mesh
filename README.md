# SARMesh

Offline search and rescue personnel tracking over mesh radio networks.

SARMesh listens to a [Meshtastic](https://meshtastic.org/) mesh, records position
beacons from field trackers, and attributes them to the teams working an incident.
It runs entirely off-grid - no internet, no cloud, no cell coverage required. State
lives in a single local SQLite file.

> **Status: early development.** The ingest pipeline and data model work end to end.
> Reporting, live status output, and a map view are not built yet.

## The app

SARMesh is a native desktop app: a Python backend and a React map UI rendered
in a Qt window via PySide6's QtWebEngine. Qt bundles its own rendering engine,
so there is no dependency on a system browser or on distro packages like
WebKitGTK — installing the app is all an operator has to do.

The same server also answers on the local network, so a second device can view
the incident in a browser without a separate build.

```bash
uv run sarmesh app                              # native window, USB radio
uv run sarmesh app --basemap terrain.mbtiles    # with an offline basemap
uv run sarmesh app --host 192.168.1.50          # radio over the network
uv run sarmesh app --offline                    # stored data only, no radio
uv run sarmesh app --browser                    # serve only; no native window
```

`--browser` is for headless boxes and for viewing from another device; the
native window is the intended way to run it.

If no radio is reachable the UI still starts — an operator can read the last
known positions and manage teams without one.

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

PySide6 ships prebuilt wheels for Linux (x86_64 and arm64), Windows and macOS,
so there is nothing to compile. On a Raspberry Pi this needs **Pi OS Trixie or
newer** — the arm64 wheels require glibc 2.39 and Bookworm ships 2.36.

## Install

```bash
uv sync
```

## Usage

Run from a source checkout, all commands write to `sarmesh.db` in the current
working directory, creating it on first use.

The packaged app cannot do that — it is launched by double-clicking, so its
working directory is whatever the OS hands it. A packaged build stores the
database in the per-user data directory instead:

| Platform | Location |
| --- | --- |
| Linux | `$XDG_DATA_HOME/sarmesh/sarmesh.db` (default `~/.local/share/sarmesh/`) |
| macOS | `~/Library/Application Support/SARMesh/sarmesh.db` |
| Windows | `%LOCALAPPDATA%\SARMesh\sarmesh.db` |

Set `SARMESH_DB` to override either default — pointing a build at an incident
database on removable media, for instance. Every command reads it, so the CLI
and the app always agree on which database they are working with.

```bash
SARMESH_DB=/media/usb/bear-creek.db uv run sarmesh app
```

### Logs

`sarmesh.log` sits next to the database in the user data directory, and is
where to look when a packaged app does not start. It is written from a source
checkout too, so the file is always in the same place.

The packaged app is built windowed: on Windows it has no console at all, and a
double-clicked macOS `.app` has none worth reading. Nothing it prints is
visible, so anything fatal is written to the log and shown in a dialog that
names the log's location.

The command line tools are intended for a source checkout or an installed
wheel, where output can actually be read. The bundle accepts the same
arguments, but only `sarmesh app`'s flags are useful without a console.

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

### Frontend

The UI lives in [`frontend/`](frontend/) (React + TypeScript + Vite, with
Leaflet for the map). Node is a **build-time** dependency only — nothing
Node-related ships to a Pi or to an end user's machine, which just receive the
compiled static files.

```bash
cd frontend
npm install
npm run dev      # Vite dev server, proxies /api and /events to :8000
npm run build    # compiles into src/sarmesh/web/static/
```

Run `uv run sarmesh app --browser --http-port 8000` alongside `npm run dev` to
get hot reload against a live backend. Ask for the port explicitly here: the
Vite proxy is hardcoded to `:8000`, and without `--http-port` the app quietly
moves to a free port if 8000 is taken — which the proxy cannot follow.
`npm run build` must be run before building a wheel, since the compiled UI is
what gets packaged.

## Packaging

```bash
uv run python scripts/build_desktop.py
```

Builds the frontend, then bundles Python, Qt and the UI into `dist/sarmesh/`.
The result runs on a machine with no Python, no uv and no Node installed;
`dist/sarmesh/sarmesh` is the executable.

Expect roughly 580 MB. Most of it is `libQt6WebEngineCore` (~194 MB), which is
Chromium — the same reason an Electron app is large, and the cost of depending
on no system browser. The spec prunes what a single-purpose offline app never
reads: non-English locales, Qt translations, devtools resources, and QML.

### Building for other platforms

PyInstaller bundles the host's real interpreter and native libraries, so it
cannot cross-compile — but that does not mean you need three machines.

**CI (preferred).** [`.github/workflows/build.yml`](.github/workflows/build.yml)
runs one native job per target and uploads all three as artifacts. Push a tag
and collect the builds. Native arm64 runners are free for public repositories;
private repos need a paid plan, in which case use the local route below.

**Locally, for the Pi.** `scripts/build_pi.sh` builds the arm64 bundle on an
x86_64 machine using Docker with QEMU emulation. The frontend is compiled
natively first since JavaScript is architecture-independent, so only
PyInstaller runs emulated. Slow — tens of minutes — but needs no Pi.

**Windows** must be built on Windows, either via the CI job or a VM.

Note the Pi target needs **Pi OS Trixie or newer**: PySide6's arm64 wheels
require glibc 2.39 and Bookworm ships 2.36. That is why the build container is
based on Debian Trixie (glibc 2.41).

`research/rawposition.txt` holds a captured POSITION_APP packet, useful as a
reference for the fields the transport parses.

## Roadmap

- [ ] Manage teams, trackers and assignments from the UI (API exists; forms do not)
- [ ] Validation on assignment (unknown IDs currently accepted silently)
- [ ] Track history — draw a team's route, not just its latest position
- [ ] Stale-tracker alerting when a node stops beaconing
- [ ] Configurable database path
- [ ] PyInstaller packaging for Windows
- [ ] GPX export for incident debriefs

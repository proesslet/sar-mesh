# SARMesh

[![License: GPL-3.0](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Build](https://github.com/proesslet/sar-mesh/actions/workflows/build.yml/badge.svg)](https://github.com/proesslet/sar-mesh/actions/workflows/build.yml)

**Offline search and rescue personnel tracking over mesh radio networks.**

SARMesh listens to a [Meshtastic](https://meshtastic.org/) mesh, records position
beacons from field trackers, and plots them against the teams working an
incident. It runs entirely off-grid: no internet, no cloud, no cell coverage.
Everything lives in a single local SQLite file.

A tracker is any Meshtastic node carried by field personnel. Nodes broadcast
position packets over LoRa, and a node connected by USB to the machine running
SARMesh acts as the receiver.

```
field trackers  ──LoRa──>  base node  ──USB──>  SARMesh  ──>  sarmesh.db
```

Each position is stamped with the incident its tracker is assigned to, so one
mesh can serve consecutive operations without the logs running together.

> **Status: early development.** The ingest pipeline, map UI, incident/team/
> tracker management and offline basemaps all work end to end. Trackers that
> stop beaconing are shown as stale, but nothing alerts on it yet, and track
> history and GPX export are not built.

> **This is a situational awareness aid, not a life-safety system.** Positions
> arrive over a lossy radio mesh and can be minutes stale or missing entirely.
> Do not use SARMesh as the only means of tracking personnel in the field.

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- A Meshtastic device on USB serial, plus one or more tracker nodes on the same
  channel

PySide6 ships prebuilt wheels for Linux (x86_64 and arm64), Windows and macOS,
so there is nothing to compile. On a Raspberry Pi you need **Pi OS Trixie or
newer**, because the arm64 wheels want glibc 2.39 and Bookworm ships 2.36.

## Quick start

```bash
uv sync
uv run sarmesh app
```

That opens the desktop app: a Python backend serving a React map UI inside a Qt
window. Qt bundles its own rendering engine, so there is no dependency on a
system browser or on distro packages like WebKitGTK.

```bash
uv run sarmesh app --basemap terrain.mbtiles   # with an offline basemap
uv run sarmesh app --host 192.168.1.50         # reach the radio over the network
uv run sarmesh app --offline                   # stored data only, no radio
uv run sarmesh app --browser                   # serve only, no native window
```

If no radio is reachable the UI still starts, so an operator can read the last
known positions and manage teams without one. The server also answers on the
local network, so a second device can view the incident in a browser.

Create an incident, add teams and trackers, and assign trackers from the UI.
The same operations are available from the command line: see
[docs/operations.md](docs/operations.md).

## Where your data lives

Run from a source checkout, everything writes to `sarmesh.db` in the working
directory. A packaged build is launched by double-clicking and cannot rely on
that, so it uses the per-user data directory:

| Platform | Location |
| --- | --- |
| Linux | `$XDG_DATA_HOME/sarmesh/` (default `~/.local/share/sarmesh/`) |
| macOS | `~/Library/Application Support/SARMesh/` |
| Windows | `%LOCALAPPDATA%\SARMesh\` |

Set `SARMESH_DB` to override both, which is how you point a build at an incident
database on removable media. Every command reads it, so the CLI and the app
always agree on which database they are using.

## Documentation

| | |
| --- | --- |
| [Operations](docs/operations.md) | Running an incident, the CLI, logs, offline basemaps |
| [Architecture](docs/architecture.md) | Data model, layout, how the layers fit together |
| [Development](docs/development.md) | Dev setup, the check commands, working on the frontend |
| [Packaging](docs/packaging.md) | Building the desktop bundle for each platform |

## Contributing

Contributions are welcome. Start with [docs/development.md](docs/development.md)
for the dev loop, and [docs/architecture.md](docs/architecture.md) for where
code belongs.

## License

Copyright (C) 2026 Preston Roesslet

SARMesh is free software under the [GNU General Public License v3.0](LICENSE),
version 3 only. It links the `meshtastic` library, which is GPL-3.0-only, so
the combined work cannot be offered under a later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the license for details.

## Acknowledgements

Built on [Meshtastic](https://meshtastic.org/), whose LoRa mesh firmware and
Python library do the hard part. Maps are rendered with
[Leaflet](https://leafletjs.com/); offline basemaps use the
[MBTiles](https://github.com/mapbox/mbtiles-spec) format.

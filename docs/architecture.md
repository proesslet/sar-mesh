# Architecture

## The shape of it

SARMesh is one process doing three things at once:

- **uvicorn** serves the HTTP API and the compiled React UI on localhost.
- **A Meshtastic reader thread** receives position packets and writes them to
  SQLite.
- **A Qt window** hosts the UI over that local HTTP server, rather than over
  `file://`, so the API, the position stream and the tile endpoint all share one
  origin. The same build is therefore viewable from another device on the
  network with no second code path.

The window must own the main thread, because macOS and GTK both require their UI
loop to run there. The server and the radio go to background threads.

Live positions reach the browser over Server-Sent Events. The radio thread hands
each position to a broadcaster, which fans it out to subscribers on the asyncio
loop via `call_soon_threadsafe`, because `asyncio.Queue` is not thread safe.

## Data model

| Entity | Purpose |
| --- | --- |
| `Incident` | A single operation, with a start and an optional end time |
| `Team` | A named field team and its personnel count |
| `Tracker` | A Meshtastic node, identified by `node_id`, with a human label |
| `TrackerAssignment` | Binds a tracker to a team for an incident, over a time window |
| `TrackerPosition` | One received beacon: lat/lon, timestamp, sats, precision, RSSI, SNR |
| `TrackerStatus` | Derived view: a tracker with its team, latest position and last-seen time |
| `Track` | Derived view: one tracker's positions for an incident, oldest first |

Assignments are historical. Releasing a tracker stamps `unassigned_at` rather
than deleting the row, so an incident's attribution can be reconstructed
afterwards.

Positions are append-only and never pruned, so a tracker's whole path is
already on disk. `/api/status` reads the latest one per tracker and `/api/tracks`
reads the run of them, capped per node so one fast radio cannot crowd out the
rest of the search. `/api/nodes` is the wider view: every node heard on the mesh
around the incident, including ones no team is carrying, which is what an
operator needs in order to spot a tracker that still wants assigning.

Only one incident is active at a time: the newest un-ended one. Ending an
incident releases its assignments, otherwise the closed incident would keep
claiming incoming positions and its trackers could not join the next search.

## Layout

```
src/sarmesh/
├── app.py              DesktopApp: binds the port, starts the server, radio and window
├── cli.py              Typer CLI
├── desktop.py          The Qt window, and the fatal-error dialog
├── diagnostics.py      Logging setup for a process with no console
├── core/
│   ├── models.py       Dataclasses for every entity
│   └── events.py       PositionBroadcaster: radio thread to SSE clients
├── services/
│   ├── tracking.py     Ingest: resolve the assignment, persist, broadcast
│   └── basemaps.py     Tile maths, URL policy, the background downloader
├── storage/
│   ├── database.py     The connection, its lock, and schema migration
│   ├── schema.py       Ordered migrations, indexed by SQLite's user_version
│   ├── mappers.py      sqlite3.Row to domain model
│   ├── paths.py        Where the database, log and basemaps live
│   └── repositories/   One module per entity, single-table SQL
├── transports/
│   └── meshtastic.py   Serial and TCP listener, packet to TrackerPosition
└── web/
    ├── server.py       create_app: wiring, lifespan, static mount
    ├── dependencies.py Depends providers reading off app.state
    ├── schemas.py      Request and response models
    ├── views.py        Read models built from several queries
    ├── tiles.py        MBTiles reader and the pack library
    └── routes/         One module per resource
```

## Where code belongs

This is the question most likely to send a newcomer to the wrong file, so:

**`routes/`** validates HTTP input, enforces the rules that produce a 404 or a
409, and returns a response model. No SQL. A new endpoint goes here and gets
registered in the `ROUTERS` tuple in `server.py`.

**`web/views.py`** builds the shapes the UI asks for that no single row
provides: a tracker with its assignment named, a team with its tracker count, a
tracker's live status. If your read needs more than one repository, it belongs
here rather than in a route or a repository.

**`storage/repositories/`** owns SQL, one module per entity, single-table
queries only. Reached as `database.teams.list()`, `database.incidents.get(...)`.
Every query goes through `Database.transaction()`, which serialises on a shared
lock because the radio thread and the HTTP thread use one connection.

**`services/`** holds behaviour that is not tied to HTTP: ingesting a position,
running a tile download. Anything the CLI and the API both need.

**`core/`** depends on nothing above it. `transports/` depends only on
`core.models`, which is what lets a second transport (BLE, or replay from a
capture) be added without touching storage or the web layer.

One inconsistency worth knowing: the guard rules ("a team holding trackers
cannot be deleted", "an incident cannot be ended twice") currently live in the
route handlers rather than in `services/`. That is the convention for now
because each rule has exactly one caller.

## Storage notes

SQLite runs in WAL mode. The radio thread writes while the HTTP thread reads,
and under the default rollback journal a write blocks every reader.
`synchronous=NORMAL` is durable across a process crash and only risks the last
commits to a power cut, which is the right trade on an SD card when the next
beacon is seconds away.

Schema changes are migrations in `storage/schema.py`, applied in order and
stamped into SQLite's `user_version`. Entries are appended only, never
reordered or edited once released. `CREATE TABLE IF NOT EXISTS` on its own would
silently do nothing to a database that already has data in it.

Opening a database that reports a higher `user_version` than the build knows
about is a hard error rather than a best-effort read.

## Frontend

The UI is React + TypeScript + Vite, with Leaflet for the map. It talks to the
same HTTP API as everything else and holds no state the server does not.

Node is a build-time dependency only. `npm run build` compiles into
`src/sarmesh/web/static/`, and that directory is what ships in the wheel and the
desktop bundle. Nothing Node-related reaches a Pi or an end user's machine.

Offline basemaps are served from `/tiles/{z}/{x}/{y}`, backed by whichever
MBTiles pack is active. MBTiles stores rows in TMS order counted from the
bottom, while Leaflet asks for XYZ tiles counted from the top, so the tile
reader flips the row. A revision counter changes on every pack swap, because
tile URLs are otherwise identical between packs and the browser would keep
serving the old pack's tiles from cache.

`research/rawposition.txt` holds a captured POSITION_APP packet, useful as a
reference for the fields the transport parses.

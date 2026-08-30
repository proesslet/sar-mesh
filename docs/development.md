# Development

## Setup

```bash
uv sync
```

That is the whole backend setup. See [architecture.md](architecture.md) for
where code belongs before adding anything.

## Checks

Run these before opening a pull request:

```bash
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy src            # type check
uv run pytest              # tests
```

`mypy` runs with `disallow_untyped_defs`, so every new function needs
annotations.

## Running without a radio

Most work does not need hardware:

```bash
uv run sarmesh app --offline
```

The UI starts, serves stored data, and skips the Meshtastic connection
entirely.

For moving trackers rather than stored ones, the simulator swaps the transport
for walkers that feed the real ingest path, so what the map draws is what it
would draw for real nodes:

```bash
uv run python scripts/simulate_incident.py --seed --browser --http-port 8000
```

`--seed` creates a demo incident, four teams and their trackers up front;
without it, assign trackers in the UI and they start beaconing within one
interval. It writes to `sarmesh-sim.db`, not the real database. `--interval`
and `--speed` control how fast history accumulates, `--ghosts` adds
unregistered nodes, and the default 8% packet loss plus terrain blackouts are
what exercise gaps in a track.

To exercise the ingest path one position at a time, write straight through the
service:

```python
from datetime import UTC, datetime
from sarmesh.core.models import TrackerPosition
from sarmesh.services.tracking import TrackingService
from sarmesh.storage.database import Database

database = Database(Path("sarmesh.db"))
database.migrate()

TrackingService(database=database).handle_position(
    TrackerPosition(
        node_id="!f0b50c58",
        node_num=4038496344,
        latitude=39.1,
        longitude=-106.2,
        received_at=datetime.now(UTC),
    )
)
```

`research/rawposition.txt` holds a real captured packet if you need the exact
field shapes the transport parses.

## Frontend

```bash
cd frontend
npm install
npm run dev      # Vite dev server, proxies /api, /events and /tiles to :8000
npm run build    # compiles into src/sarmesh/web/static/
npm run lint
```

For hot reload against a live backend, run the app alongside it:

```bash
uv run sarmesh app --browser --http-port 8000
```

Ask for the port explicitly. The Vite proxy is hardcoded to `:8000`, and without
`--http-port` the app quietly moves to a free port if 8000 is taken, which the
proxy cannot follow.

`npm run build` must run before building a wheel or a desktop bundle, since the
compiled UI is what gets packaged.

## Database changes

Schema changes are migrations, never edits to an existing one. Append a tuple of
statements to `MIGRATIONS` in `src/sarmesh/storage/schema.py`; it is applied in
order and stamped into SQLite's `user_version` on next start.

Migrations that have been released are frozen. Reordering or editing one leaves
existing databases at a version that no longer means what the code thinks.

## Adding an endpoint

1. Request and response models go in `src/sarmesh/web/schemas.py`.
2. The handler goes in the matching module under `src/sarmesh/web/routes/`, or a
   new one registered in the `ROUTERS` tuple in `server.py`.
3. Queries go in `src/sarmesh/storage/repositories/`, one module per entity.
4. If the response needs more than one repository, compose it in
   `src/sarmesh/web/views.py`.

Handlers take their collaborators as dependencies (`database: Db`), which come
from `app.state` via `src/sarmesh/web/dependencies.py`. Nothing needs to be
threaded through a closure.

## Conventions

- Prefer the standard library. This ships to field laptops and Raspberry Pis.
- Match the surrounding style rather than introducing a new one.
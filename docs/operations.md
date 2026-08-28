# Operations

Running an incident with SARMesh, from either the UI or the command line.

## The desktop app

```bash
uv run sarmesh app                              # native window, USB radio
uv run sarmesh app --basemap terrain.mbtiles    # with an offline basemap
uv run sarmesh app --host 192.168.1.50          # radio over the network
uv run sarmesh app --port 4403                  # TCP port for --host
uv run sarmesh app --http-port 8000             # pin the UI server's port
uv run sarmesh app --offline                    # stored data only, no radio
uv run sarmesh app --browser                    # serve only, no native window
```

`--browser` is for headless boxes and for viewing from another device. The
native window is the intended way to run it.

Without `--http-port` the app prefers port 8000 and quietly moves to a free one
if it is taken. Pin it when something else needs to find the server.

## Running an incident from the UI

1. **Start an incident.** Only one can be active at a time; the newest un-ended
   one wins. Positions are recorded against it.
2. **Add teams** under *Teams*, with a personnel count.
3. **Add trackers** under *Trackers*. Nodes already heard on the mesh appear in
   the unregistered list, so you do not have to type a hex node id from memory.
4. **Assign trackers to teams.** A tracker can only be held by one team at a
   time; moving it is an unassign followed by an assign.
5. **End the incident** under *Settings* when the search is over. This releases
   every assignment, so the trackers are free for the next incident.

A team holding trackers cannot be deleted, and neither can an assigned tracker.
Unassign first. This is deliberate: their positions would otherwise stop being
attributed to anyone mid-search.

Deleting a tracker leaves its recorded positions in place. They belong to the
incident that was being run, not to the tracker record, and an after-action
review still needs them.

## The command line

The CLI is meant for a source checkout or an installed wheel, where output can
actually be read. The packaged bundle accepts the same arguments, but it is
built windowed and has no console, so only `sarmesh app`'s flags are useful
there.

### Open an incident

```bash
uv run sarmesh incident create "Bear Creek Search"
# Created incident 6f2a...79: Bear Creek Search
```

Note the incident id. Assignments are made against it.

### Register teams

```bash
uv run sarmesh team create "Alpha" --personnel 4
uv run sarmesh team create "Bravo" -p 2
```

### Register trackers

The node id is the Meshtastic identifier, including the leading `!`.

```bash
uv run sarmesh tracker add '!f0b50c58' "Alpha Lead"
```

### Assign trackers to teams

```bash
uv run sarmesh tracker assign '!f0b50c58' <team-id> <incident-id>
```

> The CLI does not yet check that the ids exist. A typo produces an assignment
> pointing at nothing, which is invisible until you wonder why a tracker never
> appears. The HTTP API does validate, so the UI is the safer route.

### Record positions headlessly

```bash
uv run sarmesh run                          # USB serial
uv run sarmesh run --host 192.168.1.50      # --port defaults to 4403
```

Logs every position it hears until `Ctrl-C`. If no node can be reached it exits
with an error rather than starting.

The `meshtastic` library prints "No Serial Meshtastic device detected,
attempting TCP connection on localhost" when probing finds no serial port.
Despite the wording it does **not** attempt that connection, so pass `--host`
explicitly.

## Offline basemaps

Positions plot correctly with no basemap at all, but terrain makes them useful.
SARMesh serves raster tiles from [MBTiles](https://github.com/mapbox/mbtiles-spec)
packs.

Under *Settings → Basemaps* you can import a pack you already have, or draw a
box on the map and download one. Downloads are capped at 200,000 tiles, and the
estimate tells you the count before you commit. Zoom depth is exponential, so
the difference between a sensible request and an impossible one is two clicks.

The tile server is yours to supply. No source can be assumed to permit bulk
downloading on a search team's behalf, and OpenStreetMap's tile policy
prohibits it outright, so SARMesh refuses to bulk download from hosts known to
forbid it. Viewing them online is fine and is the default.

An imported pack is remembered across restarts. Packs live beside the database
in the user data directory, or wherever `SARMESH_BASEMAP_DIR` points.

## Where data lives

| Platform | Directory |
| --- | --- |
| Linux | `$XDG_DATA_HOME/sarmesh/` (default `~/.local/share/sarmesh/`) |
| macOS | `~/Library/Application Support/SARMesh/` |
| Windows | `%LOCALAPPDATA%\SARMesh\` |

Run from a source checkout, the database is `sarmesh.db` in the working
directory instead. `SARMESH_DB` overrides both:

```bash
SARMESH_DB=/media/usb/bear-creek.db uv run sarmesh app
```

`SARMESH_BASEMAP_DIR` does the same for basemap packs, which is how a
deployment keeps gigabytes of tiles on removable media without moving the
database too.

## Logs

`sarmesh.log` sits in the user data directory, always, including from a source
checkout. It is where to look when a packaged app does not start.

The packaged app is built windowed: on Windows it has no console at all, and a
double-clicked macOS `.app` has none worth reading. Nothing it prints is
visible, so anything fatal is written to the log and shown in a dialog naming
the log's location. The log rotates at 1 MB and keeps three backups.

*Settings → Diagnostics* shows the tail of the log and the paths of everything
SARMesh has written, for an operator with no terminal.

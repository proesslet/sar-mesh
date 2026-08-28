import { useCallback, useEffect, useMemo, useState } from "react";
import "./App.css";
import { api } from "./api";
import type {
  Area,
  Basemap,
  Incident,
  OnlineSource,
  TrackerStatus,
} from "./api";
import { MapView } from "./MapView";
import type { TrackerMarker } from "./MapView";
import { NewIncidentModal } from "./NewIncidentModal";
import { SettingsModal } from "./SettingsModal";
import { TeamsModal } from "./TeamsModal";
import { TrackersModal } from "./TrackersModal";
import { useLivePositions } from "./useLivePositions";

// A tracker that has not beaconed in this long is shown as stale. Meshtastic
// nodes typically beacon every few minutes, so this is several missed cycles
// rather than a single dropped packet.
const STALE_AFTER_MS = 10 * 60 * 1000;

function age(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h`;
}

export default function App() {
  const [statuses, setStatuses] = useState<TrackerStatus[]>([]);
  const [incident, setIncident] = useState<Incident | null>(null);
  const [basemap, setBasemap] = useState<Basemap | null>(null);
  const [online, setOnline] = useState<OnlineSource | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [newIncidentOpen, setNewIncidentOpen] = useState(false);
  const [trackersOpen, setTrackersOpen] = useState(false);
  const [teamsOpen, setTeamsOpen] = useState(false);
  // The area to download tiles over. Drawing it means handing the map back to
  // the operator, so settings closes for the duration and reopens with the
  // result -- the modal would otherwise cover the thing being drawn on.
  const [drawing, setDrawing] = useState(false);
  const [area, setArea] = useState<Area | null>(null);
  const { positions, connection } = useLivePositions();

  // Re-render on a timer so the "last seen" ages count up even while the mesh
  // is quiet; without this a stalled tracker would look fresh indefinitely.
  const [, setTick] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setTick((t) => t + 1), 10_000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    Promise.all([
      api.status(),
      api.activeIncident(),
      api.basemap(),
      api.basemaps(),
    ])
      .then(([s, i, b, library]) => {
        setStatuses(s);
        setIncident(i);
        setBasemap(b);
        setOnline(library.online);
      })
      .catch((e) => setError(String(e)));
  }, []);

  // Settings can change either of these underneath us, so both are refetched
  // rather than patched from the response: the server decides what is active.
  const refreshBasemap = useCallback(() => {
    Promise.all([api.basemap(), api.basemaps()])
      .then(([b, library]) => {
        setBasemap(b);
        setOnline(library.online);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const startDrawing = useCallback(() => {
    setSettingsOpen(false);
    setDrawing(true);
  }, []);

  const finishDrawing = useCallback((drawn: Area) => {
    setArea(drawn);
    setDrawing(false);
    setSettingsOpen(true);
  }, []);

  const refreshIncident = useCallback(() => {
    Promise.all([api.activeIncident(), api.status()])
      .then(([i, s]) => {
        setIncident(i);
        setStatuses(s);
      })
      .catch((e) => setError(String(e)));
  }, []);

  // Live SSE positions win over the snapshot loaded at startup.
  const markers = useMemo<TrackerMarker[]>(() => {
    return statuses
      .map((status) => {
        const position = positions[status.tracker.node_id] ?? status.position;
        if (!position) return null;

        return {
          nodeId: status.tracker.node_id,
          label: status.tracker.label,
          team: status.team?.name ?? null,
          position,
          stale:
            Date.now() - new Date(position.received_at).getTime() >
            STALE_AFTER_MS,
        };
      })
      .filter((m): m is TrackerMarker => m !== null);
  }, [statuses, positions]);

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>SARMesh</h1>
          <span className="incident">
            {incident ? incident.name : "No active incident"}
          </span>
        </div>

        <div className="header-actions">
          {/* Always available: trackers are kit, and kit is added and retired
              between searches as much as during one. */}
          <button type="button" onClick={() => setTrackersOpen(true)}>
            Trackers
          </button>

          <button type="button" onClick={() => setTeamsOpen(true)}>
            Teams
          </button>

          {/* Only one incident can be active -- the newest un-ended one wins --
              so this is offered only when there is none. Ending the current one
              is a deliberate act, done under Settings. */}
          {incident === null && (
            <button type="button" onClick={() => setNewIncidentOpen(true)}>
              Start new incident
            </button>
          )}

          <span className={`connection ${connection}`}>
            {connection === "live"
              ? "Receiving"
              : connection === "connecting"
                ? "Connecting"
                : "Signal lost"}
          </span>
        </div>
      </header>

      <main className="body">
        <aside className="panel">
          <div className="panel-scroll">
            <h2>
              Trackers <span className="count">{markers.length}</span>
            </h2>

            {error && <p className="error">{error}</p>}

            {!error && markers.length === 0 && (
              <p className="empty">
                No tracker positions yet. Assign a tracker to a team for the
                active incident, then wait for its next beacon.
              </p>
            )}

            <ul className="trackers">
              {markers.map((marker) => (
                <li key={marker.nodeId} className={marker.stale ? "stale" : ""}>
                  <div className="tracker-row">
                    <span className="label">{marker.label}</span>
                    <span className="age">
                      {age(marker.position.received_at)}
                    </span>
                  </div>
                  <div className="meta">
                    {marker.team ?? "Unassigned"}
                    {marker.position.satellites != null &&
                      ` · ${marker.position.satellites} sats`}
                  </div>
                </li>
              ))}
            </ul>

            {basemap && !basemap.available && (
              <p className="note">
                No offline basemap loaded. Positions still plot correctly; add
                one under Settings to get terrain.
              </p>
            )}
          </div>

          <button
            type="button"
            className="settings-button"
            onClick={() => setSettingsOpen(true)}
          >
            Settings
          </button>
        </aside>

        <MapView
          markers={markers}
          basemap={basemap}
          online={online}
          drawing={drawing}
          area={area}
          onAreaDrawn={finishDrawing}
        />

        {drawing && (
          <div className="draw-hint">
            Drag a box over the area to download.
            <button
              type="button"
              className="link"
              onClick={() => {
                setDrawing(false);
                setSettingsOpen(true);
              }}
            >
              Cancel
            </button>
          </div>
        )}
      </main>

      <TrackersModal
        open={trackersOpen}
        incident={incident}
        onClose={() => setTrackersOpen(false)}
        onChanged={refreshIncident}
      />

      <TeamsModal
        open={teamsOpen}
        onClose={() => setTeamsOpen(false)}
        onChanged={refreshIncident}
      />

      <NewIncidentModal
        open={newIncidentOpen}
        onClose={() => setNewIncidentOpen(false)}
        onCreated={refreshIncident}
      />

      <SettingsModal
        open={settingsOpen}
        incident={incident}
        area={area}
        onClose={() => setSettingsOpen(false)}
        onBasemapChange={refreshBasemap}
        onIncidentChange={refreshIncident}
        onSelectArea={startDrawing}
      />
    </div>
  );
}

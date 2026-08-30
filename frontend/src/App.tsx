import { useCallback, useMemo, useState } from "react";
import type { Area } from "./api";
import { Header } from "./components/Header";
import { Button, Message } from "./components/ui";
import { NewIncidentModal } from "./features/incidents/NewIncidentModal";
import { SettingsModal } from "./features/settings/SettingsModal";
import { TeamsModal } from "./features/teams/TeamsModal";
import { TrackerList } from "./features/trackers/TrackerList";
import { TrackersModal } from "./features/trackers/TrackersModal";
import { useLivePositions } from "./hooks/useLivePositions";
import { useNow } from "./hooks/useNow";
import { useOverview } from "./hooks/useOverview";
import { useHeardNodes } from "./hooks/useHeardNodes";
import { useTracks } from "./hooks/useTracks";
import { colourFor, teamColours } from "./lib/colours";
import { toHeardViews, toTrackerViews } from "./lib/trackers";
import { mergeTrack, toTrackRuns } from "./lib/tracks";
import { MapControls } from "./map/MapControls";
import { MapView } from "./map/MapView";
import type { NodeTrack } from "./map/tracks";
import styles from "./App.module.css";

const AGE_TICK_MS = 10_000;

type OpenDialog = "trackers" | "teams" | "newIncident" | "settings" | null;

export default function App() {
  const overview = useOverview();
  const { positions, tail, connection } = useLivePositions();
  const now = useNow(AGE_TICK_MS);

  const [dialog, setDialog] = useState<OpenDialog>(null);
  const [showTracks, setShowTracks] = useState(true);
  const [allNodes, setAllNodes] = useState(false);
  // null is the whole incident; a number narrows to the last that many hours.
  const [windowHours, setWindowHours] = useState<number | null>(null);

  // The area to download tiles over. Drawing it means handing the map back to
  // the operator, so settings closes for the duration and reopens with the
  // result -- the dialog would otherwise cover the thing being drawn on.
  const [drawing, setDrawing] = useState(false);
  const [area, setArea] = useState<Area | null>(null);

  const startDrawing = useCallback(() => {
    setDialog(null);
    setDrawing(true);
  }, []);

  const stopDrawing = useCallback(() => {
    setDrawing(false);
    setDialog("settings");
  }, []);

  const finishDrawing = useCallback(
    (drawn: Area) => {
      setArea(drawn);
      stopDrawing();
    },
    [stopDrawing],
  );

  const closeDialog = useCallback(() => setDialog(null), []);

  const trackers = useMemo(
    () => toTrackerViews(overview.statuses, positions, now),
    [overview.statuses, positions, now],
  );

  const colours = useMemo(
    () => teamColours(overview.statuses),
    [overview.statuses],
  );

  const { tracks } = useTracks(
    overview.incident?.id ?? null,
    windowHours,
    showTracks,
    connection,
  );

  const { nodes } = useHeardNodes(
    overview.incident?.id ?? null,
    allNodes,
    connection,
  );

  const heard = useMemo(
    () =>
      allNodes ? toHeardViews(nodes, overview.statuses, positions, now) : [],
    [allNodes, nodes, overview.statuses, positions, now],
  );

  // The fetched history plus whatever has arrived since, split where the mesh
  // stopped hearing the tracker.
  const trails = useMemo<NodeTrack[]>(() => {
    const byNode = new Map(trackers.map((view) => [view.nodeId, view]));

    return tracks.flatMap((track) => {
      const view = byNode.get(track.node_id);
      if (!view) return [];

      const points = mergeTrack(track.points, tail[track.node_id] ?? []);
      const runs = toTrackRuns(points, view.stale);

      return runs.length
        ? [{ nodeId: track.node_id, colour: colourFor(view, colours), runs }]
        : [];
    });
  }, [tracks, tail, trackers, colours]);

  return (
    <div className={styles.app}>
      <Header
        incident={overview.incident}
        connection={connection}
        onOpenTrackers={() => setDialog("trackers")}
        onOpenTeams={() => setDialog("teams")}
        onStartIncident={() => setDialog("newIncident")}
      />

      <main className={styles.body}>
        <aside className={styles.panel}>
          <div className={styles.panelScroll}>
            <h2>
              Trackers <span>{trackers.length}</span>
            </h2>

            <TrackerList
              trackers={trackers}
              colours={colours}
              error={overview.error}
              now={now}
            />

            {overview.basemap && !overview.basemap.available && (
              <Message>
                No offline basemap loaded. Positions still plot correctly; add
                one under Settings to get terrain.
              </Message>
            )}
          </div>

          <Button block onClick={() => setDialog("settings")}>
            Settings
          </Button>
        </aside>

        <MapView
          markers={trackers}
          heard={heard}
          tracks={trails}
          colours={colours}
          basemap={overview.basemap}
          online={overview.online}
          drawing={drawing}
          area={area}
          onAreaDrawn={finishDrawing}
        />

        {/* Hidden while drawing: the operator is dragging a box across the map
            and a panel in the corner is one more thing to catch the cursor. */}
        {!drawing && (
          <MapControls
            allNodes={allNodes}
            onAllNodes={setAllNodes}
            showTracks={showTracks}
            onShowTracks={setShowTracks}
            windowHours={windowHours}
            onWindowHours={setWindowHours}
            truncated={tracks.some((track) => track.truncated)}
          />
        )}

        {drawing && (
          <div className={styles.drawHint}>
            Drag a box over the area to download.
            <Button variant="link" onClick={stopDrawing}>
              Cancel
            </Button>
          </div>
        )}
      </main>

      <TrackersModal
        open={dialog === "trackers"}
        incident={overview.incident}
        onClose={closeDialog}
        onChanged={overview.refreshIncident}
      />

      <TeamsModal
        open={dialog === "teams"}
        onClose={closeDialog}
        onChanged={overview.refreshIncident}
      />

      <NewIncidentModal
        open={dialog === "newIncident"}
        onClose={closeDialog}
        onCreated={overview.refreshIncident}
      />

      <SettingsModal
        open={dialog === "settings"}
        incident={overview.incident}
        area={area}
        onClose={closeDialog}
        onBasemapChange={overview.refreshBasemap}
        onIncidentChange={overview.refreshIncident}
        onSelectArea={startDrawing}
      />
    </div>
  );
}

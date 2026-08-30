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
import { toTrackerViews } from "./lib/trackers";
import { MapView } from "./map/MapView";
import styles from "./App.module.css";

// How often the "last seen" ages recompute. Without a tick they would freeze
// at whatever they read when the last packet arrived.
const AGE_TICK_MS = 10_000;

// One dialog at a time: each is a native modal, and stacking two would leave
// the operator dismissing dialogs to get back to the map.
type OpenDialog = "trackers" | "teams" | "newIncident" | "settings" | null;

export default function App() {
  const overview = useOverview();
  const { positions, connection } = useLivePositions();
  const now = useNow(AGE_TICK_MS);

  const [dialog, setDialog] = useState<OpenDialog>(null);

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

            <TrackerList trackers={trackers} error={overview.error} now={now} />

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
          basemap={overview.basemap}
          online={overview.online}
          drawing={drawing}
          area={area}
          onAreaDrawn={finishDrawing}
        />

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

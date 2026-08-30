import type { Incident } from "../api";
import type { ConnectionState } from "../hooks/useLivePositions";
import { cx } from "../lib/cx";
import { Button } from "./ui";
import styles from "./Header.module.css";

const CONNECTION_LABEL: Record<ConnectionState, string> = {
  live: "Receiving",
  connecting: "Connecting",
  lost: "Signal lost",
};

export function Header({
  incident,
  connection,
  onOpenTrackers,
  onOpenTeams,
  onStartIncident,
}: {
  incident: Incident | null;
  connection: ConnectionState;
  onOpenTrackers: () => void;
  onOpenTeams: () => void;
  onStartIncident: () => void;
}) {
  return (
    <header className={styles.header}>
      <div>
        <h1>SARMesh</h1>
        <span className={styles.incident}>
          {incident ? incident.name : "No active incident"}
        </span>
      </div>

      <div className={styles.actions}>
        {/* Always available: trackers are kit, and kit is added and retired
            between searches as much as during one. */}
        <Button onClick={onOpenTrackers}>Trackers</Button>
        <Button onClick={onOpenTeams}>Teams</Button>

        {incident === null && (
          <Button onClick={onStartIncident}>Start new incident</Button>
        )}

        <span className={cx(styles.connection, styles[connection])}>
          {CONNECTION_LABEL[connection]}
        </span>
      </div>
    </header>
  );
}

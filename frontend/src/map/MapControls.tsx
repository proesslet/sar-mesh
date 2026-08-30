import styles from "./MapControls.module.css";

// null is the whole incident. Anything longer than a shift is better served by
// the full history, so the options stop there.
const WINDOWS: { label: string; hours: number | null }[] = [
  { label: "Whole incident", hours: null },
  { label: "Last 12 hours", hours: 12 },
  { label: "Last 4 hours", hours: 4 },
  { label: "Last hour", hours: 1 },
];

/**
 * View switches for the map.
 *
 * Rendered beside the map rather than inside it: a control inside Leaflet's
 * container has to stop its own clicks reaching the map, and this needs no
 * Leaflet plumbing at all where it sits.
 */
export function MapControls({
  allNodes,
  onAllNodes,
  showTracks,
  onShowTracks,
  windowHours,
  onWindowHours,
  truncated,
}: {
  allNodes: boolean;
  onAllNodes: (value: boolean) => void;
  showTracks: boolean;
  onShowTracks: (value: boolean) => void;
  windowHours: number | null;
  onWindowHours: (value: number | null) => void;
  // Some trail hit the server's per-tracker cap, so it starts later than the
  // window asked for.
  truncated: boolean;
}) {
  return (
    <div className={styles.controls}>
      <label className={styles.toggle}>
        <input
          type="checkbox"
          checked={allNodes}
          onChange={(event) => onAllNodes(event.target.checked)}
        />
        Show all heard nodes
      </label>

      <label className={styles.toggle}>
        <input
          type="checkbox"
          checked={showTracks}
          onChange={(event) => onShowTracks(event.target.checked)}
        />
        Show tracks
      </label>

      <div className={styles.window}>
        <label htmlFor="track-window">Trail</label>
        <select
          id="track-window"
          value={windowHours ?? ""}
          disabled={!showTracks}
          onChange={(event) =>
            onWindowHours(
              event.target.value ? Number(event.target.value) : null,
            )
          }
        >
          {WINDOWS.map((option) => (
            <option key={option.label} value={option.hours ?? ""}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {showTracks && truncated && (
        <p className={styles.note}>
          A trail was shortened to its most recent fixes. Narrow the window to
          see it in full.
        </p>
      )}
    </div>
  );
}

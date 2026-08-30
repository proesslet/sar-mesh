import type { CSSProperties } from "react";
import {
  ErrorMessage,
  List,
  ListItem,
  Message,
  Meta,
  Name,
  Row,
} from "../../components/ui";
import { colourFor } from "../../lib/colours";
import { formatAge } from "../../lib/format";
import type { TrackerView } from "../../lib/trackers";
import styles from "./TrackerList.module.css";

/** The live roster in the sidebar: who is out, where, and how long ago. */
export function TrackerList({
  trackers,
  colours,
  error,
  now,
}: {
  trackers: TrackerView[];
  colours: Map<string, string>;
  error: string | null;
  now: number;
}) {
  return (
    <>
      <ErrorMessage error={error} />

      {!error && trackers.length === 0 && (
        <Message tone="empty">
          No tracker positions yet. Assign a tracker to a team for the active
          incident, then wait for its next beacon.
        </Message>
      )}

      <List>
        {trackers.map((tracker) => (
          <ListItem
            key={tracker.nodeId}
            className={tracker.stale ? styles.stale : undefined}
          >
            <Row>
              <Name>
                {/* Same hue the map draws it in, so the list and the map are
                    read as one thing rather than two. */}
                <span
                  className={styles.swatch}
                  style={
                    { "--pin": colourFor(tracker, colours) } as CSSProperties
                  }
                />
                {tracker.label}
              </Name>
              <span className={styles.age}>
                {formatAge(tracker.position.received_at, now)}
              </span>
            </Row>
            <Meta>
              {tracker.team ?? "Unassigned"}
              {tracker.position.satellites != null &&
                ` · ${tracker.position.satellites} sats`}
            </Meta>
          </ListItem>
        ))}
      </List>
    </>
  );
}

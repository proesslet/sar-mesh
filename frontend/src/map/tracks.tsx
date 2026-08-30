import { Fragment } from "react";
import { CircleMarker, Polyline } from "react-leaflet";
import type { TrackRun } from "../lib/tracks";

// Drawn under the coloured line, so a trail reads against whatever the basemap
// happens to be. Half the palette falls below 3:1 contrast on light terrain,
// and an offline pack can be any shade at all.
const CASING = "#0d1014";
const CASING_WEIGHT = 5;
const TRACK_WEIGHT = 3;

// Long enough to read as deliberate at a glance rather than as a rendering
// artefact on a line that bends a lot.
const STALE_DASH = "6 5";

export interface NodeTrack {
  nodeId: string;
  colour: string;
  runs: TrackRun[];
}

/**
 * Trails behind the trackers.
 *
 * Every line is non-interactive: Leaflet would otherwise let them swallow
 * clicks meant for a marker popup, and a trail lying across the map would
 * block the drag-to-draw handler outright.
 *
 * No custom pane needed -- Leaflet already puts polylines under markers.
 */
export function TrackLayer({ tracks }: { tracks: NodeTrack[] }) {
  return (
    <>
      {tracks.flatMap(({ nodeId, colour, runs }) =>
        runs.map((run, index) => {
          const line = run.points.map(
            (point) => [point.latitude, point.longitude] as [number, number],
          );
          return (
            // A Fragment, not an element: these attach to the Leaflet map
            // rather than rendering into the React tree, so a wrapper would
            // only put a stray div inside the map container.
            <Fragment key={`${nodeId}:${index}`}>
              <Polyline
                positions={line}
                interactive={false}
                pathOptions={{
                  color: CASING,
                  weight: CASING_WEIGHT,
                  opacity: 0.5,
                }}
              />
              <Polyline
                positions={line}
                interactive={false}
                pathOptions={{
                  color: colour,
                  weight: TRACK_WEIGHT,
                  opacity: 0.9,
                  dashArray: run.dashed ? STALE_DASH : undefined,
                }}
              />
              {/* Where the mesh stopped hearing this tracker and picked it up
                  again. That is the terrain shadow, and it also stops two runs
                  of one person reading as two people. */}
              <CircleMarker
                center={line[0]}
                radius={3}
                interactive={false}
                pathOptions={{
                  color: colour,
                  weight: 2,
                  fillOpacity: 0,
                }}
              />
            </Fragment>
          );
        }),
      )}
    </>
  );
}

import type { TrackerStatus } from "../api";
import type { TrackerView } from "./trackers";

/**
 * One hue per team, so a trail and the pin at the end of it read as the same
 * people.
 *
 * Literal hex rather than tokens in index.css: Leaflet writes the colour as an
 * SVG presentation attribute, where a CSS custom property does not resolve.
 *
 * Six rather than the usual eight because trails land wherever the teams walk,
 * so any two can end up side by side -- the palette has to separate on every
 * pair, not just on neighbours in a legend. Validated against the map's own
 * background: all pairs clear the normal-vision floor and 3:1 contrast. The
 * colour-blind separation sits in the band that needs a second cue, which the
 * pin popups and the sidebar roster provide by naming the team.
 */
const TEAM_COLOURS = [
  "#cc3336",
  "#276ee1",
  "#9d47bf",
  "#179765",
  "#b37903",
  "#e356a2",
] as const;

/** A node heard on the mesh but not working this incident. */
export const UNASSIGNED_COLOUR = "#ffffff";

/**
 * Assign a colour to every team on the incident, ordered by name so the same
 * search comes up the same way each time it is opened.
 *
 * Adding a team mid-search can shift the others, because the order changes. It
 * is rare and the change is immediately visible rather than silent; the fix, if
 * it ever matters, is storing the index on the team.
 */
export function teamColours(statuses: TrackerStatus[]): Map<string, string> {
  const names = new Map<string, string>();

  for (const status of statuses) {
    if (status.team) names.set(status.team.id, status.team.name);
  }

  const ordered = [...names.entries()].sort(([, a], [, b]) =>
    a.localeCompare(b),
  );

  return new Map(
    ordered.map(([id], index) => [
      id,
      TEAM_COLOURS[index % TEAM_COLOURS.length],
    ]),
  );
}

/** A tracker's hue: its team's, or white for one nobody is carrying. */
export function colourFor(
  view: TrackerView,
  colours: Map<string, string>,
): string {
  if (view.teamId === null) return UNASSIGNED_COLOUR;

  return colours.get(view.teamId) ?? UNASSIGNED_COLOUR;
}

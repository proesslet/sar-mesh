/**
 * Elapsed time as a short, glanceable label: "45s", "12m", "3h".
 *
 * `now` is passed in rather than read from the clock so callers render from a
 * value that ticks on their own schedule -- reading the clock mid-render makes
 * the output depend on when React happens to re-render.
 */
export function formatAge(iso: string, now: number): string {
  const seconds = Math.max(0, (now - new Date(iso).getTime()) / 1000);

  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;

  return `${Math.floor(seconds / 3600)}h`;
}

/** Byte counts at pack scale, where a megabyte's decimal place is noise. */
export function formatSize(bytes: number): string {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  if (bytes >= 1e6) return `${Math.round(bytes / 1e6)} MB`;
  if (bytes >= 1e3) return `${Math.round(bytes / 1e3)} kB`;

  return `${bytes} B`;
}

/** A bounding box as "west, south → east, north", rounded to roughly 100 m. */
export function formatArea(area: {
  west: number;
  south: number;
  east: number;
  north: number;
}): string {
  const round = (value: number) => value.toFixed(3);

  return `${round(area.west)}, ${round(area.south)} → ${round(area.east)}, ${round(area.north)}`;
}

export function pluralize(count: number, singular: string): string {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}

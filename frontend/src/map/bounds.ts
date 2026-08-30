import L from "leaflet";

/**
 * Parse an MBTiles coverage string, recorded as "west,south,east,north".
 */
export function parseBounds(
  bounds: string | null | undefined,
): L.LatLngBounds | null {
  if (!bounds) return null;

  const parts = bounds.split(",").map((value) => Number(value.trim()));

  if (parts.length !== 4 || parts.some((value) => !Number.isFinite(value))) {
    return null;
  }

  const [west, south, east, north] = parts;

  if (west === east || south === north) return null;

  return L.latLngBounds([south, west], [north, east]);
}

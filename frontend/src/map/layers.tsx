import L from "leaflet";
import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import type { Area, Basemap } from "../api";
import type { TrackerView } from "../lib/trackers";
import { parseBounds } from "./bounds";

const DRAWN_AREA_STYLE = { color: "#4ea1ff", weight: 1 };

/** Frame the trackers when the set of them changes -- not as they move. */
export function FitToTrackers({ markers }: { markers: TrackerView[] }) {
  const map = useMap();
  const fittedTo = useRef<string | null>(null);

  useEffect(() => {
    if (markers.length === 0) return;

    // Keyed on which trackers are present rather than where they are: refitting
    // on every beacon would fight an operator panning around the map.
    const key = markers
      .map((marker) => marker.nodeId)
      .sort()
      .join(",");

    if (key === fittedTo.current) return;
    fittedTo.current = key;

    map.fitBounds(
      L.latLngBounds(
        markers.map(
          (marker) =>
            [marker.position.latitude, marker.position.longitude] as [
              number,
              number,
            ],
        ),
      ),
      { padding: [48, 48], maxZoom: 15 },
    );
  }, [markers, map]);

  return null;
}

/**
 * Move to a newly selected pack's coverage.
 *
 * Selecting a pack for one valley while looking at another shows a blank map,
 * which reads as a broken download rather than as looking at the wrong place.
 */
export function FitToBasemap({ basemap }: { basemap: Basemap | null }) {
  const map = useMap();
  const revision = basemap?.revision;

  useEffect(() => {
    // Revision changes only when the operator picks a different pack, so this
    // never yanks the view out from under someone who is panning around.
    if (!revision) return;

    const bounds = parseBounds(basemap?.bounds);
    if (!bounds) return;

    map.fitBounds(bounds, {
      padding: [32, 32],
      maxZoom: basemap?.maxzoom ?? 15,
    });
  }, [revision, map, basemap?.bounds, basemap?.maxzoom]);

  return null;
}

/**
 * Drag-to-draw a rectangle, for choosing the area to download tiles over.
 *
 * Written against Leaflet directly rather than pulling in leaflet-draw: this
 * is one rectangle with no editing handles, and the plugin is a large
 * dependency for an app that has to be installable on a field laptop.
 */
export function DrawArea({ onDrawn }: { onDrawn: (area: Area) => void }) {
  const map = useMap();

  useEffect(() => {
    let origin: L.LatLng | null = null;
    let rectangle: L.Rectangle | null = null;

    // Dragging is what the operator is about to do with the mouse, so panning
    // has to be off for the duration or the map would slide underneath them.
    map.dragging.disable();
    map.getContainer().style.cursor = "crosshair";

    const boxTo = (corner: L.LatLng) => L.latLngBounds(origin!, corner);

    function down(event: L.LeafletMouseEvent) {
      origin = event.latlng;
      rectangle = L.rectangle(boxTo(event.latlng), {
        ...DRAWN_AREA_STYLE,
        fillOpacity: 0.15,
      }).addTo(map);
    }

    function move(event: L.LeafletMouseEvent) {
      if (origin && rectangle) rectangle.setBounds(boxTo(event.latlng));
    }

    function up(event: L.LeafletMouseEvent) {
      if (!origin) return;

      const box = boxTo(event.latlng);
      origin = null;
      rectangle?.remove();

      // A click with no drag is an accident, not a zero-size request.
      if (
        box.getWest() === box.getEast() ||
        box.getSouth() === box.getNorth()
      ) {
        return;
      }

      onDrawn({
        west: box.getWest(),
        south: box.getSouth(),
        east: box.getEast(),
        north: box.getNorth(),
      });
    }

    map.on("mousedown", down);
    map.on("mousemove", move);
    map.on("mouseup", up);

    return () => {
      map.off("mousedown", down);
      map.off("mousemove", move);
      map.off("mouseup", up);
      rectangle?.remove();
      map.dragging.enable();
      map.getContainer().style.cursor = "";
    };
  }, [map, onDrawn]);

  return null;
}

// Shows the area already chosen, so reopening settings does not leave the
// operator guessing what the stored bounds refer to.
export function AreaOutline({ area }: { area: Area }) {
  const map = useMap();

  useEffect(() => {
    const rectangle = L.rectangle(
      L.latLngBounds([area.south, area.west], [area.north, area.east]),
      { ...DRAWN_AREA_STYLE, dashArray: "4 3", fillOpacity: 0.08 },
    ).addTo(map);

    return () => {
      rectangle.remove();
    };
  }, [map, area]);

  return null;
}

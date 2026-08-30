import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import type { Area, Basemap, OnlineSource } from "../api";
import { colourFor } from "../lib/colours";
import type { TrackerView } from "../lib/trackers";
import { trackerIcon } from "./icons";
import { AreaOutline, DrawArea, FitToBasemap, FitToTrackers } from "./layers";
import { TrackLayer } from "./tracks";
import type { NodeTrack } from "./tracks";
import "leaflet/dist/leaflet.css";
import styles from "./MapView.module.css";

const DEFAULT_CENTER: [number, number] = [39.5, -98.35];
const MAX_ZOOM = 19;

export function MapView({
  markers,
  heard,
  tracks,
  colours,
  basemap,
  online,
  drawing,
  area,
  onAreaDrawn,
}: {
  // The incident roster. Kept apart from `heard` because the map frames itself
  // on this: a stranger beaconing must not pull the view off the search.
  markers: TrackerView[];
  heard: TrackerView[];
  tracks: NodeTrack[];
  colours: Map<string, string>;
  basemap: Basemap | null;
  online: OnlineSource | null;
  drawing: boolean;
  area: Area | null;
  onAreaDrawn: (area: Area) => void;
}) {
  const first = markers[0]?.position;

  return (
    <MapContainer
      center={first ? [first.latitude, first.longitude] : DEFAULT_CENTER}
      zoom={first ? 13 : 4}
      className={styles.map}
    >
      {online?.enabled && (
        <TileLayer
          url={online.url_template}
          attribution={online.attribution ?? undefined}
          maxZoom={MAX_ZOOM}
          noWrap
        />
      )}

      {basemap?.available && (
        <TileLayer
          key={basemap.revision}
          url={`/tiles/{z}/{x}/{y}.png?v=${basemap.revision}`}
          minNativeZoom={basemap.minzoom ?? 0}
          maxNativeZoom={basemap.maxzoom ?? 16}
          maxZoom={MAX_ZOOM}
          noWrap
        />
      )}

      <FitToBasemap basemap={basemap} />
      <FitToTrackers markers={markers} />

      <TrackLayer tracks={tracks} />

      {drawing && <DrawArea onDrawn={onAreaDrawn} />}
      {!drawing && area && <AreaOutline area={area} />}

      {[...markers, ...heard].map((marker) => (
        <Marker
          key={marker.nodeId}
          position={[marker.position.latitude, marker.position.longitude]}
          icon={trackerIcon(colourFor(marker, colours), marker.stale)}
        >
          <Popup>
            <strong>{marker.label}</strong>
            <br />
            {marker.team ?? "Unassigned"}
            <br />
            {marker.position.latitude.toFixed(5)},{" "}
            {marker.position.longitude.toFixed(5)}
            <br />
            <small>
              {new Date(marker.position.received_at).toLocaleTimeString()}
              {marker.position.satellites != null &&
                ` · ${marker.position.satellites} sats`}
              {marker.position.rssi != null && ` · ${marker.position.rssi} dBm`}
            </small>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}

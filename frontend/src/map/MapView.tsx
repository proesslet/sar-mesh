import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import type { Area, Basemap, OnlineSource } from "../api";
import type { TrackerView } from "../lib/trackers";
import { trackerIcon } from "./icons";
import { AreaOutline, DrawArea, FitToBasemap, FitToTrackers } from "./layers";
import "leaflet/dist/leaflet.css";
import styles from "./MapView.module.css";

// Roughly the centre of the continental US, used only until a tracker reports.
const DEFAULT_CENTER: [number, number] = [39.5, -98.35];

// Leaflet will not request tiles past this, whatever a pack or source claims.
const MAX_ZOOM = 19;

export function MapView({
  markers,
  basemap,
  online,
  drawing,
  area,
  onAreaDrawn,
}: {
  markers: TrackerView[];
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
      {/* Underneath the offline pack on purpose. Where a pack has coverage its
          tiles win, which is what an operator in the field needs; everywhere
          else the online map shows through, so they can see where they are
          while choosing the next area to download. When there is no network
          these tiles simply fail to paint and the pack shows regardless, so
          the fallback needs no connectivity check. */}
      {online?.enabled && (
        <TileLayer
          url={online.url_template}
          attribution={online.attribution ?? undefined}
          maxZoom={MAX_ZOOM}
          noWrap
        />
      )}

      {basemap?.available && (
        // Keyed and versioned on the revision: tile URLs are identical between
        // packs, so without it a swap would keep painting the old pack's tiles
        // out of the browser cache.
        <TileLayer
          key={basemap.revision}
          url={`/tiles/{z}/{x}/{y}.png?v=${basemap.revision}`}
          // A pack downloaded for zooms 10-15 holds nothing at zoom 4. Without
          // these bounds Leaflet asks for tiles that were never in the pack and
          // paints nothing at all; with them it scales the nearest zoom it does
          // have, so the pack stays visible at every zoom level.
          minNativeZoom={basemap.minzoom ?? 0}
          maxNativeZoom={basemap.maxzoom ?? 16}
          maxZoom={MAX_ZOOM}
          noWrap
        />
      )}

      <FitToBasemap basemap={basemap} />
      <FitToTrackers markers={markers} />

      {drawing && <DrawArea onDrawn={onAreaDrawn} />}
      {!drawing && area && <AreaOutline area={area} />}

      {markers.map((marker) => (
        <Marker
          key={marker.nodeId}
          position={[marker.position.latitude, marker.position.longitude]}
          icon={trackerIcon(marker.stale)}
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

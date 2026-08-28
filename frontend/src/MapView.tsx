import L from 'leaflet'
import { useEffect, useMemo } from 'react'
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import type { Basemap, OnlineSource, Position } from './api'
import 'leaflet/dist/leaflet.css'

export interface Area {
  west: number
  south: number
  east: number
  north: number
}

export interface TrackerMarker {
  nodeId: string
  label: string
  team: string | null
  position: Position
  stale: boolean
}

// Leaflet's default marker is a PNG whose URL breaks under bundlers. A divIcon
// is styled entirely in CSS, so there is no image asset to resolve and nothing
// to fetch at runtime -- which also keeps the app working fully offline.
function icon(stale: boolean): L.DivIcon {
  return L.divIcon({
    className: '',
    html: `<div class="tracker-pin ${stale ? 'stale' : ''}"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  })
}

function FitToTrackers({ markers }: { markers: TrackerMarker[] }) {
  const map = useMap()

  useMemo(() => {
    if (markers.length === 0) return

    const bounds = L.latLngBounds(
      markers.map((m) => [m.position.latitude, m.position.longitude] as [number, number]),
    )
    map.fitBounds(bounds, { padding: [48, 48], maxZoom: 15 })
    // Refit only when the set of trackers changes, not on every position
    // update, or the map would fight the operator panning around.
  }, [markers.length, map])

  return null
}

/**
 * MBTiles records coverage as "west,south,east,north". Parsed defensively:
 * the pack may have been built by any tool, or by hand.
 */
function parseBounds(bounds: string | null | undefined): L.LatLngBounds | null {
  if (!bounds) return null

  const parts = bounds.split(',').map((value) => Number(value.trim()))

  if (parts.length !== 4 || parts.some((value) => !Number.isFinite(value))) return null

  const [west, south, east, north] = parts

  if (west === east || south === north) return null

  return L.latLngBounds([south, west], [north, east])
}

/**
 * Move to a newly selected pack's coverage.
 *
 * Selecting a pack for one valley while looking at another shows a blank map,
 * which reads as a broken download rather than as looking at the wrong place.
 */
function FitToBasemap({ basemap }: { basemap: Basemap | null }) {
  const map = useMap()
  const revision = basemap?.revision

  useEffect(() => {
    // Revision changes only when the operator picks a different pack, so this
    // never yanks the view out from under someone who is panning around.
    if (!revision) return

    const bounds = parseBounds(basemap?.bounds)
    if (!bounds) return

    map.fitBounds(bounds, { padding: [32, 32], maxZoom: basemap?.maxzoom ?? 15 })
  }, [revision, map, basemap?.bounds, basemap?.maxzoom])

  return null
}

/**
 * Drag-to-draw a rectangle, for choosing the area to download tiles over.
 *
 * Written against Leaflet directly rather than pulling in leaflet-draw: this
 * is one rectangle with no editing handles, and the plugin is a large
 * dependency for an app that has to be installable on a field laptop.
 */
function DrawArea({ onDrawn }: { onDrawn: (area: Area) => void }) {
  const map = useMap()

  useEffect(() => {
    let origin: L.LatLng | null = null
    let rectangle: L.Rectangle | null = null

    // Dragging is what the operator is about to do with the mouse, so panning
    // has to be off for the duration or the map would slide underneath them.
    map.dragging.disable()
    map.getContainer().style.cursor = 'crosshair'

    const bounds = (corner: L.LatLng) => L.latLngBounds(origin!, corner)

    function down(event: L.LeafletMouseEvent) {
      origin = event.latlng
      rectangle = L.rectangle(bounds(event.latlng), {
        color: '#4ea1ff',
        weight: 1,
        fillOpacity: 0.15,
      }).addTo(map)
    }

    function move(event: L.LeafletMouseEvent) {
      if (origin && rectangle) rectangle.setBounds(bounds(event.latlng))
    }

    function up(event: L.LeafletMouseEvent) {
      if (!origin) return

      const box = bounds(event.latlng)
      origin = null
      rectangle?.remove()

      // A click with no drag is an accident, not a zero-size request.
      if (box.getWest() === box.getEast() || box.getSouth() === box.getNorth()) return

      onDrawn({
        west: box.getWest(),
        south: box.getSouth(),
        east: box.getEast(),
        north: box.getNorth(),
      })
    }

    map.on('mousedown', down)
    map.on('mousemove', move)
    map.on('mouseup', up)

    return () => {
      map.off('mousedown', down)
      map.off('mousemove', move)
      map.off('mouseup', up)
      rectangle?.remove()
      map.dragging.enable()
      map.getContainer().style.cursor = ''
    }
  }, [map, onDrawn])

  return null
}

// Shows the area already chosen, so reopening settings does not leave the
// operator guessing what the stored bounds refer to.
function AreaOutline({ area }: { area: Area }) {
  const map = useMap()

  useEffect(() => {
    const rectangle = L.rectangle(
      L.latLngBounds([area.south, area.west], [area.north, area.east]),
      { color: '#4ea1ff', weight: 1, dashArray: '4 3', fillOpacity: 0.08 },
    ).addTo(map)

    return () => {
      rectangle.remove()
    }
  }, [map, area])

  return null
}

export function MapView({
  markers,
  basemap,
  online,
  drawing,
  area,
  onAreaDrawn,
}: {
  markers: TrackerMarker[]
  basemap: Basemap | null
  online: OnlineSource | null
  drawing: boolean
  area: Area | null
  onAreaDrawn: (area: Area) => void
}) {
  const center: [number, number] = markers.length
    ? [markers[0].position.latitude, markers[0].position.longitude]
    : [39.5, -98.35]

  return (
    <MapContainer center={center} zoom={markers.length ? 13 : 4} className="map">
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
          maxZoom={19}
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
          maxZoom={19}
          noWrap
        />
      )}

      <FitToBasemap basemap={basemap} />

      {drawing && <DrawArea onDrawn={onAreaDrawn} />}
      {!drawing && area && <AreaOutline area={area} />}

      <FitToTrackers markers={markers} />

      {markers.map((marker) => (
        <Marker
          key={marker.nodeId}
          position={[marker.position.latitude, marker.position.longitude]}
          icon={icon(marker.stale)}
        >
          <Popup>
            <strong>{marker.label}</strong>
            <br />
            {marker.team ?? 'Unassigned'}
            <br />
            {marker.position.latitude.toFixed(5)}, {marker.position.longitude.toFixed(5)}
            <br />
            <small>
              {new Date(marker.position.received_at).toLocaleTimeString()}
              {marker.position.satellites != null && ` · ${marker.position.satellites} sats`}
              {marker.position.rssi != null && ` · ${marker.position.rssi} dBm`}
            </small>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  )
}

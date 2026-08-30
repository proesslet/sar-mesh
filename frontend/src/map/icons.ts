import L from "leaflet";
import styles from "./MapView.module.css";

// Leaflet's default marker is a PNG whose URL breaks under bundlers. A divIcon
// is styled entirely in CSS, so there is no image asset to resolve and nothing
// to fetch at runtime -- which also keeps the app working fully offline.
function pin(colour: string, stale: boolean): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div class="${styles.pin}${stale ? ` ${styles.stale}` : ""}" style="--pin:${colour}"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

// Cached because react-leaflet reapplies the icon whenever the object identity
// changes, which would rebuild every marker's DOM node on each re-render. The
// palette is small, so this stays a handful of entries.
const icons = new Map<string, L.DivIcon>();

export function trackerIcon(colour: string, stale: boolean): L.DivIcon {
  const key = `${colour}|${stale}`;
  let icon = icons.get(key);

  if (!icon) {
    icon = pin(colour, stale);
    icons.set(key, icon);
  }

  return icon;
}

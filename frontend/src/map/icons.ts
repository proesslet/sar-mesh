import L from "leaflet";
import styles from "./MapView.module.css";

// Leaflet's default marker is a PNG whose URL breaks under bundlers. A divIcon
// is styled entirely in CSS, so there is no image asset to resolve and nothing
// to fetch at runtime -- which also keeps the app working fully offline.
function pin(stale: boolean): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div class="${styles.pin}${stale ? ` ${styles.stale}` : ""}"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

// Built once: react-leaflet reapplies the icon whenever the object identity
// changes, which would rebuild every marker's DOM node on each re-render.
const FRESH_PIN = pin(false);
const STALE_PIN = pin(true);

export function trackerIcon(stale: boolean): L.DivIcon {
  return stale ? STALE_PIN : FRESH_PIN;
}

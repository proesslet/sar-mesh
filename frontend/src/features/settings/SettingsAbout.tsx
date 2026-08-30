import {
  CopyButton,
  List,
  ListItem,
  Message,
  Meta,
  Name,
  Row,
  Section,
} from "../../components/ui";
import styles from "./SettingsAbout.module.css";

const REPOSITORY = "https://github.com/proesslet/sar-mesh";

/**
 * What the app is built on.
 *
 * Shown as text with a copy button rather than as links: the desktop build
 * hosts the UI in a bare QWebEngineView, where a link either does nothing or
 * navigates the app off its own interface with no way back. The machine is
 * also expected to be off-grid, so a link would usually go nowhere anyway.
 */
const CREDITS = [
  {
    name: "Meshtastic",
    detail: "The mesh radio firmware that field trackers run",
    url: "https://meshtastic.org/",
  },
  {
    name: "Leaflet",
    detail: "Map rendering, BSD-2-Clause",
    url: "https://leafletjs.com/",
  },
  {
    name: "OpenStreetMap",
    detail: "Default online tile source, © OpenStreetMap contributors, ODbL",
    url: "https://www.openstreetmap.org/copyright",
  },
  {
    name: "React",
    detail: "User interface, MIT",
    url: "https://react.dev/",
  },
  {
    name: "FastAPI · Uvicorn · Typer",
    detail: "The local server and command line, MIT / BSD-3-Clause",
    url: "https://fastapi.tiangolo.com/",
  },
];

export function SettingsAbout({ version }: { version: string | null }) {
  return (
    <>
      <Section title="SARMesh">
        <p className={styles.tagline}>
          Offline search and rescue personnel tracking over mesh radio networks.{" "}
          {version && <span className={styles.version}>Version {version}</span>}
        </p>

        <Message>
          SARMesh listens to a Meshtastic mesh, records position beacons from
          field trackers, and plots them against the teams working an incident.
          It runs entirely off-grid: no internet, no cloud, no cell coverage.
          Everything lives in a single local SQLite file.
        </Message>

        <Row>
          <Meta>Project</Meta>
          <CopyButton value={REPOSITORY} />
        </Row>
        <code className={styles.url}>{REPOSITORY}</code>
      </Section>

      <Section title="License">
        <p className={styles.notice}>
          <strong>SARMesh</strong> Copyright © 2026 Preston Roesslet
          <br />
          This program comes with <strong>absolutely no warranty</strong>.
          <br />
          This is free software, and you are welcome to redistribute it under
          the terms of the GNU General Public License, version 3.
        </p>
      </Section>

      <Section title="Built with">
        <List>
          {CREDITS.map((credit) => (
            <ListItem key={credit.name}>
              <Row>
                <Name>{credit.name}</Name>
                <CopyButton value={credit.url} title={`Copy ${credit.url}`} />
              </Row>
              <Meta>{credit.detail}</Meta>
            </ListItem>
          ))}
        </List>
      </Section>
    </>
  );
}

import type { ReactNode } from "react";
import type { RadioInfo } from "../../api";
import {
  Actions,
  Button,
  ErrorMessage,
  Message,
  Meta,
  Name,
  Row,
  Section,
} from "../../components/ui";
import { useRadio } from "../../hooks/useRadio";
import styles from "./SettingsRadio.module.css";

/**
 * One reading from the node.
 *
 * Renders nothing when the value is missing rather than showing an empty
 * label: a node partway through its config download genuinely does not know
 * its own firmware version yet, and a blank row reads as a fault that is not
 * there.
 */
function Detail({ label, value }: { label: string; value: ReactNode }) {
  if (value == null || value === "") return null;

  return (
    <Row className={styles.detail}>
      <Meta className={styles.label}>{label}</Meta>
      <span className={styles.value}>{value}</span>
    </Row>
  );
}

function RadioDetails({ radio }: { radio: RadioInfo }) {
  return (
    <>
      <Row>
        <Name>{radio.long_name ?? radio.node_id ?? "Unnamed node"}</Name>
        {radio.short_name && (
          <code className={styles.tag}>{radio.short_name}</code>
        )}
      </Row>

      <div className={styles.details}>
        <Detail label="Node ID" value={radio.node_id} />
        <Detail label="Node number" value={radio.node_num} />
        <Detail label="Hardware" value={radio.hardware} />
        <Detail label="Firmware" value={radio.firmware_version} />
        <Detail label="Role" value={radio.role} />
        <Detail label="Known nodes" value={radio.node_count} />
      </div>

      {/* The count includes the attached node, so one means it has heard
          nothing else -- worth saying outright, since that is exactly the
          state an operator is trying to diagnose when they open this. */}
      {radio.node_count <= 1 && (
        <Message tone="empty">This node has not heard any others yet.</Message>
      )}
    </>
  );
}

export function SettingsRadio() {
  const { radio, disconnected, error, loading, reload } = useRadio();

  return (
    <Section title="Radio">
      <ErrorMessage error={error} />

      {radio ? (
        <RadioDetails radio={radio} />
      ) : (
        !loading && (
          <Message tone="empty">
            {disconnected
              ? "No Meshtastic node connected. Plug one in over USB, or start SARMesh with --host to reach one over the network."
              : "The radio could not be read."}
          </Message>
        )
      )}

      <Actions>
        <Button onClick={reload} disabled={loading}>
          {loading ? "Checking…" : "Refresh"}
        </Button>
      </Actions>
    </Section>
  );
}

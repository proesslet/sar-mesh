import { useState } from "react";
import { api } from "../../api";
import type { Incident } from "../../api";
import {
  Actions,
  Button,
  ErrorMessage,
  Field,
  Form,
  Message,
  Meta,
  Section,
  TextInput,
} from "../../components/ui";
import { useAsyncAction } from "../../hooks/useAsyncAction";

export function SettingsIncident({
  incident,
  onChange,
}: {
  incident: Incident | null;
  // Fired after a rename or an end, so the header reflects the change.
  onChange: () => void;
}) {
  const [name, setName] = useState(incident?.name ?? "");
  const [confirmEnd, setConfirmEnd] = useState(false);
  const [editing, setEditing] = useState(incident?.id ?? null);
  const { busy, error, run } = useAsyncAction();

  // The active incident can change while settings are open -- it is ended, or
  // a new one is started -- and the form has to follow. Keyed on the id rather
  // than the object so a refetch that returns the same incident does not wipe
  // whatever the operator was part-way through typing.
  if ((incident?.id ?? null) !== editing) {
    setEditing(incident?.id ?? null);
    setName(incident?.name ?? "");
    setConfirmEnd(false);
  }

  if (incident === null) {
    return (
      <Section title="Incident">
        <Message tone="empty">
          No active incident. Start one to record positions against it.
        </Message>
      </Section>
    );
  }

  const trimmed = name.trim();
  const dirty = trimmed !== incident.name;

  return (
    <Section title="Incident">
      <ErrorMessage error={error} />

      <Form
        onSubmit={() => {
          if (dirty && trimmed) {
            run(() => api.renameIncident(incident.id, trimmed), onChange);
          }
        }}
      >
        <Field label="Name" htmlFor="incident-name">
          <Actions>
            <TextInput
              id="incident-name"
              value={name}
              disabled={busy}
              onChange={(event) => setName(event.target.value)}
            />
            <Button type="submit" disabled={busy || !dirty || !trimmed}>
              Save
            </Button>
          </Actions>
        </Field>
      </Form>

      <Meta>Started {new Date(incident.started_at).toLocaleString()}</Meta>

      <Actions>
        {confirmEnd ? (
          <>
            {/* Ending is what stops positions being recorded against this
                incident, and there is no undo, so it takes two clicks. */}
            <Meta>End {incident.name}?</Meta>
            <Button
              danger
              disabled={busy}
              onClick={() => run(() => api.endIncident(incident.id), onChange)}
            >
              End incident
            </Button>
            <Button onClick={() => setConfirmEnd(false)}>Cancel</Button>
          </>
        ) : (
          <Button disabled={busy} onClick={() => setConfirmEnd(true)}>
            End incident
          </Button>
        )}
      </Actions>
    </Section>
  );
}

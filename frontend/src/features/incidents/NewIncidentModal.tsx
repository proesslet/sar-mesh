import { useState } from "react";
import { api } from "../../api";
import { Modal } from "../../components/Modal";
import {
  Actions,
  Button,
  ErrorMessage,
  Field,
  Form,
  Message,
  TextInput,
} from "../../components/ui";
import { useAsyncAction } from "../../hooks/useAsyncAction";

export function NewIncidentModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const { busy, error, run } = useAsyncAction();

  // Not rendered while closed, so the field starts empty each time rather than
  // holding the name of an incident that was already created.
  if (!open) return null;

  const trimmed = name.trim();

  return (
    <Modal open={open} title="New incident" onClose={onClose}>
      <ErrorMessage error={error} />

      <Form
        onSubmit={() => {
          if (!trimmed) return;

          run(
            () => api.createIncident(trimmed),
            () => {
              setName("");
              onCreated();
              onClose();
            },
          );
        }}
      >
        <Field label="Name" htmlFor="new-incident-name">
          <Actions>
            <TextInput
              id="new-incident-name"
              placeholder="Ridge Search"
              value={name}
              disabled={busy}
              onChange={(event) => setName(event.target.value)}
            />
            <Button type="submit" disabled={busy || !trimmed}>
              Start
            </Button>
          </Actions>
        </Field>
      </Form>

      <Message>
        Positions and tracker assignments are recorded against the active
        incident. End it under Settings when the search is over.
      </Message>
    </Modal>
  );
}

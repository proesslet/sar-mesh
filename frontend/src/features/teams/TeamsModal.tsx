import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import type { Team } from "../../api";
import { Modal } from "../../components/Modal";
import {
  Actions,
  Button,
  ErrorMessage,
  Field,
  Form,
  List,
  ListItem,
  Message,
  Meta,
  Name,
  Row,
  Section,
  TextInput,
} from "../../components/ui";
import { useAsyncAction } from "../../hooks/useAsyncAction";
import { pluralize } from "../../lib/format";

const DEFAULT_PERSONNEL = 2;

export function TeamsModal({
  open,
  onClose,
  onChanged,
}: {
  open: boolean;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [teams, setTeams] = useState<Team[]>([]);
  const [name, setName] = useState("");
  const [personnel, setPersonnel] = useState(DEFAULT_PERSONNEL);
  const { busy, error, fail, run } = useAsyncAction();

  const load = useCallback(() => {
    api.teams().then(setTeams).catch(fail);
  }, [fail]);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  // Teams name the rows in the sidebar, so a change here has to reach it.
  const mutate = useCallback(
    (action: () => Promise<unknown>, after?: () => void) =>
      run(action, () => {
        after?.();
        load();
        onChanged();
      }),
    [run, load, onChanged],
  );

  if (!open) return null;

  const trimmed = name.trim();

  return (
    <Modal open={open} title="Teams" onClose={onClose} size="md">
      <ErrorMessage error={error} />

      <Section title="Teams" count={teams.length}>
        {teams.length === 0 && (
          <Message tone="empty">
            No teams yet. Add one below, then assign trackers to it.
          </Message>
        )}

        <List>
          {teams.map((team) => (
            <ListItem key={team.id}>
              <Row>
                <Name>{team.name}</Name>
                <Button
                  variant="link"
                  danger
                  // A team holding trackers cannot be deleted: their positions
                  // would stop being attributed to anyone mid-search.
                  disabled={busy || team.tracker_count > 0}
                  title={
                    team.tracker_count > 0
                      ? `Holding ${pluralize(team.tracker_count, "tracker")}`
                      : "Delete this team"
                  }
                  onClick={() => mutate(() => api.deleteTeam(team.id))}
                >
                  Delete
                </Button>
              </Row>
              <Meta>
                {team.personnel_count} personnel
                {team.tracker_count > 0 &&
                  ` · ${pluralize(team.tracker_count, "tracker")}`}
              </Meta>
            </ListItem>
          ))}
        </List>
      </Section>

      <Section title="Add a team">
        <Form
          onSubmit={() => {
            if (!trimmed) return;

            mutate(
              () => api.createTeam(trimmed, personnel),
              () => {
                setName("");
                setPersonnel(DEFAULT_PERSONNEL);
              },
            );
          }}
        >
          <Field label="Name" htmlFor="team-name">
            <TextInput
              id="team-name"
              placeholder="Alpha"
              value={name}
              disabled={busy}
              full
              onChange={(event) => setName(event.target.value)}
            />
          </Field>

          <Field label="Personnel" htmlFor="team-personnel">
            <Actions>
              <TextInput
                id="team-personnel"
                type="number"
                min={0}
                max={99}
                value={personnel}
                disabled={busy}
                onChange={(event) => setPersonnel(Number(event.target.value))}
              />
              <Button type="submit" disabled={busy || !trimmed}>
                Add
              </Button>
            </Actions>
          </Field>
        </Form>
      </Section>
    </Modal>
  );
}

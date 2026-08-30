import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import type { Incident, Team, Tracker, UnregisteredNode } from "../../api";
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
  Select,
  TextInput,
} from "../../components/ui";
import { useAsyncAction } from "../../hooks/useAsyncAction";
import { useNow } from "../../hooks/useNow";
import { formatAge } from "../../lib/format";
import styles from "./TrackersModal.module.css";

const AGE_TICK_MS = 10_000;

/** Assign an unassigned tracker to a team, for the incident under way. */
function AssignControl({
  nodeId,
  teams,
  disabled,
  onAssign,
}: {
  nodeId: string;
  teams: Team[];
  disabled: boolean;
  onAssign: (teamId: string) => void;
}) {
  const [teamId, setTeamId] = useState("");

  return (
    <div className={styles.assign}>
      <Select
        aria-label={`Assign ${nodeId} to a team`}
        value={teamId}
        disabled={disabled}
        onChange={(event) => setTeamId(event.target.value)}
      >
        <option value="">Assign to…</option>
        {teams.map((team) => (
          <option key={team.id} value={team.id}>
            {team.name}
          </option>
        ))}
      </Select>
      <Button
        variant="link"
        disabled={disabled || !teamId}
        onClick={() => onAssign(teamId)}
      >
        Assign
      </Button>
    </div>
  );
}

/** Describes what a tracker is currently committed to, for its meta line. */
function assignmentSummary(tracker: Tracker): string {
  const { assignment } = tracker;
  if (!assignment) return " · Unassigned";

  const team = assignment.team_name ?? "Assigned";
  return assignment.incident_name
    ? ` · ${team} · ${assignment.incident_name}`
    : ` · ${team}`;
}

export function TrackersModal({
  open,
  incident,
  onClose,
  onChanged,
}: {
  open: boolean;
  // Assignments belong to an incident, so there is nothing to assign to
  // until one is running.
  incident: Incident | null;
  onClose: () => void;
  // Trackers feed the map and the sidebar, so a change here has to reach them.
  onChanged: () => void;
}) {
  const [trackers, setTrackers] = useState<Tracker[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [heard, setHeard] = useState<UnregisteredNode[]>([]);
  const [nodeId, setNodeId] = useState("");
  const [label, setLabel] = useState("");
  const { busy, error, fail, run } = useAsyncAction();
  const now = useNow(AGE_TICK_MS);

  const load = useCallback(() => {
    Promise.all([api.trackers(), api.unregisteredNodes(), api.teams()])
      .then(([list, nodes, teamList]) => {
        setTrackers(list);
        setHeard(nodes);
        setTeams(teamList);
      })
      .catch(fail);
  }, [fail]);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  // Every mutation here reshapes the same three lists, and the map and sidebar
  // read from the same records, so both are refreshed rather than patched.
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

  const trimmedId = nodeId.trim();
  const trimmedLabel = label.trim();

  return (
    <Modal open={open} title="Trackers" onClose={onClose} size="md">
      <ErrorMessage error={error} />

      <Section title="Registered" count={trackers.length}>
        {trackers.length === 0 && (
          <Message tone="empty">
            No trackers yet. Add one below to start assigning it to a team.
          </Message>
        )}

        <List>
          {trackers.map((tracker) => (
            <ListItem key={tracker.node_id}>
              <Row>
                <Name>{tracker.label}</Name>
                <Button
                  variant="link"
                  danger
                  // A tracker a team is carrying cannot be deleted: its
                  // positions would stop being attributed to anyone mid-search.
                  disabled={busy || tracker.assignment !== null}
                  title={
                    tracker.assignment
                      ? `Assigned to ${tracker.assignment.team_name ?? "a team"}`
                      : "Delete this tracker"
                  }
                  onClick={() =>
                    mutate(() => api.deleteTracker(tracker.node_id))
                  }
                >
                  Delete
                </Button>
              </Row>
              <Meta>
                <code>{tracker.node_id}</code>
                {assignmentSummary(tracker)}
              </Meta>

              {tracker.assignment ? (
                <div className={styles.assign}>
                  <Button
                    variant="link"
                    disabled={busy}
                    onClick={() => mutate(() => api.unassign(tracker.node_id))}
                  >
                    Unassign
                  </Button>
                </div>
              ) : (
                // Only offered with an incident to assign against and a team
                // to assign to; the reason is spelled out below the list
                // rather than left as a control that does nothing.
                incident !== null &&
                teams.length > 0 && (
                  <AssignControl
                    nodeId={tracker.node_id}
                    teams={teams}
                    disabled={busy}
                    onAssign={(teamId) =>
                      mutate(() =>
                        api.assign(incident.id, tracker.node_id, teamId),
                      )
                    }
                  />
                )
              )}
            </ListItem>
          ))}
        </List>

        {/* Both are preconditions for assigning, and neither is obvious from
            a row that simply has no control on it. */}
        {trackers.length > 0 && incident === null && (
          <Message>Start an incident to assign trackers to teams.</Message>
        )}

        {trackers.length > 0 && incident !== null && teams.length === 0 && (
          <Message>Add a team before assigning trackers.</Message>
        )}
      </Section>

      <Section title="Add a tracker">
        {heard.length > 0 && (
          <>
            <Message>
              Heard on the mesh but not registered. Pick one to fill in its ID.
            </Message>
            <List>
              {heard.map((node) => (
                <ListItem key={node.node_id}>
                  <Row>
                    <code>{node.node_id}</code>
                    <Button
                      variant="link"
                      disabled={busy}
                      onClick={() => setNodeId(node.node_id)}
                    >
                      Use
                    </Button>
                  </Row>
                  <Meta>
                    Last heard {formatAge(node.last_seen_at, now)} ago
                  </Meta>
                </ListItem>
              ))}
            </List>
          </>
        )}

        <Form
          onSubmit={() => {
            if (!trimmedId || !trimmedLabel) return;

            mutate(
              () => api.createTracker(trimmedId, trimmedLabel),
              () => {
                setNodeId("");
                setLabel("");
              },
            );
          }}
        >
          <Field label="Node ID" htmlFor="tracker-node-id">
            <TextInput
              id="tracker-node-id"
              placeholder="!a1b2c3d4"
              value={nodeId}
              disabled={busy}
              full
              onChange={(event) => setNodeId(event.target.value)}
            />
          </Field>

          <Field label="Label" htmlFor="tracker-label">
            <Actions>
              <TextInput
                id="tracker-label"
                placeholder="Team 2 radio"
                value={label}
                disabled={busy}
                onChange={(event) => setLabel(event.target.value)}
              />
              <Button
                type="submit"
                disabled={busy || !trimmedId || !trimmedLabel}
              >
                Add
              </Button>
            </Actions>
          </Field>
        </Form>
      </Section>
    </Modal>
  );
}

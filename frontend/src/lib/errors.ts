/**
 * The operator-facing text for a thrown value.
 *
 * `String(error)` would prefix the class name -- "TypeError: Failed to fetch"
 * -- which is noise to someone reading a message in a field laptop's sidebar.
 */
export function toMessage(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause);
}

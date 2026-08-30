import type { ReactNode } from "react";
import { cx } from "../../lib/cx";
import styles from "./Message.module.css";

/**
 * A line of prose under a heading or a list.
 *
 * "error" is a failure the operator has to act on; the others are quieter --
 * "empty" for a list with nothing in it, "note" for a standing explanation.
 */
export function Message({
  tone = "note",
  className,
  children,
}: {
  tone?: "error" | "note" | "empty";
  className?: string;
  children: ReactNode;
}) {
  return (
    <p
      className={cx(
        styles.message,
        tone === "error" && styles.error,
        className,
      )}
    >
      {children}
    </p>
  );
}

/** Renders nothing when there is no error, which is the common case. */
export function ErrorMessage({ error }: { error: string | null }) {
  if (!error) return null;

  return <Message tone="error">{error}</Message>;
}

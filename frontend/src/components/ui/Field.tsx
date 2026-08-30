import type { ReactNode } from "react";
import { cx } from "../../lib/cx";
import styles from "./Field.module.css";

/**
 * A group of fields submitted together.
 *
 * Always a real <form>, so Enter submits from any input inside it rather than
 * only from the one that happens to sit beside the button.
 */
export function Form({
  onSubmit,
  className,
  children,
}: {
  onSubmit: () => void;
  className?: string;
  children: ReactNode;
}) {
  return (
    <form
      className={className}
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      {children}
    </form>
  );
}

/** A labelled control. Wrap one or more in a Form to make Enter submit. */
export function Field({
  label,
  htmlFor,
  className,
  children,
}: {
  label: string;
  /** Omit only when the label describes a group rather than one control. */
  htmlFor?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cx(styles.field, className)}>
      <label htmlFor={htmlFor}>{label}</label>
      {children}
    </div>
  );
}

/** A horizontal run of controls -- input plus button, progress plus cancel. */
export function Actions({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <div className={cx(styles.actions, className)}>{children}</div>;
}

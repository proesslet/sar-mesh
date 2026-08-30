import type { ReactNode } from "react";
import { cx } from "../../lib/cx";
import styles from "./List.module.css";

/** A rule-separated list of records -- trackers, teams, map packs, nodes. */
export function List({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <ul className={cx(styles.list, className)}>{children}</ul>;
}

export function ListItem({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <li className={cx(styles.item, className)}>{children}</li>;
}

/** The top line of an item: what it is on the left, what to do with it right. */
export function Row({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <div className={cx(styles.row, className)}>{children}</div>;
}

/** The emphasised name within a Row. */
export function Name({ children }: { children: ReactNode }) {
  return <span className={styles.name}>{children}</span>;
}

/** The quiet second line: ids, counts, timestamps, assignment state. */
export function Meta({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <div className={cx(styles.meta, className)}>{children}</div>;
}

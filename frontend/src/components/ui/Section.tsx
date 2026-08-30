import type { ReactNode } from "react";
import { cx } from "../../lib/cx";
import styles from "./Section.module.css";

/** A titled block of a dialog, separated from its neighbours by a rule. */
export function Section({
  title,
  count,
  className,
  children,
}: {
  title: string;
  /** Shown beside the title, for a section headed by a list. */
  count?: number;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={cx(styles.section, className)}>
      <h3>
        {title}
        {count != null && <span className={styles.count}> {count}</span>}
      </h3>
      {children}
    </section>
  );
}

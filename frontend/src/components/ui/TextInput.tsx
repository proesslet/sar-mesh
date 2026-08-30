import type { InputHTMLAttributes, SelectHTMLAttributes } from "react";
import { cx } from "../../lib/cx";
import styles from "./TextInput.module.css";

type TextInputProps = InputHTMLAttributes<HTMLInputElement> & {
  /** Fills its line. Numeric inputs stay narrow, so this is off by default. */
  full?: boolean;
};

export function TextInput({ full, className, type, ...rest }: TextInputProps) {
  return (
    <input
      type={type}
      className={cx(
        styles.input,
        type === "number" ? styles.number : full && styles.full,
        className,
      )}
      {...rest}
    />
  );
}

export function Select({
  className,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cx(styles.input, styles.select, className)} {...rest} />
  );
}

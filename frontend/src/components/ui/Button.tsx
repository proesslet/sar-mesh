import type { ButtonHTMLAttributes } from "react";
import { cx } from "../../lib/cx";
import styles from "./Button.module.css";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  /** "link" for an inline control that must not outweigh the text beside it. */
  variant?: "outline" | "link";
  /** Colours the hover state red, for actions that destroy something. */
  danger?: boolean;
  /** Stretches to fill its container. */
  block?: boolean;
};

/**
 * Every button in the app.
 *
 * `type` defaults to "button": a bare <button> inside a <form> submits it, and
 * an action button that silently submits its form is a genuinely confusing bug.
 */
export function Button({
  variant = "outline",
  danger,
  block,
  className,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cx(
        variant === "link" ? styles.link : styles.button,
        danger && styles.danger,
        block && styles.block,
        className,
      )}
      {...rest}
    />
  );
}

import type { ReactNode } from "react";

import styles from "./components.module.css";
import "./tokens.module.css";

export type ButtonProps = {
  label: string;
  variant: "solid" | "subtle" | "outline";
  size: "compact" | "regular";
  radius: "square" | "soft" | "pill";
  density: "compact" | "comfortable";
  background: "accent" | "surface" | "transparent";
  foreground: "light" | "dark";
  border: "none" | "subtle" | "strong";
  fontWeight: "regular" | "semibold";
  state: "default" | "disabled" | "loading";
};

export type InputProps = {
  label: string;
  placeholder: string;
  value: string;
  tone: "quiet" | "strong";
  state: "default" | "disabled";
};

export type BadgeProps = {
  label: string;
  tone: "neutral" | "accent" | "success";
};

export type CardProps = {
  title: string;
  description: string;
  emphasis: "quiet" | "raised";
};

export function Button(props: ButtonProps) {
  const isLoading = props.state === "loading";
  const isDisabled = props.state !== "default";

  return (
    <button
      aria-busy={isLoading || undefined}
      className={styles.button}
      data-background={props.background}
      data-border={props.border}
      data-density={props.density}
      data-font-weight={props.fontWeight}
      data-foreground={props.foreground}
      data-radius={props.radius}
      data-size={props.size}
      data-variant={props.variant}
      disabled={isDisabled}
      type="button"
    >
      {isLoading ? "Loading…" : props.label}
    </button>
  );
}

export function Input(props: InputProps) {
  return (
    <label className={styles.inputField}>
      <span className={styles.inputLabel}>{props.label}</span>
      <input
        className={styles.input}
        data-tone={props.tone}
        defaultValue={props.value}
        disabled={props.state === "disabled"}
        placeholder={props.placeholder}
      />
    </label>
  );
}

export function Badge(props: BadgeProps) {
  return (
    <span className={styles.badge} data-tone={props.tone}>
      {props.label}
    </span>
  );
}

export function Card({ children, ...props }: CardProps & { children?: ReactNode }) {
  return (
    <section aria-label={props.title} className={styles.card} data-emphasis={props.emphasis}>
      <header className={styles.cardHeader}>
        <h2 className={styles.cardTitle}>{props.title}</h2>
        <p className={styles.cardDescription}>{props.description}</p>
      </header>
      {children}
    </section>
  );
}

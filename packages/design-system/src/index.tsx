import type { ReactNode } from "react";

import styles from "./components.module.css";
import "./tokens.module.css";

export type ButtonProps = {
  content: { label: string };
  semantic: { role: "primary-action" | "secondary-action"; state: "default" | "disabled" | "loading" };
  appearance: {
    recipe: "primary" | "secondary" | "outline" | "ghost";
    size: "compact" | "regular";
    radius: "square" | "soft" | "pill";
    density: "compact" | "comfortable";
    fontWeight: "regular" | "semibold";
  };
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

export type FormFieldProps = {
  label: string;
  hint?: string | null;
  appearance: {
    labelPlacement: "above" | "inline";
    gap: "tight" | "regular" | "loose";
    hintTone: "quiet" | "strong";
  };
};

export type SettingsFormProps = {
  title: string;
  description: string;
};

export type SettingsTemplateProps = {
  title: string;
};

export type ProjectSettingsPageProps = {
  title: string;
};

export function Button(props: ButtonProps) {
  const isLoading = props.semantic.state === "loading";
  const isDisabled = props.semantic.state !== "default";

  return (
    <button
      aria-busy={isLoading || undefined}
      className={styles.button}
      data-density={props.appearance.density}
      data-font-weight={props.appearance.fontWeight}
      data-radius={props.appearance.radius}
      data-recipe={props.appearance.recipe}
      data-role={props.semantic.role}
      data-size={props.appearance.size}
      disabled={isDisabled}
      type="button"
    >
      {isLoading ? "Loading…" : props.content.label}
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

export function FormField({ appearance, children, hint, label }: FormFieldProps & { children?: ReactNode }) {
  return (
    <section
      aria-label={label}
      className={styles.formField}
      data-gap={appearance.gap}
      data-label-placement={appearance.labelPlacement}
    >
      <div className={styles.formFieldHeader}>
        <strong>{label}</strong>
        {hint ? <p data-hint-tone={appearance.hintTone}>{hint}</p> : null}
      </div>
      {children}
    </section>
  );
}

export function SettingsForm({ children, ...props }: SettingsFormProps & { children?: ReactNode }) {
  return (
    <section aria-label={props.title} className={styles.settingsForm}>
      <header className={styles.settingsFormHeader}>
        <h2>{props.title}</h2>
        <p>{props.description}</p>
      </header>
      {children}
    </section>
  );
}

export function SettingsTemplate({ children, title }: SettingsTemplateProps & { children?: ReactNode }) {
  return (
    <div className={styles.settingsTemplate}>
      <header><h1>{title}</h1></header>
      {children}
    </div>
  );
}

export function ProjectSettingsPage({ children, title }: ProjectSettingsPageProps & { children?: ReactNode }) {
  return <main aria-label={title} className={styles.projectSettingsPage}>{children}</main>;
}

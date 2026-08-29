"use client";

import { markDevtoolsActive } from "@json-render/core";
import { buttonFixtureSpec, ControlledRenderer } from "@itl/ui-catalog";
import { type MouseEvent, type ReactNode, useEffect, useMemo, useState } from "react";

import {
  type ButtonPath,
  type ButtonToken,
  type DesignContext,
  type Interpretation,
  type RefineVariant,
  buttonTokenValues,
  emptyInterpretation,
  isButtonSpec,
  setButtonToken,
  updateInterpretation,
} from "../refine/refine-engine";
import { recordPreferenceEvent } from "../refine/memory-client";
import { generateVariants as requestVariants, parseCritique } from "../refine/refine-client";

import styles from "./controlled-canvas.module.css";

const contexts: Record<"toolbar" | "hero" | "form", DesignContext> = {
  toolbar: { role: "secondary-action", surface: "toolbar", density: "compact" },
  hero: { role: "primary-action", surface: "hero", density: "comfortable" },
  form: { role: "primary-action", surface: "form", density: "comfortable" },
};

export function ControlledCanvas() {
  const [currentSpec, setCurrentSpec] = useState(buttonFixtureSpec);
  const [surface, setSurface] = useState<keyof typeof contexts>("hero");
  const [selectedElementId, setSelectedElementId] = useState("continue-button");
  const [reaction, setReaction] = useState("quase");
  const [critique, setCritique] = useState("");
  const [interpretation, setInterpretation] = useState<Interpretation | null>(null);
  const [variants, setVariants] = useState<RefineVariant[]>([]);
  const [status, setStatus] = useState("Select a Button and describe what to retain or explore.");
  const [memoryEvents, setMemoryEvents] = useState(0);
  const context = contexts[surface];

  useEffect(() => markDevtoolsActive(), []);

  const selectedIsButton = isButtonSpec(currentSpec, selectedElementId);
  const selectedButton = useMemo(
    () => (selectedIsButton ? currentSpec.elements[selectedElementId] : undefined),
    [currentSpec, selectedElementId, selectedIsButton],
  );

  async function interpretCritique() {
    if (!selectedIsButton) {
      setStatus("Select a Button before submitting feedback.");
      return;
    }
    try {
      const parsed = await parseCritique({ spec: currentSpec, targetElementId: selectedElementId, critique });
      setInterpretation(parsed);
      setVariants([]);
      setStatus("Review the visual directives. Nothing has been stored yet.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "The critique could not be interpreted.");
    }
  }

  async function generateCandidates(includeWild = false) {
    if (!interpretation) return;
    try {
      if (!includeWild) {
        recordEvent({
          action: "confirmed_critique",
          source: "confirmed_critique",
          beforeSpec: currentSpec,
          targetElementId: selectedElementId,
          critique,
          interpretation,
        });
      }
      const next = await requestVariants({
        spec: currentSpec,
        targetElementId: selectedElementId,
        interpretation,
        includeWild,
        context,
      });
      setVariants(next);
      setStatus(
        includeWild ? "An opt-in recipe-centroid exploration was added." : "Constrained alternatives are ready.",
      );
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "The current spec was retained.");
    }
  }

  function editToken(token: ButtonToken, value: string) {
    if (!selectedIsButton) return;
    const nextSpec = setButtonToken(currentSpec, selectedElementId, token, value);
    setCurrentSpec(nextSpec);
    setInterpretation((current) =>
      updateInterpretation(current ?? emptyInterpretation(selectedElementId), "keep", `/appearance/${token}`, true),
    );
    setVariants([]);
    recordEvent({
      action: "manual_edit",
      source: "manual_edit",
      beforeSpec: currentSpec,
      afterSpec: nextSpec,
      targetElementId: selectedElementId,
      evidence: {
        likedPaths: [`/appearance/${token}`],
        dislikedPaths: [],
        lockedPaths: [`/appearance/${token}`],
        strength: "strong",
      },
      directives: [{ kind: "keep", path: `/appearance/${token}` }],
    });
    setStatus(`${token} was directly edited and is now strong Keep evidence.`);
  }

  function recordEvent(input: Omit<Parameters<typeof recordPreferenceEvent>[0], "context">) {
    void recordPreferenceEvent({ ...input, context }).then((recorded) => {
      setMemoryEvents((count) => count + Number(recorded));
    });
  }

  return (
    <main className={styles.canvas} onClick={selectElement(setSelectedElementId)}>
      <div className={styles.workbench}>
        <section
          aria-label="Button context"
          className={styles.contextPicker}
          onClick={(event) => event.stopPropagation()}
        >
          <span>Session context</span>
          {Object.keys(contexts).map((name) => (
            <button
              aria-pressed={surface === name}
              key={name}
              onClick={() => setSurface(name as keyof typeof contexts)}
              type="button"
            >
              {name}
            </button>
          ))}
        </section>
        <ContextSurface surface={surface}>
          <ControlledRenderer spec={currentSpec} />
        </ContextSurface>
        <p aria-live="polite" className={styles.selection} data-testid="selected-element">
          Selected element: {selectedElementId}
        </p>
        <p aria-live="polite" className={styles.status} data-testid="refine-status">{status}</p>
        <aside aria-label="Preference memory" className={styles.notice}>
          Preference memory: {memoryEvents} explicit action{memoryEvents === 1 ? "" : "s"} stored locally when the API is running.
        </aside>

        {selectedIsButton && selectedButton?.type === "Button" ? (
          <section aria-label="Button critique" className={styles.panel} onClick={(event) => event.stopPropagation()}>
            <h1>Refine this Button</h1>
            <p>Feedback can change only visual appearance; its label, role, and state are not taste dimensions.</p>
            <div aria-label="Absolute feedback" className={styles.reactions}>
              {["gosto", "quase", "indiferente", "não gosto"].map((value) => (
                <button
                  aria-pressed={reaction === value}
                  className={styles.reaction}
                  key={value}
                  onClick={() => {
                    setReaction(value);
                    recordEvent({
                      action: value === "indiferente" ? "indifference" : "absolute_feedback",
                      source: "absolute_feedback",
                      beforeSpec: currentSpec,
                      targetElementId: selectedElementId,
                      critique: value,
                    });
                  }}
                  type="button"
                >
                  {value}
                </button>
              ))}
            </div>
            <label className={styles.textLabel}>
              Optional critique
              <textarea
                onChange={(event) => setCritique(event.target.value)}
                placeholder="I like the recipe and spacing, but it is too rounded."
                value={critique}
              />
            </label>
            <button className={styles.primaryAction} onClick={() => void interpretCritique()} type="button">
              Review interpretation
            </button>
            <fieldset className={styles.inspector}>
              <legend>Direct visual editor</legend>
              <p>Recipes derive background, border, hover, and focus tokens together.</p>
              {Object.entries(buttonTokenValues).map(([token, values]) => (
                <label key={token}>
                  {token}
                  <select
                    aria-label={`Edit ${token}`}
                    onChange={(event) => editToken(token as ButtonToken, event.target.value)}
                    value={selectedButton.props.appearance[token as ButtonToken]}
                  >
                    {values.map((value) => <option key={value} value={value}>{value}</option>)}
                  </select>
                </label>
              ))}
            </fieldset>
          </section>
        ) : (
          <p className={styles.notice}>Select the Button to refine it. This laboratory edits one component only.</p>
        )}

        {interpretation ? (
          <InterpretationReview
            interpretation={interpretation}
            onChange={setInterpretation}
            onConfirm={() => void generateCandidates()}
          />
        ) : null}
        {variants.length > 0 ? (
          <section
            aria-label="Constrained alternatives"
            className={styles.variants}
            onClick={(event) => event.stopPropagation()}
          >
            <div className={styles.variantsHeading}>
              <h2>Constrained alternatives</h2>
              {!variants.some((variant) => variant.kind === "wild_explore") ? (
                <button onClick={() => void generateCandidates(true)} type="button">Explore recipe centroid</button>
              ) : null}
            </div>
            <div className={styles.variantGrid}>
              {variants.map((variant) => (
                <VariantCard
                  key={variant.id}
                  variant={variant}
                  onAccept={() => {
                    recordEvent({
                      action: "candidate_acceptance",
                      source: "candidate_acceptance",
                      beforeSpec: currentSpec,
                      afterSpec: variant.spec,
                      targetElementId: selectedElementId,
                      selectedElementId,
                      candidateId: variant.id,
                      interpretation,
                    });
                    setCurrentSpec(variant.spec);
                    setVariants([]);
                    setStatus(`${variant.kind} was accepted.`);
                  }}
                  onEvidence={(label) => {
                    recordEvent({
                      action: label === "Indifference" ? "indifference" : "explicit_attribute_feedback",
                      source: label === "Indifference" ? "absolute_feedback" : "explicit_attribute_feedback",
                      beforeSpec: currentSpec,
                      targetElementId: selectedElementId,
                      selectedElementId,
                      candidateId: variant.id,
                      interpretation,
                    });
                    setStatus(`${label} was stored for ${variant.kind}; no winner was assumed.`);
                  }}
                />
              ))}
            </div>
            <button
              className={styles.rejectAll}
              onClick={() => {
                recordEvent({
                  action: "rejection",
                  source: "absolute_feedback",
                  beforeSpec: currentSpec,
                  targetElementId: selectedElementId,
                  interpretation,
                });
                setVariants([]);
                setStatus("None of these was recorded. No option was selected as a winner.");
              }}
              type="button"
            >
              Reject all
            </button>
          </section>
        ) : null}
      </div>
    </main>
  );
}

function ContextSurface({ children, surface }: { children: ReactNode; surface: keyof typeof contexts }) {
  return (
    <section aria-label={`${surface} Button surface`} className={`${styles.currentSpec} ${styles[surface]}`}>
      {surface === "toolbar" ? <span>Project settings</span> : null}
      {surface === "hero" ? <div><p>Make each interaction intentional.</p><h2>Build a calmer workflow</h2></div> : null}
      {surface === "form" ? <label>Email address<input placeholder="you@example.com" type="email" /></label> : null}
      {children}
    </section>
  );
}

function InterpretationReview({ interpretation, onChange, onConfirm }: {
  interpretation: Interpretation;
  onChange: (interpretation: Interpretation) => void;
  onConfirm: () => void;
}) {
  const paths = Object.keys(buttonTokenValues).map((token) => `/appearance/${token}` as ButtonPath);
  const selected = (kind: "keep" | "explore") => interpretation.directives
    .filter((directive) => directive.kind === kind)
    .map((directive) => directive.path);
  return (
    <section aria-label="Review refinement interpretation" className={styles.intentReview}>
      <h2>Confirm interpretation</h2>
      <p>{interpretation.rationale}</p>
      {interpretation.ambiguity.map((message) => <p className={styles.notice} key={message}>{message}</p>)}
      <div className={styles.intentColumns}>
        <TokenChecklist
          heading="Keep"
          paths={paths}
          selected={selected("keep")}
          onChange={(path, checked) => onChange(updateInterpretation(interpretation, "keep", path, checked))}
        />
        <TokenChecklist
          heading="Explore"
          paths={paths}
          selected={selected("explore")}
          onChange={(path, checked) => onChange(updateInterpretation(interpretation, "explore", path, checked))}
        />
      </div>
      <button className={styles.primaryAction} onClick={onConfirm} type="button">
        Generate constrained alternatives
      </button>
    </section>
  );
}

function TokenChecklist({ heading, paths, selected, onChange }: {
  heading: string;
  paths: ButtonPath[];
  selected: ButtonPath[];
  onChange: (path: ButtonPath, checked: boolean) => void;
}) {
  return (
    <fieldset className={styles.tokenChecklist}>
      <legend>{heading}</legend>
      {paths.map((path) => (
        <label key={path}>
          <input checked={selected.includes(path)} onChange={(event) => onChange(path, event.target.checked)} type="checkbox" />
          {path.replace("/appearance/", "")}
        </label>
      ))}
    </fieldset>
  );
}

function VariantCard({ variant, onAccept, onEvidence }: {
  variant: RefineVariant;
  onAccept: () => void;
  onEvidence: (evidence: "Almost" | "Indifference") => void;
}) {
  return (
    <article className={styles.variant}>
      <p className={styles.variantKind}>{variant.kind.replaceAll("_", " ")}: {variant.direction}</p>
      <ControlledRenderer spec={variant.spec} />
      <div className={styles.variantActions}>
        <button onClick={onAccept} type="button">Accept</button>
        <button onClick={() => onEvidence("Almost")} type="button">Almost</button>
        <button onClick={() => onEvidence("Indifference")} type="button">Indifferent</button>
      </div>
    </article>
  );
}

function selectElement(setSelectedElementId: (elementId: string) => void) {
  return (event: MouseEvent<HTMLElement>) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const elementId = target.closest<HTMLElement>("[data-jr-key]")?.dataset.jrKey;
    if (elementId) setSelectedElementId(elementId);
  };
}

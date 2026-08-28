"use client";

import { markDevtoolsActive } from "@json-render/core";
import { ControlledRenderer, fixtureSpec } from "@itl/ui-catalog";
import { type MouseEvent, useEffect, useState } from "react";

import {
  type ButtonPath,
  type ButtonToken,
  type PatchIntent,
  type RefineVariant,
  buttonTokenValues,
  createLocalVariants,
  isButtonSpec,
  parseCritiqueLocally,
  setButtonToken,
  updateIntent,
} from "../refine/refine-engine";

import styles from "./controlled-canvas.module.css";

export function ControlledCanvas() {
  const [currentSpec, setCurrentSpec] = useState(fixtureSpec);
  const [selectedElementId, setSelectedElementId] = useState("continue-button");
  const [reaction, setReaction] = useState("quase");
  const [critique, setCritique] = useState("");
  const [intent, setIntent] = useState<PatchIntent | null>(null);
  const [variants, setVariants] = useState<RefineVariant[]>([]);
  const [status, setStatus] = useState("Select a Button and describe what to retain or explore.");

  useEffect(() => markDevtoolsActive(), []);

  const selectedIsButton = isButtonSpec(currentSpec, selectedElementId);
  const selectedButton = selectedIsButton ? currentSpec.elements[selectedElementId] : undefined;

  function interpretCritique() {
    if (!selectedIsButton) {
      setStatus("Select a Button before submitting feedback.");
      return;
    }
    setIntent(parseCritiqueLocally(critique, selectedElementId));
    setVariants([]);
    setStatus("Review the proposed Keep and Explore tokens before generating alternatives.");
  }

  function generateVariants(includeWild = false) {
    if (!intent) return;
    try {
      setVariants(createLocalVariants(currentSpec, intent, includeWild));
      setStatus(includeWild ? "A directed wild exploration was added." : "Constrained alternatives are ready for review.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "The current spec was retained.");
    }
  }

  function editToken(token: ButtonToken, value: string) {
    if (!selectedIsButton) return;
    setCurrentSpec((spec) => setButtonToken(spec, selectedElementId, token, value));
    setIntent((current) => {
      const base = current ?? parseCritiqueLocally("", selectedElementId);
      return updateIntent(base, "lockedPaths", `/props/${token}` as ButtonPath, true);
    });
    setVariants([]);
    setStatus(`${token} was directly edited and is now stronger Keep evidence.`);
  }

  return (
    <main className={styles.canvas} onClick={selectElement(setSelectedElementId)}>
      <div className={styles.workbench}>
        <section aria-label="Current controlled component" className={styles.currentSpec}>
          <ControlledRenderer spec={currentSpec} />
        </section>
        <p aria-live="polite" className={styles.selection} data-testid="selected-element">
          Selected element: {selectedElementId}
        </p>
        <p aria-live="polite" className={styles.status} data-testid="refine-status">{status}</p>

        {selectedIsButton && selectedButton?.type === "Button" ? (
          <section aria-label="Button critique" className={styles.panel} onClick={(event) => event.stopPropagation()}>
            <h1>Refine this Button</h1>
            <p>Use an absolute reaction, then say what should stay or change.</p>
            <div aria-label="Absolute feedback" className={styles.reactions}>
              {[
                ["gosto", "Gosto"],
                ["quase", "Quase"],
                ["indiferente", "Indiferente"],
                ["não gosto", "Não gosto"],
              ].map(([value, label]) => (
                <button aria-pressed={reaction === value} className={styles.reaction} key={value} onClick={() => setReaction(value)} type="button">
                  {label}
                </button>
              ))}
            </div>
            <label className={styles.textLabel}>
              Optional critique
              <textarea onChange={(event) => setCritique(event.target.value)} placeholder="I like the color and spacing, but it is too rounded." value={critique} />
            </label>
            <button className={styles.primaryAction} onClick={interpretCritique} type="button">Review interpretation</button>

            <fieldset className={styles.inspector}>
              <legend>Direct token editor</legend>
              <p>Direct edits are stronger evidence than an inferred critique.</p>
              {Object.entries(buttonTokenValues).map(([token, values]) => (
                <label key={token}>
                  {token}
                  <select aria-label={`Edit ${token}`} onChange={(event) => editToken(token as ButtonToken, event.target.value)} value={selectedButton.props[token as ButtonToken]}>
                    {values.map((value) => <option key={value} value={value}>{value}</option>)}
                  </select>
                </label>
              ))}
            </fieldset>
          </section>
        ) : (
          <p className={styles.notice}>Select the Button to refine it. This phase does not edit nested elements.</p>
        )}

        {intent ? <IntentReview intent={intent} onChange={setIntent} onConfirm={() => generateVariants()} /> : null}
        {variants.length > 0 ? (
          <section aria-label="Constrained alternatives" className={styles.variants} onClick={(event) => event.stopPropagation()}>
            <div className={styles.variantsHeading}>
              <h2>Constrained alternatives</h2>
              {!variants.some((variant) => variant.kind === "wild_explore") ? <button onClick={() => generateVariants(true)} type="button">Explore this direction</button> : null}
            </div>
            <div className={styles.variantGrid}>
              {variants.map((variant) => <VariantCard key={variant.id} variant={variant} onAccept={() => { setCurrentSpec(variant.spec); setVariants([]); setStatus(`${variant.kind} was accepted.`); }} onEvidence={(evidence) => setStatus(`${evidence} was recorded for ${variant.kind}; no winner was assumed.`)} />)}
            </div>
            <button className={styles.rejectAll} onClick={() => { setVariants([]); setStatus("None of these was recorded. No option was selected as a winner."); }} type="button">Reject all</button>
          </section>
        ) : null}
      </div>
    </main>
  );
}

function IntentReview({ intent, onChange, onConfirm }: { intent: PatchIntent; onChange: (intent: PatchIntent) => void; onConfirm: () => void }) {
  const paths = Object.keys(buttonTokenValues).map((token) => `/props/${token}` as ButtonPath);
  return (
    <section aria-label="Review refinement intent" className={styles.intentReview}>
      <h2>Confirm interpretation</h2>
      <p>{intent.rationale}</p>
      {intent.ambiguity.map((message) => <p className={styles.notice} key={message}>{message}</p>)}
      <div className={styles.intentColumns}>
        <TokenChecklist heading="Keep" paths={paths} selected={intent.lockedPaths} onChange={(path, checked) => onChange(updateIntent(intent, "lockedPaths", path, checked))} />
        <TokenChecklist heading="Explore" paths={paths} selected={intent.explorationPaths} onChange={(path, checked) => onChange(updateIntent(intent, "explorationPaths", path, checked))} />
      </div>
      <button className={styles.primaryAction} onClick={onConfirm} type="button">Generate constrained alternatives</button>
    </section>
  );
}

function TokenChecklist({ heading, paths, selected, onChange }: { heading: string; paths: ButtonPath[]; selected: ButtonPath[]; onChange: (path: ButtonPath, checked: boolean) => void }) {
  return <fieldset className={styles.tokenChecklist}><legend>{heading}</legend>{paths.map((path) => <label key={path}><input checked={selected.includes(path)} onChange={(event) => onChange(path, event.target.checked)} type="checkbox" />{path.replace("/props/", "")}</label>)}</fieldset>;
}

function VariantCard({ variant, onAccept, onEvidence }: { variant: RefineVariant; onAccept: () => void; onEvidence: (evidence: string) => void }) {
  return (
    <article className={styles.variant}>
      <p className={styles.variantKind}>{variant.kind.replace("_", " ")}</p>
      <ControlledRenderer spec={variant.spec} />
      <div className={styles.variantActions}>
        <button onClick={onAccept} type="button">Accept</button>
        <button onClick={() => onEvidence("Almost")} type="button">Almost</button>
        <button onClick={() => onEvidence("Indifference")} type="button">Indifferent</button>
        <button onClick={() => onEvidence("Mix request")} type="button">Mix</button>
      </div>
    </article>
  );
}

function selectElement(setSelectedElementId: (elementId: string) => void) {
  return (event: MouseEvent<HTMLElement>) => {
    const target = event.target;
    if (!(target instanceof Element)) return;

    const element = target.closest<HTMLElement>("[data-jr-key]");
    const elementId = element?.dataset.jrKey;
    if (elementId) setSelectedElementId(elementId);
  };
}

"use client";

import { markDevtoolsActive } from "@json-render/core";
import { buttonFixtureSpec, ControlledRenderer } from "@itl/ui-catalog";
import { type MouseEvent, type ReactNode, useEffect, useMemo, useState } from "react";

import { messages as localizedMessages, type Locale, type Messages } from "@/i18n/messages";

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

export function ControlledCanvas({ locale }: { locale: Locale }) {
  const messages = localizedMessages[locale];
  const [currentSpec, setCurrentSpec] = useState(buttonFixtureSpec);
  const [surface, setSurface] = useState<keyof typeof contexts>("hero");
  const [selectedElementId, setSelectedElementId] = useState("continue-button");
  const [reaction, setReaction] = useState("1");
  const [critique, setCritique] = useState("");
  const [interpretation, setInterpretation] = useState<Interpretation | null>(null);
  const [variants, setVariants] = useState<RefineVariant[]>([]);
  const [isParsingCritique, setIsParsingCritique] = useState(false);
  const [isGeneratingVariants, setIsGeneratingVariants] = useState(false);
  const [status, setStatus] = useState(messages.selectButton);
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
      setStatus(messages.selectButton);
      return;
    }
    const trimmedCritique = critique.trim();
    if (!trimmedCritique) {
      setStatus(messages.emptyCritique);
      return;
    }
    setIsParsingCritique(true);
    try {
      const parsed = await parseCritique({
        spec: currentSpec,
        targetElementId: selectedElementId,
        critique: trimmedCritique,
      });
      setInterpretation(reviewableInterpretation(parsed));
      setVariants([]);
      setStatus(messages.parsed);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "The critique could not be interpreted.");
    } finally {
      setIsParsingCritique(false);
    }
  }

  async function generateCandidates(includeWild = false) {
    if (!interpretation || isGeneratingVariants) return;
    setIsGeneratingVariants(true);
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
        includeWild ? messages.wildCandidatesReady : messages.candidatesReady,
      );
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "The current spec was retained.");
    } finally {
      setIsGeneratingVariants(false);
    }
  }

  function editToken(token: ButtonToken, value: string) {
    if (!selectedIsButton) return;
    const nextSpec = setButtonToken(currentSpec, selectedElementId, token, value);
    setCurrentSpec(nextSpec);
    setInterpretation((current) =>
      updateInterpretation(current ?? emptyInterpretation(selectedElementId), `/appearance/${token}`, true),
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
    setStatus(`${token} was directly edited and is now strong ${messages.keep} evidence.`);
  }

  function recordEvent(input: Omit<Parameters<typeof recordPreferenceEvent>[0], "context">) {
    void recordPreferenceEvent({ ...input, context }).then((recorded) => {
      setMemoryEvents((count) => count + Number(recorded));
    });
  }

  function selectSurface(nextSurface: keyof typeof contexts) {
    setSurface(nextSurface);
    setVariants([]);
  }

  return (
    <main className={styles.canvas} onClick={selectElement(setSelectedElementId)}>
      <div className={styles.workbench}>
        <section
          aria-label="Button context"
          className={styles.contextPicker}
          onClick={(event) => event.stopPropagation()}
        >
          <span>{messages.context}</span>
          {Object.keys(contexts).map((name) => (
            <button
              aria-pressed={surface === name}
              key={name}
              onClick={() => selectSurface(name as keyof typeof contexts)}
              type="button"
            >
              {messages.surfaces[name as keyof typeof contexts]}
            </button>
          ))}
        </section>
        <section aria-label={messages.preview} className={styles.reviewedUi}>
          <div className={styles.sectionHeading}>
            <strong>{messages.preview}</strong>
            <p>{messages.previewHint}</p>
          </div>
          <ContextSurface messages={messages} surface={surface}>
            <ControlledRenderer spec={currentSpec} />
          </ContextSurface>
          <p aria-live="polite" className={styles.selection} data-testid="selected-element">
            {messages.selectedElement}: {selectedElementId}
          </p>
        </section>
        {selectedIsButton && selectedButton?.type === "Button" ? (
          <>
            <div aria-label={messages.feedback} className={styles.reviewDivider} role="separator">
              <span>{messages.feedback}</span>
            </div>
            <section
              aria-busy={isParsingCritique}
              aria-label={messages.feedback}
              className={styles.panel}
              onClick={(event) => event.stopPropagation()}
            >
            <p>{messages.feedbackHint}</p>
            <div aria-label={messages.reactions} className={styles.reactions}>
              {messages.reactionLabels.map((value, index) => (
                <button
                  aria-pressed={reaction === String(index)}
                  className={styles.reaction}
                  key={value}
                  onClick={() => {
                    setReaction(String(index));
                    recordEvent({
                      action: index === 2 ? "indifference" : "absolute_feedback",
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
              {messages.critique}
              <textarea
                onChange={(event) => setCritique(event.target.value)}
                placeholder={messages.critiquePlaceholder}
                value={critique}
              />
            </label>
            <button
              className={styles.primaryAction}
              disabled={!critique.trim() || isParsingCritique}
              onClick={() => void interpretCritique()}
              type="button"
            >
              {isParsingCritique ? messages.reviewingInterpretation : messages.reviewInterpretation}
              {isParsingCritique ? <span aria-hidden className={styles.loadingSpinner} /> : null}
            </button>
            <fieldset className={styles.inspector}>
              <legend>{messages.inspector}</legend>
              <p>{messages.inspectorHint}</p>
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
          </>
        ) : (
          <p className={styles.notice}>{messages.noButton}</p>
        )}
        <p aria-live="polite" className={styles.status} data-testid="refine-status">{status}</p>
        <aside aria-label={messages.preferenceMemory(memoryEvents)} className={styles.notice}>
          {messages.preferenceMemory(memoryEvents)}
        </aside>

        {interpretation ? (
          <>
            <div aria-label={messages.reviewFeedback} className={styles.reviewDivider} role="separator">
              <span>{messages.reviewFeedback}</span>
            </div>
            <InterpretationReview
              interpretation={interpretation}
              isGenerating={isGeneratingVariants}
              messages={messages}
              onChange={setInterpretation}
              onConfirm={() => void generateCandidates()}
            />
          </>
        ) : null}
        {variants.length > 0 ? (
            <section
              aria-busy={isGeneratingVariants}
            aria-label={messages.alternativesRegion}
            className={styles.variants}
            onClick={(event) => event.stopPropagation()}
          >
            <div className={styles.variantsHeading}>
              <h2>{messages.alternatives}</h2>
              {!variants.some((variant) => variant.kind === "wild_explore") ? (
                <button disabled={isGeneratingVariants} onClick={() => void generateCandidates(true)} type="button">
                  {isGeneratingVariants ? messages.exploringRecipe : messages.exploreRecipe}
                  {isGeneratingVariants ? <span aria-hidden className={styles.loadingSpinner} /> : null}
                </button>
              ) : null}
            </div>
            <div className={styles.variantGrid}>
              {variants.map((variant) => (
                <VariantCard
                  baseline={currentSpec}
                  key={variant.id}
                  messages={messages}
                  surface={surface}
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
                    setStatus(messages.accepted(variant.kind));
                  }}
                  onEvidence={(label) => {
                    recordEvent({
                      action: label === messages.indifferent ? "indifference" : "explicit_attribute_feedback",
                      source: label === messages.indifferent ? "absolute_feedback" : "explicit_attribute_feedback",
                      beforeSpec: currentSpec,
                      targetElementId: selectedElementId,
                      selectedElementId,
                      candidateId: variant.id,
                      interpretation,
                    });
                    setStatus(messages.evidenceStored(label, variant.kind));
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
                setStatus(messages.rejected);
              }}
              type="button"
            >
              {messages.rejectAll}
            </button>
          </section>
        ) : null}
      </div>
    </main>
  );
}

function ContextSurface({
  children,
  messages,
  surface,
}: {
  children: ReactNode;
  messages: Messages;
  surface: keyof typeof contexts;
}) {
  return (
    <section aria-label={messages.buttonSurface(messages.surfaces[surface])} className={`${styles.currentSpec} ${styles[surface]}`}>
      {surface === "toolbar" ? <span>{messages.projectSettings}</span> : null}
      {surface === "hero" ? <div><p>{messages.heroTagline}</p><h2>{messages.heroTitle}</h2></div> : null}
      {surface === "form" ? <label>{messages.emailAddress}<input placeholder={messages.emailPlaceholder} type="email" /></label> : null}
      {children}
    </section>
  );
}

function InterpretationReview({ interpretation, isGenerating, messages, onChange, onConfirm }: {
  interpretation: Interpretation;
  isGenerating: boolean;
  messages: Messages;
  onChange: (interpretation: Interpretation) => void;
  onConfirm: () => void;
}) {
  const paths = Object.keys(buttonTokenValues).map((token) => `/appearance/${token}` as ButtonPath);
  const keptPaths = interpretation.directives
    .filter((directive) => directive.kind === "keep")
    .map((directive) => directive.path);
  return (
    <section aria-label={messages.reviewRegion} className={styles.intentReview}>
      <h2>{messages.confirmInterpretation}</h2>
      <p>{interpretation.rationale}</p>
      <p>{messages.reviewSelectionHint}</p>
      {interpretation.ambiguity.map((message) => <p className={styles.notice} key={message}>{message}</p>)}
      <TokenChecklist
        heading={messages.keep}
        paths={paths}
        selected={keptPaths}
        onChange={(path, checked) => onChange(updateInterpretation(interpretation, path, checked))}
      />
      <button className={styles.primaryAction} disabled={isGenerating} onClick={onConfirm} type="button">
        {isGenerating ? messages.generatingAlternatives : messages.generateAlternatives}
        {isGenerating ? <span aria-hidden className={styles.loadingSpinner} /> : null}
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

function reviewableInterpretation(interpretation: Interpretation): Interpretation {
  const keptPaths = new Set(
    interpretation.directives.filter((directive) => directive.kind === "keep").map((directive) => directive.path),
  );
  const firstPath = Object.keys(buttonTokenValues)[0] as ButtonToken;
  return updateInterpretation(interpretation, `/appearance/${firstPath}`, keptPaths.has(`/appearance/${firstPath}`));
}

function VariantCard({ baseline, messages, surface, variant, onAccept, onEvidence }: {
  baseline: typeof buttonFixtureSpec;
  messages: Messages;
  surface: keyof typeof contexts;
  variant: RefineVariant;
  onAccept: () => void;
  onEvidence: (evidence: string) => void;
}) {
  const changes = variantChanges(baseline, variant.spec);
  return (
    <article className={styles.variant}>
      <p className={styles.variantKind}>{variant.kind.replaceAll("_", " ")}: {variant.direction}</p>
      <ContextSurface messages={messages} surface={surface}>
        <ControlledRenderer spec={variant.spec} />
      </ContextSurface>
      <div aria-label={messages.changes} className={styles.variantChanges}>
        <strong>{messages.changes}</strong>
        <ul>
          {changes.map((change) => <li key={change}>{change}</li>)}
        </ul>
      </div>
      <div className={styles.variantActions}>
        <button onClick={onAccept} type="button">{messages.accept}</button>
        <button onClick={() => onEvidence(messages.almost)} type="button">{messages.almost}</button>
        <button onClick={() => onEvidence(messages.indifferent)} type="button">{messages.indifferent}</button>
      </div>
    </article>
  );
}

function variantChanges(baseline: typeof buttonFixtureSpec, variant: RefineVariant["spec"]): string[] {
  const before = baseline.elements["continue-button"];
  const after = variant.elements["continue-button"];
  if (before?.type !== "Button" || after?.type !== "Button") return [];
  return (Object.keys(buttonTokenValues) as ButtonToken[])
    .filter((token) => before.props.appearance[token] !== after.props.appearance[token])
    .map((token) => `${token}: ${before.props.appearance[token]} → ${after.props.appearance[token]}`);
}

function selectElement(setSelectedElementId: (elementId: string) => void) {
  return (event: MouseEvent<HTMLElement>) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const elementId = target.closest<HTMLElement>("[data-jr-key]")?.dataset.jrKey;
    if (elementId) setSelectedElementId(elementId);
  };
}

"use client";

import { markDevtoolsActive } from "@json-render/core";
import { ControlledRenderer, refineFixtureSpec, type UISpec } from "@itl/ui-catalog";
import { type MouseEvent, type ReactNode, useEffect, useMemo, useState } from "react";

import { messages as localizedMessages, type Locale, type Messages } from "@/i18n/messages";

import {
  type AppearancePath,
  type AppearanceToken,
  type DesignContext,
  type Interpretation,
  type ProjectContext,
  type RefineVariant,
  appearancePaths,
  appearanceValues,
  currentAppearance,
  editableComponentType,
  emptyInterpretation,
  scopeFor,
  setAppearanceToken,
  updateInterpretation,
} from "../refine/refine-engine";
import {
  type RetrievedObservation,
  recordPreferenceEvent,
  retrievePreferenceMemory,
} from "../refine/memory-client";
import { generateVariants as requestVariants, parseCritique } from "../refine/refine-client";

import styles from "./controlled-canvas.module.css";

const contexts: Record<"toolbar" | "hero" | "form", DesignContext> = {
  toolbar: { role: "secondary-action", surface: "toolbar", density: "compact" },
  hero: { role: "primary-action", surface: "hero", density: "comfortable" },
  form: { role: "primary-action", surface: "form", density: "comfortable" },
};
/**
 * The product this session is judging for. It is a separate axis from where a
 * stimulus sits on the screen, so the same hero button judged under two tones
 * is two readings rather than one contradiction.
 */
const projectContexts: Record<"serious" | "playful", ProjectContext> = {
  serious: { productKind: "saas", visualTone: ["serious", "minimal"], platform: "web" },
  playful: { productKind: "marketing", visualTone: ["playful", "expressive"], platform: "web" },
};
type ConcreteObservation = RetrievedObservation & {
  outcome: NonNullable<RetrievedObservation["outcome"]>;
  observedAppearance: NonNullable<RetrievedObservation["observedAppearance"]>;
};

export function ControlledCanvas({ locale }: { locale: Locale }) {
  const messages = localizedMessages[locale];
  const [currentSpec, setCurrentSpec] = useState(refineFixtureSpec);
  const [surface, setSurface] = useState<keyof typeof contexts>("hero");
  const [productTone, setProductTone] = useState<keyof typeof projectContexts>("serious");
  const [selectedElementId, setSelectedElementId] = useState("continue-button");
  const [reaction, setReaction] = useState("1");
  const [critique, setCritique] = useState("");
  const [interpretation, setInterpretation] = useState<Interpretation | null>(null);
  const [variants, setVariants] = useState<RefineVariant[]>([]);
  const [isParsingCritique, setIsParsingCritique] = useState(false);
  const [isGeneratingVariants, setIsGeneratingVariants] = useState(false);
  const [status, setStatus] = useState(messages.selectSubject);
  const [memoryEvents, setMemoryEvents] = useState(0);
  const [round, setRound] = useState(1);
  const [observations, setObservations] = useState<RetrievedObservation[]>([]);
  const context = contexts[surface];
  const projectContext = projectContexts[productTone];

  useEffect(() => markDevtoolsActive(), []);

  const selectedType = editableComponentType(currentSpec, selectedElementId);
  const tokenValues = useMemo(
    () => appearanceValues(currentSpec, selectedElementId),
    [currentSpec, selectedElementId],
  );
  const appearance = useMemo(
    () => currentAppearance(currentSpec, selectedElementId),
    [currentSpec, selectedElementId],
  );
  const paths = useMemo(() => appearancePaths(currentSpec, selectedElementId), [currentSpec, selectedElementId]);

  async function interpretCritique() {
    if (!selectedType) {
      setStatus(messages.selectSubject);
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
      setInterpretation(reviewableInterpretation(parsed, paths));
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
      const scope = scopeFor(currentSpec, selectedElementId);
      if (!scope) {
        setStatus(messages.selectSubject);
        return;
      }
      const next = await requestVariants({
        spec: currentSpec,
        targetElementId: selectedElementId,
        interpretation,
        includeWild,
        context,
        projectContext,
        scope,
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

  function editToken(token: AppearanceToken, value: string) {
    if (!selectedType) return;
    const nextSpec = setAppearanceToken(currentSpec, selectedElementId, token, value);
    setCurrentSpec(nextSpec);
    setInterpretation((current) =>
      updateInterpretation(current ?? emptyInterpretation(selectedElementId), `/appearance/${token}`, true, paths),
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

  function recordEvent(
    input: Omit<Parameters<typeof recordPreferenceEvent>[0], "context" | "componentType" | "scope">,
  ) {
    // A decision is only recordable when its subject and level are known.
    const scope = scopeFor(currentSpec, input.targetElementId);
    const componentType = editableComponentType(currentSpec, input.targetElementId);
    if (!scope || !componentType) return;
    void recordPreferenceEvent({ ...input, componentType, scope, context, projectContext }).then((recorded) => {
      if (!recorded) return;
      setMemoryEvents((count) => count + 1);
      void retrievePreferenceMemory({
        context,
        projectContext,
        componentType,
        scope,
        evidence: input.evidence ?? input.interpretation?.evidence,
      }).then(setObservations);
    });
  }

  function selectSurface(nextSurface: keyof typeof contexts) {
    setSurface(nextSurface);
    setVariants([]);
    const scope = scopeFor(currentSpec, selectedElementId);
    if (!scope || !selectedType) return;
    void retrievePreferenceMemory({
      context: contexts[nextSurface],
      projectContext,
      componentType: selectedType,
      scope,
    }).then(setObservations);
  }

  function selectProductTone(nextTone: keyof typeof projectContexts) {
    setProductTone(nextTone);
    const scope = scopeFor(currentSpec, selectedElementId);
    if (!scope || !selectedType) return;
    void retrievePreferenceMemory({
      context,
      projectContext: projectContexts[nextTone],
      componentType: selectedType,
      scope,
    }).then(setObservations);
  }

  return (
    <main className={styles.canvas} onClick={selectElement(setSelectedElementId)}>
      <div className={styles.workbench}>
        <section
          aria-label="Design context"
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
        <section
          aria-label={messages.projectTone}
          className={styles.contextPicker}
          onClick={(event) => event.stopPropagation()}
        >
          <span>{messages.projectTone}</span>
          {Object.keys(projectContexts).map((name) => (
            <button
              aria-pressed={productTone === name}
              key={name}
              onClick={() => selectProductTone(name as keyof typeof projectContexts)}
              type="button"
            >
              {messages.projectTones[name as keyof typeof projectContexts]}
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
        {selectedType ? (
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
              {Object.entries(tokenValues).map(([token, values]) => (
                <label key={token}>
                  {token}
                  <select
                    aria-label={`Edit ${token}`}
                    onChange={(event) => editToken(token, event.target.value)}
                    value={appearance[token]}
                  >
                    {values.map((value) => <option key={value} value={value}>{value}</option>)}
                  </select>
                </label>
              ))}
            </fieldset>
          </section>
          </>
        ) : (
          <p className={styles.notice}>{messages.noSubject}</p>
        )}
        <p aria-live="polite" className={styles.status} data-testid="refine-status">{status}</p>
        <aside aria-label={messages.preferenceMemory(memoryEvents)} className={styles.notice}>
          {messages.preferenceMemory(memoryEvents)}
        </aside>
        <LearningLoopDebugger messages={messages} observations={observations} round={round} />

        {interpretation ? (
          <>
            <div aria-label={messages.reviewFeedback} className={styles.reviewDivider} role="separator">
              <span>{messages.reviewFeedback}</span>
            </div>
            <InterpretationReview
              interpretation={interpretation}
              isGenerating={isGeneratingVariants}
              messages={messages}
              paths={paths}
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
                  targetElementId={selectedElementId}
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
                    setInterpretation(null);
                    setCritique("");
                    setRound((currentRound) => currentRound + 1);
                    setStatus(messages.accepted(variant.kind));
                  }}
                  onEvidence={(outcome) => {
                    recordEvent({
                      action: outcome === "indifferent" ? "indifference" : "almost",
                      source: outcome === "indifferent" ? "absolute_feedback" : "explicit_attribute_feedback",
                      beforeSpec: currentSpec,
                      afterSpec: variant.spec,
                      targetElementId: selectedElementId,
                      selectedElementId,
                      candidateId: variant.id,
                      interpretation,
                    });
                    setStatus(messages.evidenceStored(
                      outcome === "indifferent" ? messages.indifferent : messages.almost,
                      variant.kind,
                    ));
                  }}
                />
              ))}
            </div>
            <button
              className={styles.rejectAll}
              onClick={() => {
                variants.forEach((variant) => {
                  recordEvent({
                    action: "rejection",
                    source: "absolute_feedback",
                    beforeSpec: currentSpec,
                    afterSpec: variant.spec,
                    targetElementId: selectedElementId,
                    selectedElementId,
                    candidateId: variant.id,
                    interpretation,
                  });
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
    <section aria-label={messages.subjectSurface(messages.surfaces[surface])} className={`${styles.currentSpec} ${styles[surface]}`}>
      {surface === "toolbar" ? <span>{messages.projectSettings}</span> : null}
      {surface === "hero" ? <div><p>{messages.heroTagline}</p><h2>{messages.heroTitle}</h2></div> : null}
      {surface === "form" ? <label>{messages.emailAddress}<input placeholder={messages.emailPlaceholder} type="email" /></label> : null}
      {children}
    </section>
  );
}

function InterpretationReview({ interpretation, isGenerating, messages, paths, onChange, onConfirm }: {
  interpretation: Interpretation;
  isGenerating: boolean;
  messages: Messages;
  paths: AppearancePath[];
  onChange: (interpretation: Interpretation) => void;
  onConfirm: () => void;
}) {
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
        onChange={(path, checked) => onChange(updateInterpretation(interpretation, path, checked, paths))}
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
  paths: AppearancePath[];
  selected: AppearancePath[];
  onChange: (path: AppearancePath, checked: boolean) => void;
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

function reviewableInterpretation(interpretation: Interpretation, paths: AppearancePath[]): Interpretation {
  const keptPaths = new Set(
    interpretation.directives.filter((directive) => directive.kind === "keep").map((directive) => directive.path),
  );
  const [firstPath] = paths;
  if (!firstPath) return interpretation;
  return updateInterpretation(interpretation, firstPath, keptPaths.has(firstPath), paths);
}

function LearningLoopDebugger({ messages, observations, round }: {
  messages: Messages;
  observations: RetrievedObservation[];
  round: number;
}) {
  const concreteObservations = observations.filter(
    (observation): observation is ConcreteObservation =>
      observation.outcome !== null && observation.observedAppearance !== null,
  );
  return (
    <aside aria-label={messages.learningLoop} className={styles.learningLoop}>
      <strong>{messages.round(round)}</strong>
      <p>{messages.usingObservations(concreteObservations.length)}</p>
      <ul>
        {concreteObservations.map((observation) => (
          <li key={observation.id}>
            <span>{messages.observationOutcome(observation.outcome)}</span>
            <span>
              {observation.context?.surface ?? messages.unknownContext} — {observation.observedAppearance.componentType}
              {": "}
              {Object.values(observation.observedAppearance.appearance).join(" / ")}
            </span>
          </li>
        ))}
      </ul>
    </aside>
  );
}

function VariantCard({ baseline, messages, surface, targetElementId, variant, onAccept, onEvidence }: {
  baseline: UISpec;
  messages: Messages;
  surface: keyof typeof contexts;
  targetElementId: string;
  variant: RefineVariant;
  onAccept: () => void;
  onEvidence: (outcome: "almost" | "indifferent") => void;
}) {
  const changes = variantChanges(baseline, variant.spec, targetElementId);
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
        <button onClick={() => onEvidence("almost")} type="button">{messages.almost}</button>
        <button onClick={() => onEvidence("indifferent")} type="button">{messages.indifferent}</button>
      </div>
    </article>
  );
}

function variantChanges(baseline: UISpec, variant: RefineVariant["spec"], targetElementId: string): string[] {
  const before = currentAppearance(baseline, targetElementId);
  const after = currentAppearance(variant, targetElementId);
  return Object.keys(before)
    .filter((token) => before[token] !== after[token])
    .map((token) => `${token}: ${before[token]} → ${after[token]}`);
}

function selectElement(setSelectedElementId: (elementId: string) => void) {
  return (event: MouseEvent<HTMLElement>) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const elementId = target.closest<HTMLElement>("[data-jr-key]")?.dataset.jrKey;
    if (elementId) setSelectedElementId(elementId);
  };
}

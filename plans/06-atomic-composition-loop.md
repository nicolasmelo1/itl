# Plan 06 — Atomic vertical slice and contextual Taste Loop

## Goal

Extend the Button laboratory through one registered Atomic Design vertical slice
and prove the complete learning boundary:

```text
shown candidate → explicit human outcome → contextual event log
    → retrieval by context + scope → minimized TasteBrief
    → provider → bounded candidate patches → shown candidate
```

The deliverable is deliberately **not** a complete production design system.
It is a controlled settings-page slice whose layer constraints, rendering, and
human-feedback loop are real. The full catalog inventory described in [the
Atomic Design system document](../docs/atomic-design-system.md) remains the
long-term target, to be expanded only after this loop is evaluated.

**Exit condition:** a generation request carries its explicit `AtomicScope`;
retrieval uses that scope and its design context; the provider can receive only
a versioned `TasteBrief`; each brief preserves the displayed stimulus and the
human outcome without exposing private event fields; and the registered
settings-page slice has focused composition, accessibility, and responsive
proof.

## Session shape

| Time | Scope | Example outcome |
| --- | --- | --- |
| 0–5 min | Context and one starting reference | “Dense financial dashboard, deliberate and quiet.” |
| 5–15 min | Foundations or one atom | Font role, spacing step, field label, border, or Button. |
| 15–30 min | One bounded composition | Field with label and help text; then a small form group. |
| 30–40 min | Review and promotion | Record outcome, shown stimulus, contextual rule, and next scope. |

The session stops at the current level when feedback is ambiguous. It does not
jump to a page merely to fill the time budget.

## Scope of this phase

This phase establishes the following vertical slice:

1. canonical foundation tokens and their CSS projection;
2. the registered Button atom plus the atoms and molecule needed by the
   settings page;
3. one registered organism, template, and concrete settings page composition;
4. append-only preference events and contextual retrieval for the Button
   generation path; and
5. provider conditioning through the minimized `TasteBrief` only.

The phase does not claim that every component listed in the long-term catalog
(for example DataTable, Checkout, or every atom state) is implemented or has
browser proof. Adding those components is subsequent catalog work, not evidence
that the Taste Loop has learned anything.

## Taste data model and conditioning contract

Every event retains the private audit record needed to reconstruct a decision:
level, scope, context, before/after renderable spec, candidate ID, explicit
critique, parser interpretation, directives, source, and timestamps. That
record is never the model-facing type.

The model-facing decision is the compact, inspectable `TasteBriefDecision`:

```text
eventId
scope + context relation
outcome: accepted | almost | rejected | indifferent | manual_edit
stimulus: minimal appearance delta + candidateId when available
directives
strength + source
preference polarity/relation
```

`stimulus` says what was actually shown; it must be sufficient to distinguish,
for example, a rejected pill/compact candidate from an accepted square/compact
candidate without including a whole `beforeSpec` or `afterSpec`. `outcome` must
survive retrieval into every subsequent brief. A rejection must not inherit a
previous critique interpretation as if that interpretation were positive
evidence; its directives, if any, must be explicitly attributable to that
reaction.

The brief is versioned and auditable through event IDs. It excludes private
`critique`, `beforeSpec`, `afterSpec`, `parserInterpretation`, arbitrary diffs,
and any unbounded event payload.

`GenerateSpecRequest` and `GenerateVariantsRequest` both carry `scope` (with a
Button-compatible default only for backwards-compatible local callers). The
service retrieves using `request.context` and `request.scope`, records the
brief version and evidence IDs, and never silently substitutes the generic
Button scope for an explicit one.

The provider interface accepts `TasteBrief`, not `list[RetrievedEvidence]`.
Both remote and DSPy adapters serialize the brief under a deliberate
`tasteBrief` field. `RetrievedEvidence` remains a repository/service type and
is not an accepted provider argument. A provider-boundary test inspects the
actual request payload and fails if it contains `critique`, `beforeSpec`,
`afterSpec`, `parserInterpretation`, or `retrievedEvidence`.

## Retrieval semantics

Retrieval has two separate responsibilities:

- **Relevance/ranking:** source confidence, evidence strength, context
  compatibility, and scope compatibility decide whether an event should be
  retrieved for this request. Exact scope must be attainable through the
  generation requests, rather than only through persistence/debugging.
- **Preference meaning:** outcome and the preference relation/polarity express
  whether the retrieved stimulus was accepted, almost accepted, rejected,
  indifferent, or manually edited. They are passed to the brief; they must not
  be collapsed into a single positive “score”.

An explicit attribute comment and a candidate acceptance may have different
source confidence, but an `almost` event must not become stronger than an
acceptance merely because of a source-weight accident. Tests cover that
relevance and polarity are independently preserved, including a highly
relevant rejection.

## Implementation sequence

1. Keep the canonical DTCG token source and CSS projection; constrain the
   registered settings-page composition to the current vertical slice.
2. Add `scope` to both generation request contracts and route it unchanged to
   retrieval, TasteBrief construction, and generation audit records.
3. Extend the TasteBrief schema/version with `outcome` and a minimum
   `stimulus`; map these exclusively from retrieved event data while preserving
   the private event record outside the brief.
4. Split retrieval ranking from preference polarity, then add fixtures for
   accepted, almost, rejected, indifferent, and manual-edit reactions across
   compatible and incompatible context/scope.
5. Change every candidate-patch provider signature and adapter payload from
   `RetrievedEvidence` to `TasteBrief`; add the provider-boundary leak test.
6. Keep the composition and browser checks focused on the registered settings
   slice, and rename their assertions and sealed gate requirements to match
   that evidence.

## Guardrails

- Accessibility, schema validation, responsiveness, and semantic content are
  hard constraints for every registered structure in this slice.
- A model can choose only catalog values and registered composition patterns;
  it cannot emit HTML, CSS, actions, URLs, or a new component type.
- Do not infer global brand rules from one Button or one context. Keep
  uncertainty, contradiction, and outcome polarity visible in the brief.
- `TasteBrief` is the only memory artifact that may cross the provider/model
  boundary. The repository projection and raw event record stay server-side.
- Do not begin prompt optimization, GEPA, or a learned taste model until a
  held-out, human-reviewed evaluation corpus exists.

## Deterministic gates

Phase 06 has two executable gates. Their names intentionally describe the
evidence currently produced; they do not overclaim full-catalog or every-layer
coverage.

### `atomic-foundations`

`pnpm verify:atomic-foundations` validates the canonical DTCG-shaped token
source against its CSS projection, then runs the web typecheck and tests. It
must prove:

- `atomic.foundations_use_a_canonical_dtcg_shaped_source`
- `atomic.foundation_css_projection_has_no_token_drift`
- `atomic.existing_components_remain_type_safe_and_tested`

### `atomic-design-system`

`pnpm verify:atomic-design-system` first runs the foundation gate and then
requires the dedicated proof suites below. It is sealed only after `sf seal
atomic-design-system` records a fresh report with these assertions:

- `atomic.foundations_are_canonical_and_projected`
- `atomic.catalog_slice_has_valid_hierarchy_and_safe_slots`
- `atomic.sessions_preserve_level_scope_context_and_outcome`
- `atomic.taste_brief_is_minimized_versioned_auditable_and_provider_bounded`
- `atomic.settings_page_uses_registered_compositions`
- `atomic.settings_slice_has_basic_responsive_and_keyboard_proof`

The final gate runs deterministic fixtures. It includes invalid slot graphs, a
rejected upward propagation, conflicting contexts, token projection drift,
malformed briefs, forbidden provider-payload fields, unregistered component
attempts, narrow/wide settings-page viewports, keyboard focus, and reduced
motion. It does **not** assert responsive behaviour, keyboard traversal, or
state coverage for every future Atomic component.

## Acceptance criteria

- [ ] Canonical foundation tokens project to the registered slice without drift. (proof: assertion:atomic.foundations_are_canonical_and_projected)
- [ ] The registered composition slice rejects inverted levels, cycles, missing references, and invalid slots. (proof: deferred: `atomic.catalog_slice_has_valid_hierarchy_and_safe_slots`)
- [ ] Every generation request uses its supplied Atomic level, scope, and design context for retrieval. (proof: deferred: `atomic.sessions_preserve_level_scope_context_and_outcome`)
- [ ] A retrieved accepted, almost, rejected, indifferent, or manual-edit reaction retains its outcome and minimum shown stimulus in the TasteBrief. (proof: deferred: `atomic.sessions_preserve_level_scope_context_and_outcome`)
- [ ] Candidate-patch providers receive only a minimized, versioned TasteBrief; the outbound model payload contains no raw evidence/private event fields; outputs audit brief version and evidence IDs. (proof: deferred: `atomic.taste_brief_is_minimized_versioned_auditable_and_provider_bounded`)
- [ ] The settings page renders only registered organisms and compositions. (proof: deferred: `atomic.settings_page_uses_registered_compositions`)
- [ ] The settings slice has narrow/wide viewport, keyboard-focus, and reduced-motion proof. (proof: deferred: `atomic.settings_slice_has_basic_responsive_and_keyboard_proof`)

## After this phase: prove the loop before expanding infrastructure

The next PR is `feat: add held-out taste-loop evaluation`, not another broad
Atomic Design expansion and not GEPA. It asks whether, after _N_ judgments
from the same person, contextual memory improves prediction of that person’s
next judgment.

Compare at least:

| Baseline | Conditioning |
| --- | --- |
| A | LLM without memory |
| B | Most recent preference only |
| ITL | Contextual, scoped TasteBrief |

Evaluate held-out sessions by context (`hero`, `form`, `toolbar`, `dashboard`)
and later by Atomic level. Record acceptance rate, pairwise win rate, top-1
preference hit rate, regret/rejected-candidate rate, constraint violations,
and diversity. Only a positive held-out result justifies prompt optimization,
DSPy compilation, or GEPA.

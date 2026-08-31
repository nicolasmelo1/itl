# Plan 06 — Full Atomic Design system and learning loop

## Goal

Turn the Button laboratory into the complete Atomic Design system: foundations,
atoms, molecules, organisms, templates and pages. A person progresses through
bounded decisions in **20–40 minute sessions**. The resulting evidence is
structured enough to condition future UI-generation prompts, but remains
contextual and auditable.

**Exit condition:** all six layers have catalog contracts and deterministic
fixtures; sessions persist scope/context; prompts receive a minimized,
versioned taste brief; and a concrete page renders only registered structures
with responsive and accessibility proof.

## Session shape

| Time | Scope | Example outcome |
| --- | --- | --- |
| 0–5 min | Context and one starting reference | “Dense financial dashboard, deliberate and quiet.” |
| 5–15 min | Foundations or one atom | Font role, spacing step, field label, border, or Button. |
| 15–30 min | One bounded composition | Field with label and help text; then a small form group. |
| 30–40 min | Review and promotion | Accept/reject, state the rule's context, and choose the next scope. |

The session stops at the current level when feedback is ambiguous. It should
not jump to a page merely to fill the time budget.

## Complete component progression

The complete layer definitions, inventory, contracts, learning rules and
references live in [the Atomic Design system document](../docs/atomic-design-system.md).
The short form is:

1. **Foundations** — complete token architecture: typography, spacing, sizing,
   grids, color roles, borders, radius, elevation, motion, breakpoints,
   iconography, focus and cross-cutting accessibility/content rules.
2. **Atoms** — content, media, action/feedback, text-entry, choice and
   accessibility primitives; each has anatomy, variants, states and a11y.
3. **Molecules** — Field, SearchField, InputGroup, ButtonGroup, navigation,
   feedback and Card compositions with bounded slots and responsibilities.
4. **Organisms** — application header, navigation, sidebar, hero, auth form,
   data table, filter panel, dialog, toast region, footer and content feeds.
5. **Templates** — responsive app-shell, dashboard, marketing, authentication,
   settings, content-detail and checkout layouts with named regions.
6. **Pages** — concrete routes with real content, data and state, built from a
   reviewed template.

## Taste data model

Every event retains `level`, target component/composition, design context,
before/after renderable spec, explicit evidence, directives, and the source
of the decision. A preference can be promoted only with an explicit relation:

- a **foundation** rule can be reused by compatible atoms and compositions;
- an **atom** rule is reused only by the same atom or an explicitly mapped
  semantic role;
- a **composition** rule stays scoped to its molecule/organism and context;
- conflicting observations are preserved, not averaged away.

The first prompt-facing artifact is a compact, inspectable **taste brief**:
confirmed directives grouped by level and context, supporting event IDs,
confidence/source, and explicit exclusions. It is input context for a model,
not executable code and not a universal visual score.

## Implementation sequence

1. Create canonical DTCG token files and compile CSS/platform outputs; add a
   foundation inspector, modes and token documentation.
2. Add `level`, `scope`, anatomy/slots and token dependencies to the catalog,
   session and preference-event contracts; migrate Button as an atom.
3. Complete the atom library with accessibility/state fixtures, then the
   molecule library with child/slot validation.
4. Add organism, template and page registries with responsive, loading/error,
   data and route contracts.
5. Generate and display the design-system manifest plus contextual taste brief
   alongside every model request; log the exact versions and evidence IDs used.

## Guardrails

- Accessibility, schema validation, responsiveness, and semantic content are
  hard constraints at every level.
- A model can choose only catalog values and registered composition patterns;
  it cannot emit HTML, CSS, actions, URLs, or a new component type.
- Do not infer global brand rules from one Button or one context. Keep
  uncertainty and contradictions visible in the brief.
- Do not begin prompt optimization or a learned taste model until an evaluation
  corpus contains held-out, human-reviewed sessions across at least two levels.

## Deterministic gates

Phase 06 has two executable gates. They are intentionally separate: the
foundation gate can protect the first implementation slice, while the final
gate cannot be sealed until every layer has real, focused proof suites.

### `atomic-foundations`

`pnpm verify:atomic-foundations` validates the canonical DTCG-shaped token
source against its CSS projection, then runs the web typecheck and tests. It
must prove:

- `atomic.foundations_use_a_canonical_dtcg_shaped_source`
- `atomic.foundation_css_projection_has_no_token_drift`
- `atomic.existing_components_remain_type_safe_and_tested`

### `atomic-design-system`

`pnpm verify:atomic-design-system` first runs the foundation gate and then
requires dedicated proof suites; it fails explicitly while any required suite
is absent. It is sealed only after `sf seal atomic-design-system` records a
fresh report with all of these assertions:

- `atomic.foundations_are_canonical_and_projected`
- `atomic.catalog_has_complete_hierarchy_and_safe_slots`
- `atomic.sessions_preserve_level_scope_and_context`
- `atomic.taste_brief_is_minimized_versioned_and_auditable`
- `atomic.templates_and_pages_render_only_registered_structures`
- `atomic.accessibility_and_responsive_states_hold_at_every_layer`

The final gate runs only deterministic fixtures. It must include invalid slot
graphs, a rejected upward propagation, conflicting contexts, token projection
drift, malformed briefs, unregistered component attempts, narrow/wide
viewports, keyboard navigation and reduced-motion states. A documentation-only
change cannot satisfy it.

## Acceptance criteria

- [ ] Canonical foundation tokens project to the component library without drift. (proof: assertion:atomic.foundations_are_canonical_and_projected)
- [ ] The full hierarchy and component slots reject inverted levels, cycles and missing references. (proof: assertion:atomic.catalog_has_complete_hierarchy_and_safe_slots)
- [ ] Every preference event and retrieval preserves Atomic level, scope and design context. (proof: assertion:atomic.sessions_preserve_level_scope_and_context)
- [ ] Generation receives only a minimized, versioned taste brief and each output audits the brief version and evidence IDs. (proof: assertion:atomic.taste_brief_is_minimized_versioned_and_auditable)
- [ ] Templates and pages render only registered organisms and compositions. (proof: assertion:atomic.templates_and_pages_render_only_registered_structures)
- [ ] Narrow/wide viewport, keyboard focus and reduced-motion behaviour remain accessible through the rendered hierarchy. (proof: assertion:atomic.accessibility_and_responsive_states_hold_at_every_layer)

## Completion milestones

| Milestone | Proof |
| --- | --- |
| Foundations and atoms | Canonical token source compiles to the product; each atom has finite schema, all states and accessibility fixtures. |
| Molecules | Field, search, navigation, feedback and action compositions validate slots and retain scoped preference evidence. |
| Organisms | Reviewed sections handle responsive, loading, empty and error states without bypassing the catalog. |
| Templates | Named layout regions and breakpoints compose organisms deterministically. |
| Pages and AI handoff | Real routes render reviewed templates; every model request uses a versioned manifest and contextual taste brief with auditable evidence IDs. |

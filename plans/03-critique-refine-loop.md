# Plan 03 — Critique, locks, and local refinement

## Goal

Prove the product's core interaction: a user can see one credible component,
say exactly what to retain or change, and receive constrained alternatives
without being forced into a false A/B preference.

**Exit condition:** Starting from a Button spec, a user can submit a critique,
review the interpreted locks and exploration paths, choose a variant or reject
all of them, and every output remains schema-valid while locked attributes are
unchanged.

## Scope and decisions

- The initial product flow targets Button only. This validates the interaction
  model before it is generalized to nested elements.
- Use DSPy to declare three typed operations: `GenerateSpec`, `ParseCritique`,
  and `GenerateVariants`. Begin zero/few-shot; do not use GEPA.
- The parsing contract returns structured patch intent, not CSS and not a new
  component. It identifies `likedPaths`, `dislikedPaths`, `lockedPaths`,
  `explorationPaths`, ambiguity, and a human-readable rationale.
- Variants must be labelled `exploit`, `adjacent_explore`, or `wild_explore`.
  The initial refine screen should prioritize exploit and adjacent variants;
  wild alternatives appear only through an explicit user exploration action.
- A critique is reviewable before mutation. The user can edit the inferred
  locks/paths, so the LLM never silently treats an inference as consent.

## Work sequence

1. Define API request/response schemas shared as generated contract fixtures
   under `contracts/refine/`, not as shared runtime code. Include spec version, target element ID, critique,
   patch intent, variants, and machine-readable validation errors.
2. Configure DSPy behind a provider adapter. Keep prompts/signatures local to
   the Python service and require structured output validation after every
   model call. In development, use deterministic fixtures so the entire flow
   is testable without a model.
3. Implement `GenerateSpec` only for an initial Button request. It may select
   from catalog tokens, but it may not create a component or prop outside the
   catalog.
4. Implement `ParseCritique` for free text such as “gosto da cor e do
   espaçamento, mas está arredondado demais.” It returns a proposed intent;
   reject unresolvable property paths rather than guessing.
5. Add the critique UI: absolute feedback (`gosto`, `quase`, `indiferente`,
   `não gosto`), optional text, selected element indication, and a confirmation
   panel that separates **Keep** from **Explore**.
6. Implement deterministic patch and variant generation. A variant starts from
   the current valid spec; locked paths remain byte-for-byte semantically
   equal, while explored paths must change to another allowed value.
7. Render three variations only after their validation passes. Provide distinct
   actions: accept, almost, indifferent, reject all, mix, and explore this
   direction. “Reject all” records a rejection and does not create a winner.
8. Add an inspector for direct token editing (e.g., `radius: lg → sm`). Treat
   it as a stronger evidence source than an inferred critique; it remains a
   simple constrained editor, not Figma.
9. Fail closed when an LLM returns invalid JSON, unsupported paths, or a
   lock-breaking variant. Show a retryable explanation and retain the current
   rendered spec.

## Guardrails

- Locks are enforced by deterministic comparison, never merely requested in a
  prompt.
- “None of these” is first-class evidence: it cannot be converted into an
  implicit preference for the least disliked alternative.
- All model output undergoes the same catalog/schema validation as fixture
  specs before rendering or persistence.
- The MVP makes no claim that it knows whether a UI is beautiful. It only
  preserves explicit user intent and explores a bounded option space.

## Acceptance criteria

- [ ] A text critique produces a reviewable structured proposal of kept and explored Button paths. (proof: assertion:refine.critique_yields_reviewable_patch_intent)
- [ ] Confirmed locked paths remain unchanged in every returned variant. (proof: assertion:refine.locks_are_preserved)
- [ ] Every explored path changes only to a valid catalogue value, and every variant passes schema validation. (proof: assertion:refine.explored_values_are_valid)
- [ ] The interaction offers acceptance, indifference, rejection of all options, and directed exploration without mandatory pairwise choice. (proof: assertion:refine.rejection_is_not_a_preference)
- [ ] Invalid or ambiguous AI output does not alter the current spec and returns a recoverable typed error. (proof: assertion:refine.invalid_model_output_preserves_current_spec)

## Verification procedure

1. Use deterministic contract fixtures for critiques covering explicit likes,
   dislikes, ambiguous language, no target selection, and conflicting locks.
2. Property-test the patch engine: for all valid Button specs, a locked path
   never changes and an explored path always validates.
3. Run an end-to-end browser test: generate fixture, critique radius, confirm
   background/spacing locks, choose an alternative, then reject all on a later
   comparison.
4. Exercise invalid model payloads to prove validation and current-state
   preservation, then run package and factory checks.

## Deterministic completion gate

`critique-refine-loop` activates on the typed DSPy adapter, critique/refinement
UI, and generated contract fixtures. Its evidence command runs with a
deterministic provider fixture — no live model call is permitted in this gate
— and reports these passed assertions:

- `refine.critique_yields_reviewable_patch_intent`
- `refine.locks_are_preserved`
- `refine.explored_values_are_valid`
- `refine.rejection_is_not_a_preference`
- `refine.invalid_model_output_preserves_current_spec`

The run must include an unknown path, malformed model JSON, conflicting locks,
and “none of these.” It is sealed with `sf seal critique-refine-loop`; changing
the refinement implementation without a fresh deterministic run leaves it red.

## Explicit non-goals

- No user-level taste model, automatic optimization, GEPA, or full-page UI.

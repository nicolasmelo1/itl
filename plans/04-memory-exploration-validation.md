# Plan 04 — Preference memory, exploration, and MVP validation

## Goal

Persist the evidence from the refinement loop, retrieve it only when relevant,
and demonstrate that the system can explore without collapsing a person's
possibly multimodal taste into one rigid profile.

**Exit condition:** A later Button generation receives relevant prior evidence
and demonstrably respects it where applicable, exploration feedback is stored
separately from exploitation feedback, and the MVP evaluation suite detects
regressions in locks, relevance, and rejection handling.

## Scope and decisions

- Store an append-only `PreferenceEvent` log in SQLite. The log preserves raw
  examples; it is the source of truth rather than a prematurely compressed
  scalar “taste score.”
- Record source, component type, optional context, before/after spec, selected
  element, liked/disliked/locked paths, text critique, and timestamp.
- Distinguish confidence by evidence source: manual edit > confirmed critique
  > explicit attribute feedback > absolute rating/rejection > pairwise choice
  > model inference. The ranking informs retrieval but never deletes events.
- Retrieve a small relevant set by component type, context, path overlap,
  recency, and confidence. Do not introduce a vector database for the MVP.
- Maintain explicit policies: exploit uses well-supported relevant evidence;
  adjacent exploration changes uncertain nearby dimensions; wild exploration
  samples a coherent named direction only after user opt-in.
- GEPA stays out of scope. Its first legitimate candidates are later
  `ParseCritique` structured accuracy and lock-respecting generation, after a
  held-out labelled dataset exists.

## Work sequence

1. Create the SQLite schema and migrations for immutable preference events and
   renderable spec snapshots. Add a repository boundary in the API service;
   callers cannot issue ad hoc SQL.
2. Persist every explicit action from Plan 03, including rejection, indifference,
   “explore more,” and manual edits. Retain the original text and the
   parser's interpretation separately so model inferences remain auditable.
3. Implement deterministic relevance retrieval for Button requests. It must
   return both supporting and contradictory evidence when the context differs;
   e.g. a dense dashboard's square-button evidence must not become a global
   prohibition on rounded CTA buttons.
4. Pass retrieved evidence to `GenerateSpec` and `GenerateVariants` in a
   bounded, inspectable format. Log which event IDs were used for each output.
5. Implement exploration budgeting at the session level: default sessions use
   mostly exploitation, a smaller adjacent share, and opt-in wild exploration.
   Never randomize individual visual tokens independently; alternatives must
   follow a coherent named direction.
6. Build an MVP evaluation corpus of manually verified scenarios. Split it
   before any later optimizer work into development and hidden human review
   examples. Include counterfactual contexts and isomorphic content changes.
7. Add robustness tests: substitute label/copy, change amounts, and vary the
   context label. Rules unaffected by these transformations should remain
   stable; context-sensitive preferences may change only with recorded
   evidence explaining why.
8. Run a small human evaluation: present one current proposal and one relevant
   evidence-informed proposal blind. Measure acceptance/rejection and the
   usefulness of the refine interaction; do not reduce results to a single
   “beauty” score.
9. Decide the next phase from evidence. Add Input/Card only if the Button loop
   is useful; consider GEPA only if a signature has enough labelled examples
   and a metric not based solely on a VLM judge.

## Guardrails

- No VLM-only reward is an optimization target. Accessibility, schema, and
  lock constraints remain hard gates; visual judgement is a proxy and human
  preference is the eventual ground truth.
- Hold out human preference examples from any prompt/compiler optimization.
  Rising internal score with falling blind human acceptance is reward hacking,
  not progress.
- Do not infer a universal “user hates rounded corners” rule from one event.
  Preserve context and contradictions in the event log.
- Stored critiques may contain sensitive user text. Keep the local database
  out of git and define retention/export/delete behavior before multi-user
  work begins.

## Acceptance criteria

- [ ] Every explicit feedback action from the refine loop is stored as an immutable, queryable preference event with its source and context. (proof: assertion:memory.explicit_feedback_is_immutable_and_queryable)
- [ ] Generation records the exact evidence IDs it retrieved, and tests prove irrelevant contexts do not dominate relevant evidence. (proof: assertion:memory.retrieval_is_auditable_and_contextual)
- [ ] Exploit, adjacent, and opt-in wild exploration are distinguishable policies and never force a pairwise winner after rejection. (proof: assertion:exploration.policies_are_distinct_and_non_coercive)
- [ ] Counterfactual content changes preserve relevant constraints and do not invalidate an otherwise valid spec. (proof: assertion:evaluation.counterfactual_constraints_hold)
- [ ] The evaluation set includes held-out human review cases and no automated optimizer is trained on those cases. (proof: assertion:evaluation.holdout_is_excluded_from_optimization)

## Verification procedure

1. Unit-test event persistence, migration, retrieval ranking, contradiction
   handling, and audit links from output to event IDs.
2. Use fixture histories with both square technical buttons and rounded CTA
   buttons. Assert the request context retrieves the matching evidence without
   erasing the other mode.
3. Run end-to-end tests that submit feedback, restart the service, generate a
   later Button, and display the evidence used.
4. Run content/viewport perturbation fixtures and schema validation for every
   output. Compare human blind-review acceptance separately from all internal
   checks.

## Deterministic completion gate

`memory-exploration-validation` activates on preference persistence,
retrieval/evaluation logic, memory UI, and database migrations. Its evidence
command uses an isolated SQLite database and a fixed versioned fixture corpus;
it cannot use a live LLM, production data, or mutable human judgement. The raw
report must show these passed assertions:

- `memory.explicit_feedback_is_immutable_and_queryable`
- `memory.retrieval_is_auditable_and_contextual`
- `exploration.policies_are_distinct_and_non_coercive`
- `evaluation.counterfactual_constraints_hold`
- `evaluation.holdout_is_excluded_from_optimization`

Mandatory negative cases are conflicting contextual evidence, a rejected
variant, a content perturbation, and attempted use of held-out IDs during
optimization. Seal only a fresh report with
`sf seal memory-exploration-validation`.

## Explicit non-goals

- No global reward model, GEPA compile loop, VLM taste optimizer, embeddings,
  molecules, organisms, templates, pages, or production personalization API.

# Plan 07 — Multi-component taste acquisition and generalization

## The question changes

Plan 06 asked whether one refinement loop could be safe, auditable and
contextual. It answered yes, on a Button. That was infrastructure, and it is
done.

This phase asks the product's actual research question:

> Can judgments over a heterogeneous collection of UI predict a person's
> preference on stimuli they have never been shown?

Not "can we predict the next Button". A Button-only result has high internal
validity and almost no external validity for the thesis "ITL learns a person's
UI taste". From here, **Button is an integration fixture and a smoke test for
the loop, not the research domain.**

**Exit condition:** a person sits down, runs a 20–40 minute session over dozens
of heterogeneous components in an isolated, keyboard-driven bench, exports a
portable `.taste`, and an evaluation harness reports — on held-out judgments —
whether that `.taste` beats no-memory and raw-retrieval baselines, including on
components it was never trained on.

## Where the project actually stands

Measured from `apps/ai/data/preferences.db` on 2026-08-31:

| | |
| --- | --- |
| Judgments recorded | 95, over three days |
| Provider | real — Ollama Cloud, `glm-5.3-flash` |
| Generations audited | 46 (28 exploit, 10 adjacent, 8 wild) |
| Subjects | Button 89, FormField 6 |
| Contexts | hero 74, form 11, toolbar 10 |
| Distinct session IDs | **1** — the web client hardcodes `"local"` |
| Rows carrying `scope` and `outcome` | 34 of 95; the older 61 predate those columns |

Four consequences shape this plan:

1. **The corpus is real and was collected against a real model.** This is not a
   cold start. It is, however, one subject, one dominant context, and one
   session identifier.
2. **Session hold-out is impossible on this data.** Every row is `local`. The
   primary benchmark must therefore split on `created_at`, and the acquisition
   client must start issuing real session IDs immediately — the split is only
   as good as the identifier.
3. **The signal is dominated by the weakest evidence.** 39 manual edits and 23
   indifferences against 2 acceptances and 4 rejections. Twenty-three
   indifferences is the candidate generator failing to produce a meaningful
   contrast, which is the empirical argument for pairwise acquisition.
4. **The contradiction the context taxonomy predicts is already in the data.**
   Under a single usage context — `primary-action / hero / comfortable` —
   manual edits move to `soft` 22 times, `pill` 10 and `square` 7, and the two
   candidate acceptances are one `square` and one `pill`. Some of that is
   exploration rather than settled preference, but the current model cannot
   distinguish "changed their mind" from "different product tone", because it
   has no axis for the second.

### A data-integrity bug that must be fixed before more collection

`PREFERENCE_DATABASE_PATH` defaults to the **relative** path
`data/preferences.db`. `pnpm dev:ai` runs `uv --directory apps/ai run uvicorn`,
so the server writes `apps/ai/data/preferences.db`, while anything invoked from
the repository root reads or creates a second, empty `data/preferences.db`.
Both files exist right now. A corpus that silently forks by working directory
is not a corpus.

## Why this is not "expand the catalog to look like progress"

Two statements that sound contradictory and are not:

- We must not expand the catalog to *pretend* we learned taste.
- We need stimulus diversity to *test whether* we learned taste.

Plan 06 was right to refuse the first. This plan requires the second, and the
gate reflects it: the deliverable is not "N components exist", it is "held-out
prediction on unseen components is measurable".

## The ontology change

This is the core of the phase, and it replaces the per-component appearance
vocabulary introduced in the current runtime.

### Problem with the current shape

Today a component owns its own vocabulary. `Button` has `recipe`, `size`,
`radius`, `density`, `fontWeight`; `FormField` has `labelPlacement`, `gap`,
`hintTone`. Evidence is recorded against `/appearance/<token>` *of that
component*. Two consequences:

1. A preference expressed on a Card teaches nothing about a Dialog.
2. Every new component needs a hand-written vocabulary. At 57 catalog
   components that is 57 bespoke ontologies; at "20,000 components" it is
   absurd.

### Shared taste dimensions

Taste lives in a small shared space. Components are *stimuli* that expose parts
of that space, not private namespaces.

```text
shape        radius · borderWeight · geometry
density      spacing · padding · controlHeight · informationDensity
emphasis     contrast · elevation · weight · saturation
typography   scale · weight · tracking · hierarchy
surface      fill · border · elevation · transparency
motion       speed · amplitude · easing
composition  alignment · whitespace · grouping · hierarchy
```

The dimension list is finite, versioned and part of the catalog contract. It is
allowed to grow; it is not allowed to grow per component.

### Component capability manifests

A component declares which dimensions it exposes, how each maps onto its own
props, and how its finite values project onto the shared ordinal scale:

```text
Button
  shape.radius          → /appearance/radius     square 0.0 · soft 0.5 · pill 1.0
  density.controlHeight → /appearance/size       compact 0.0 · regular 1.0
  density.padding       → /appearance/density    compact 0.0 · comfortable 1.0
  emphasis.weight       → /appearance/fontWeight regular 0.0 · semibold 1.0
  emphasis.contrast     → /appearance/recipe     ghost 0.0 · outline 0.33 · secondary 0.66 · primary 1.0

Card
  shape.radius          → /appearance/radius     none 0.0 · sm 0.33 · md 0.66 · lg 1.0
  surface.elevation     → /appearance/emphasis   quiet 0.0 · raised 1.0
  surface.border        → /appearance/border     none 0.0 · hairline 0.5 · solid 1.0
  density.padding       → /appearance/padding    tight 0.0 · regular 0.5 · loose 1.0
```

The value scale is what makes transfer possible: `Button.radius=square` and
`Card.radius=none` are different tokens and the *same* point on
`shape.radius`. A model never sees the normalized number as a free parameter —
it still proposes catalog values, and the engine still validates them.

Adding a component becomes: renderer + manifest. No learning code changes.

### What an observation now teaches

One judgment produces evidence at several altitudes at once:

```text
Preference(component, context) =
    GlobalTaste + RoleTaste + ContextTaste + ComponentResidual + Interaction
```

Accepting a square, compact, regular-weight Button is evidence for
`shape.radius → angular`, `density.padding → compact`, `emphasis.weight →
restrained` — *and* a Button-scoped residual. When the same person later keeps a
raised Card, the contradiction is visible on `surface.elevation` rather than
being invisible in a separate Button namespace.

Residuals are first-class, not error terms: "angular everywhere, but pill is
fine on chips" is a real taste statement and must survive into the artifact.

## Context taxonomy

The current `DesignContext` is 2×4×2 positional cells and cannot represent the
motivating case — round buttons in a playful product, square in a serious one
read as the *same* context and therefore as a contradiction.

Context splits into two independent products:

```text
ProjectContext            UsageContext
  productKind               surface
  visualTone[]              semanticRole
  audience?                 density
  platform                  state
  brandProfile?
```

`ProjectContext` is a property of the *project or session*, not of the
artifact; `UsageContext` is where in a screen the stimulus sits. Retrieval
relations (`exact` / `compatible` / `global` / `mismatch`) are computed per
axis, so "same usage, different product tone" is a legible relation instead of
a contradiction. `AtomicScope` stays as the subject axis.

Migration: the 95 existing rows have no `ProjectContext`, and 61 of them have
neither `scope` nor `outcome`. They are read as `unspecified`, rank below any
row that names a project context, and are never rewritten. Where they are used
in evaluation, they are reported as a separate legacy stratum rather than
silently pooled.

## Acquisition: the taste bench

The present canvas is a 561-line single screen with 336 lines of CSS, one
surface at a time, everything visible simultaneously. It is optimized for
demonstrating the pipeline, not for collecting preference. It gets replaced for
acquisition work (it remains as the refinement/debug view).

### Signals to collect

Absolute reactions alone are the weakest and noisiest preference signal. The
bench collects five, and they are additive, not alternatives:

| Signal | Question | Existing support |
| --- | --- | --- |
| absolute | do I like this? | implemented |
| **pairwise, same context** | A or B? | `pairwise_choice` exists in the schema, no UI produces it |
| **pairwise, cross-context contrast** | same stimulus, two project tones — which fits which? | does not exist |
| critique | why? | implemented |
| manual edit | what would I do instead? | implemented |
| almost | how close was it? | implemented |

Cross-context contrast is the only signal that directly discovers
*conditionality*, which is the product's central claim.

### The screen

One stimulus at a time, full-bleed, no scroll, keyboard-first:

```text
┌──────────────────────────────────────────────────────────┐
│  serious · saas · desktop        Field · molecule   12/30 │
├────────────────────────────┬─────────────────────────────┤
│                            │                             │
│            A               │              B              │
│                            │                             │
├────────────────────────────┴─────────────────────────────┤
│  ← A    → B    ↓ either    ↑ neither    c critique  e edit│
└──────────────────────────────────────────────────────────┘
```

Critique and the token inspector are on-demand overlays (`c`, `e`), not
permanent panels. A session is a fixed-length queue and ends with a summary of
what moved: dimensions that gained strong evidence, dimensions that became
contradictory, dimensions still unknown.

The stimulus queue is chosen to cover the dimension space, not by component
popularity, and deliberately reserves held-out components.

### Storybook becomes the workbench it was meant to be

Storybook is installed (`@storybook/react`, `addon-a11y`) with exactly one
stories file — six Button stories plus one grouped render. The
`ui.storybook_matches_catalog` assertion is currently proven by
`build-storybook` merely succeeding, which proves nothing about the catalog.

In this phase: every registered component gets stories generated from the
catalog — one per documented state, plus a *dimension sweep* story per declared
capability — and the assertion is rewritten to compare the story set against
the catalog registry and fail when they diverge. Storybook is where a component
is reviewed in isolation; the bench is where taste is acquired.

## The provider contract, and a decision about DSPy

`DSPyRefineProvider` is dead code: the class is declared and never referenced
anywhere else in the repository, `configured_provider()` can only return the
OpenAI-compatible or deterministic providers, and `dspy` is an optional
dependency. The signature that was supposed to be the portable, optimizable,
cross-agent contract has never executed.

That is a real loss, because the signature is exactly what makes the next claim
true: **a model family is not a safety boundary — the protocol is.** GLM, Kimi
and GPT can all be asked for the same `CandidatePatch` JSON through the same
declared signature, and the engine validates all of them identically. Taste
portability into *unconstrained* coding agents (write me any React app) is a
different, later problem and is out of scope here.

Decision for this phase: make DSPy the live path when a provider is configured,
behind the existing `RefineProvider` interface, so the signatures are exercised
by real traffic and the provider-boundary leak test covers them. Optimization
(MIPRO/GEPA) stays parked — it needs the corpus and the metric this phase
produces. If we are not willing to run it live, we delete the class and the
optional dependency in this phase instead; a declared-but-unreachable contract
is worse than no contract.

## The `.taste` artifact

### Shape

Sanitized observations are canonical; compiled preferences are a derived cache.
A rule compiler can be wrong, and a compiler that is the only source destroys
the evidence that would let us fix it. Recompiling must always be possible.

```text
.taste
├── meta                 id · version · dimensionSpaceVersion · catalogVersion
├── observations         canonical · sanitized · auditable
│     context · stimulus (dimension coordinates + concrete values) ·
│     outcome · eventIds · strength · source
├── preferences          derived · per dimension · per context mode
├── contextualModes      where a preference flips, with the evidence for the flip
├── componentResiduals   exceptions that do not generalize
└── unresolvedContradictions
```

Private material — critique text, before/after specs, parser interpretation —
never enters the file, exactly as `TasteBrief` already excludes it.

### Where it lives

Taste is personal data. Default location is per-user
(`~/.itl/taste/<profile>.taste`), **not** a file committed to a project repo. A
project references a profile by name; committing a profile is an explicit
opt-in, not the architecture.

Readers, in order of preference: an MCP tool (`get_taste(context)`) that
returns only the relevant slice, so context filtering happens before the prompt;
the file itself for agents without MCP; a compiled prompt block as the last
resort, with the loss of auditability stated.

## Evaluation

### Two held-outs, and only one of them is the main result

The primary split is **temporal / session hold-out**: earlier sessions train,
later sessions test, with every context having history.

```text
TRAIN  sessions 1-4   (hero, form, dashboard, toolbar)
DEV    sessions 5-6
TEST   sessions 7-9   (unseen sessions, seen contexts)
```

This answers "after it knows me, does it predict my next choice?" — the actual
product question.

Leave-context-out is a **secondary** benchmark and is reported separately as
OOD generalization. Asking the system to predict a context in which it has never
observed the person is asking it to extrapolate, and a system whose thesis is
"taste is contextual" is *allowed* to answer "insufficient evidence" there. A
weak OOD result does not falsify the thesis; it may confirm it. Conflating the
two would make a correct system look broken.

Two further splits exist only because this phase is multi-component:

| Split | Question | Strength of claim |
| --- | --- | --- |
| Seen-component | new stimulus, trained component | weakest |
| **Cross-component, shared dimension** | Button+Card+Input evidence → unseen Dialog | strong |
| **Held-out component** | never judged, only its manifest is known | strongest |

The held-out component test is what would make me believe ITL learns taste
rather than Button trivia.

### Baselines

| | Conditioning |
| --- | --- |
| A | no memory |
| B | global heuristic (majority preference, context-blind) |
| C | last relevant preference |
| D | raw retrieval (top-*k* evidence, evaluation harness only, never in the production provider path) |
| E | structured `.taste` / TasteBrief |

Metrics as specified in Plan 06: acceptance rate, pairwise win rate, top-1 hit
rate, regret, constraint violations, diversity. Read `E > D > A` as "retrieval
helps and structure helps beyond raw memory"; `E ≈ D > A` as "structure buys
auditability and portability, not accuracy".

### Sample size

95 judgments already exist. Roughly 200 more across the stimulus panel is a
planning figure, not a threshold. The stop rule is the confidence interval on
the primary metric, not a count: stop when the interval separates E from A, or
when it is tight around zero and the honest answer is "no measurable signal".
How many are needed depends on the effect size, which nobody knows yet.

Judgments must keep being collected against a **real provider**, as they have
been. The deterministic provider emits catalog-derived fixtures; preference data
collected against it would measure the fixture generator.

The existing 95 are usable for the pipeline and for the legacy stratum, but they
cannot carry the primary result on their own: one subject, one session ID, and a
context distribution of 74/11/10.

### Transfer test

Finally, the question that motivates the artifact: export `.taste`, hand it to a
second agent (Agent A → Agent B, GPT → GLM, GLM → GPT) through the same
signature, generate stimuli in held-out contexts, and have the person judge them
blind against stimuli generated without taste. If the person cannot tell them
apart, the artifact carries no signal, regardless of what the offline metrics
said.

## The stimulus catalog

The whole inventory is built in this phase. Not because a large catalog is
evidence of learning — it is not — but because the thesis cannot be tested
against a narrow one, and because after 07A a component costs a renderer and a
manifest rather than a change to the learning system.

Current state: **8 registered types, 2 of them editable**. Everything below is
the target.

| Level | Components | Count |
| --- | --- | --- |
| Foundation / primitive — *projection only, not a taste subject* | Typography scale, Aspect Ratio, Direction, Scroll Area, Resizable, Separator | 6 |
| Atom | Button, Input, Textarea, Label, Checkbox, Switch, Slider, Toggle, Native Select, Badge, Avatar, Progress, Spinner, Skeleton, Kbd, Marker, Item | 17 |
| Molecule | Field, Input Group, Input OTP, Button Group, Toggle Group, Radio Group, Select, Combobox, Date Picker, Calendar, Card, Alert, Empty, Tooltip, Popover, Hover Card, Accordion, Collapsible, Tabs, Breadcrumb, Pagination, Carousel, Attachment, Bubble, Message, Toast | 26 |
| Organism | Dialog, Alert Dialog, Drawer, Sheet, Command, Context Menu, Dropdown Menu, Menubar, Navigation Menu, Sidebar, Table, Data Table, Chart, Message Scroller, Questionnaire | 14 |
| Composition — the Blocks analogue shadcn does not ship | Form, Hero, Authentication, Settings region, Dashboard region, Checkout | 6 |

### Wave 1 cuts vertically, not horizontally

Building all 17 atoms before the first molecule would exercise one level for
weeks and never show the loop end to end. Wave 1 therefore takes a few
components from **every** category, chosen so that the slice is dependency-closed
— nothing in it slots a component outside it — and so that every dimension group
is exposed by at least three components across two levels.

| Level | Wave 1 |
| --- | --- |
| Foundation | token projection (already exists) |
| Atom | Button, Input, Label, Checkbox, Badge, Item |
| Molecule | Field, Card, Alert, Tabs, Button Group |
| Organism | Dialog, Sidebar, Table |
| Composition | Form, Hero |
| Reserved held-out | Popover — built, rendered, never judged |

Seventeen components. At the end of Wave 1 the entire loop is runnable on
heterogeneous stimuli: bench → judgments across four levels → `.taste` →
evaluation, including a first, small version of the held-out-component test via
Popover.

Composition order still constrains the later waves — a Field needs a Label and
an Input, a Data Table needs a Checkbox and a Pagination — so they fill in by
level:

| Wave | Set |
| --- | --- |
| B1 | vertical slice above (17) |
| B2 | remaining atoms (11) |
| B3 | remaining molecules (21) |
| B4 | remaining organisms (11) |
| B5 | remaining compositions (4) |

Each wave ships green — registered schema, renderer, capability manifest,
documented states, generated stories, a11y checks — so the phase never becomes a
long dark period, and the loop is measurable from the end of B1 rather than the
end of B5.

### Held-out components

Five components are built, rendered and documented like every other, and are
**never shown during acquisition**: Popover, Accordion, Hover Card, Carousel and
Data Table. Their manifests are known; no judgment about them is ever collected
in training. They exist to answer the strongest question in the evaluation —
whether taste predicts preference on a component the person was never asked
about.

Popover lands in Wave 1 precisely so that this test can run in miniature as soon
as the first slice is complete, instead of waiting for the whole inventory.

The reservation is enforced by the acquisition queue, not by convention, and a
test fails if a held-out component appears in a training judgment.

### Why 57 components is tractable, and what makes 20,000 imaginable

A component today is duplicated across four places: a Zod schema, a Pydantic
model, a React renderer and its stories. Written by hand 57 times that is the
main cost of this phase, and it is exactly the duplication that would make
20,000 impossible.

So the component becomes **data, not code**: one declarative definition per
component — props and their finite values, documented states, allowed children,
taste capabilities and value-scale projections — from which the build generates
the Zod schema, the Pydantic model, the story set and the manifest. Only the
renderer stays hand-written, because it is React and it carries the
accessibility contract.

That collapses the per-component cost to a declaration plus a renderer, makes
TypeScript/Python drift structurally impossible instead of merely tested, and
turns "add 20,000 components" into a data problem.

## Delivery

| Sub-phase | Work | Gate |
| --- | --- | --- |
| 07A — **delivered** | Corpus integrity first: one unambiguous database path, real session IDs from the client, legacy rows marked. Then the shared dimension space, capability manifests, value-scale projection, `ProjectContext` × `UsageContext`, and evidence recorded at dimension altitude. Includes the already-delivered generic subject registry, scoped retrieval and `TasteBrief` v3. | `pnpm verify:multi-component-taste` |
| 07B | Declarative component definitions and their code generation, then the full catalog in four dependency-ordered waves (17 atoms → 26 molecules → 14 organisms → 6 compositions), each with renderer, manifest, states, generated stories and a11y checks. Real `ui.storybook_matches_catalog` assertion. | `taste.stimulus_catalog_covers_the_dimension_space` |
| 07C | Taste bench: single-stimulus screen, pairwise same-context and cross-context contrast, keyboard flow, session summary. DSPy live or removed. | `taste.bench_acquires_pairwise_and_contextual_signal` |
| 07D | `.taste` export/import, MCP reader, evaluation harness with the four splits and five baselines. | `taste.portable_artifact_round_trips_and_is_evaluated` |

Acquisition itself — sitting down and judging — is human work between 07C and
07D, not a code deliverable. It is the thing everything else exists to enable.

## Guardrails

- A model chooses catalog values and registered compositions only. Normalized
  dimension coordinates are an internal representation; they are never a free
  parameter a model may emit.
- `TasteBrief` remains the only memory artifact crossing the provider boundary,
  and the leak test extends to the DSPy adapter.
- Observations stay canonical. A compiled preference that cannot name its
  evidence IDs does not enter the artifact.
- Taste files are personal by default. No profile is committed without an
  explicit choice.
- Contradiction and uncertainty are outputs, not failures. A dimension with
  conflicting evidence is reported as conflicting.
- No prompt optimization, DSPy compilation or learned taste model until the
  held-out evaluation exists and shows signal.

## Decisions taken against earlier proposals

Recorded so they are not re-litigated:

- **Context hold-out is secondary, not primary.** Temporal/session hold-out is
  the main benchmark; asking for a context never observed tests extrapolation,
  which the thesis does not claim.
- **Foundations do not come before transfer.** Token-level editing is valuable,
  but building a full foundation→atom→molecule inheritance system before knowing
  whether taste transfers at all is building on an untested hypothesis. Shared
  dimensions give most of the propagation benefit without that bet.
- **`.taste` is not rules-only.** Sanitized observations are canonical; compiled
  rules are a rebuildable cache.
- **`.taste` is not a git-committed file by default.** It is personal data in
  per-user storage, referenced by projects by name.
- **A model family is not the safety boundary.** GLM and Kimi go through the
  same signature and the same validator. Unconstrained coding agents are a later
  phase with a different contract.
- **Button is not the research domain.** It stays as the loop's smoke fixture.

## Acceptance criteria

- [x] The preference store resolves to one path regardless of working directory, and every recorded judgment carries a real session ID. (proof: assertion:taste.corpus_resolves_to_one_path_with_real_session_ids)
- [x] Every registered component declares its taste capabilities, and one judgment records evidence on shared dimensions plus a component residual. (proof: assertion:taste.dimensions_are_shared_and_component_declared)
- [x] A preference recorded on one component changes retrieval for a different component that shares the dimension, and does not change dimensions it does not share. (proof: assertion:taste.shared_dimension_evidence_transfers_without_leaking)
- [x] `ProjectContext` and `UsageContext` are independent axes, and the same usage under two product tones is a compatible relation rather than a contradiction. (proof: assertion:taste.project_and_usage_contexts_are_independent_axes)
- [ ] Every component in the target inventory is registered with a schema, a renderer, a capability manifest and documented states, and its schema is generated from one declaration rather than written twice. (proof: deferred: `taste.stimulus_catalog_covers_the_dimension_space`)
- [ ] Every declared dimension is exposed by at least three components across two Atomic levels, and the five held-out components never appear in a training judgment. (proof: deferred: `taste.stimulus_catalog_covers_the_dimension_space`)
- [ ] Storybook renders every registered component's states and dimension sweeps from the catalog, and the assertion fails when stories and catalog diverge. (proof: deferred: `taste.stimulus_catalog_covers_the_dimension_space`)
- [ ] The bench records same-context pairwise and cross-context contrast judgments, on one screen without scrolling, entirely from the keyboard. (proof: deferred: `taste.bench_acquires_pairwise_and_contextual_signal`)
- [ ] The DSPy signature path is exercised by the live provider and carries no private event fields — or the adapter and its dependency are removed. (proof: deferred: `taste.bench_acquires_pairwise_and_contextual_signal`)
- [ ] A `.taste` file round-trips: export, import into a clean store, and reproduce the same retrieval result for the same query. (proof: deferred: `taste.portable_artifact_round_trips_and_is_evaluated`)
- [ ] The harness reports baselines A–E over temporal, leave-context-out, cross-component and held-out-component splits, and the held-out-component result is reported separately. (proof: deferred: `taste.portable_artifact_round_trips_and_is_evaluated`)
- [x] The multi-subject loop and its scoped, non-propagating retrieval remain green. (proof: assertion:atomic.taste_loop_runs_on_more_than_one_editable_subject)

## Out of scope

Foundation token editing as a taste subject; learned prompt compilation, MIPRO
or GEPA; taste portability into unconstrained code-generating agents;
multi-person or team taste; visual regression or VLM judging. Components outside
the inventory above — the inventory is the scope, not a sample of it.

## After this phase

Only two branches, decided by the held-out result:

- **Signal exists** → foundation-level learning, the remaining catalog, and
  prompt optimization against a real metric.
- **No signal** → the representation is wrong, and the next phase is about
  acquisition and representation, not more components.

# Plan 05 — Contextual Button laboratory

## Goal

Make Button a complete, contextual preference-learning laboratory before adding
another editable component. A critique becomes evidence plus executable
attribute directives; candidates are coherent recipes rather than arbitrary
token combinations.

**Exit condition:** the web app sends every refinement request to the API, a
Button event persists typed context/evidence/directives, and the deterministic
engine produces directional exploit, adjacent, and opt-in named wild candidates.

## Contract

- `PreferenceEvidence` records what the person liked/disliked/locked; it is not
  the mutation language.
- `AttributeDirective` is one of `keep`, `avoid`, `prefer`, `set`, `increase`,
  `decrease`, or `explore`, scoped only to visual paths.
- Button splits `content.label`, `semantic.role/state`, and visual
  `appearance.recipe/size/radius/density/fontWeight`. State is never a taste
  dimension.
- `DesignContext` is typed: Button role, surface (`toolbar`, `hero`, `form`,
  `dashboard`), and contextual density.
- Recipes (`primary`, `secondary`, `outline`, `ghost`) derive background,
  foreground, border, hover, and focus tokens. Generated specs cannot express
  those implementation tokens independently.
- An interpretation is transient until the person confirms it. Only then is it
  persisted as `confirmed_critique`; an unconfirmed parser result is not
  elevated to evidence.
- `candidate_acceptance` and `pairwise_choice` are separate actions.
  Candidate identity is stored in `candidateId`, never overloaded into an
  element ID.
- Retrieval reports two independent relations: context (`exact`, `compatible`,
  `global`, `mismatch`) and preference (`supporting`, `conflicting`,
  `unknown`). A different surface is not itself a contradiction.
- For the MVP, live OpenAI-compatible providers remain direct, JSON-only HTTP
  adapters. DSPy is optional experimentation infrastructure, not a hidden
  runtime dependency; `GenerateVariants` is removed because candidate
  materialization is deterministic.

## Work sequence

1. Export the Button manifest from `ui-catalog` into
   `contracts/catalog/button.v1.json`; test that Python and TypeScript accept
   the same visual vocabulary.
2. Replace `PatchIntent` with evidence and discriminated directives. Prove
   `soft + decrease(radius)` produces `square`, never `pill`.
3. Materialize candidates deterministically: exploit follows the directive,
   adjacent adds one nearby coherent visual change, and wild applies an opt-in
   named recipe centroid while preserving explicit keeps.
4. Remove local critique/variant generation from the web app. The browser uses
   typed HTTP clients for parse, variants, and events; TypeScript remains the
   catalog/rendering authority.
5. Add static toolbar, hero, and form surfaces around the one editable Button.
   Events store `DesignContext` rather than an opaque context string.
6. Migrate preference events to persist context, evidence, directives, and a
   before/after spec diff. Implement retrieval only after this data is real:
   component + role + surface + evidence strength, no embeddings.
7. Run several local sessions, retain the raw observations, then decide whether
   Input, Card, or any molecule is justified.

The adjacent budget is revised together with the policy semantics; it must be
expressed directly as a ratio, not inferred from enum indexes.

## Acceptance criteria

- [ ] A directional critique is compiled to a directive and cannot move in the opposite direction. (proof: assertion:button.directives_preserve_direction)
- [ ] Every generated Button uses a coherent recipe and never independently controls implementation colors or borders. (proof: assertion:button.recipes_are_coherent)
- [ ] State and content are excluded from visual preference directives. (proof: assertion:button.taste_space_is_visual_only)
- [ ] The canvas uses the API refinement boundary and stores a typed context for toolbar, hero, and form sessions. (proof: assertion:button.web_uses_api_and_typed_context)
- [ ] Retrieval ranks matching component/role/surface evidence over a contextual mismatch without deleting the mismatch. (proof: assertion:button.retrieval_is_contextual)

## Deterministic completion gate

`button-contextual-lab` activates on the catalog contract, Button renderer,
refinement boundary, memory migrations, and canvas contexts. Its fixture corpus
contains the directional-radius negative case, incoherent-recipe rejection,
all three static contexts, and conflicting contextual evidence. Seal only a
fresh passing report with `sf seal button-contextual-lab`.

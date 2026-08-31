# Plan 02 — Controlled UI language and component workbench

## Goal

Define the smallest safe UI language that an AI may produce, then render that
language with real React components. Prove that a JSON spec is valid, selected
by element ID, and visually inspectable before adding any LLM behavior.

**Exit condition:** The app and Storybook both render the same validated
Button, Input, Badge, and Card specs from one versioned catalog, and invalid
or unsupported specs never reach the renderer.

## Scope and decisions

- Adopt `@json-render/core` and `@json-render/react` as the UI-spec IR and
  renderer. Its flat `root` plus `elements` structure is canonical because it
  gives every target element a stable ID for selection and patching.
- Build custom MVP components rather than adopting a ready-made visual catalog.
  The product needs a deliberately controlled aesthetic space, not arbitrary
  CSS or a vendor design system.
- Use Storybook as the design-system workbench, documentation surface, and
  isolated state test harness. It is not the source of truth for UI specs.
- Begin with atoms: Button first, then Input and Badge. Card is the one
  bounded molecule in this phase because it composes registered child atoms;
  do not model organisms, templates, or page composition yet.
- Each variable visual property is a finite enum/token. Raw CSS, Tailwind
  class strings, arbitrary colors, and free-form pixel values are forbidden in
  the generated spec.

## Work sequence

1. Define a versioned `UISpec` schema, stable element IDs, allowed parent-child
   relationships, and catalog metadata (`atom` level plus editable prop paths).
   Validate with Zod at runtime and derive TypeScript types from the schema.
2. Define the first Button prop surface: `label`, `variant`, `size`, `radius`,
   `density`, `background`, `foreground`, `border`, `fontWeight`, and explicit
   semantic/interaction state. Keep the initial option set intentionally small.
3. Implement the Button from design tokens, not from per-instance ad hoc CSS.
   Include normal, hover, focus-visible, disabled, and loading states. Give it
   an accessible name and native `<button>` semantics.
4. Register Button in the json-render catalog and build an adapter that accepts
   only schema-valid specs. Unknown components, invalid enum values, dangling
   child IDs, cyclic references, and unknown props must produce a typed
   validation failure.
5. Add a canvas that renders a fixed fixture spec. It must expose element IDs
   to the selection layer without making the generated JSON depend on DOM IDs.
6. Add Storybook stories for each controlled Button family and state. Stories
   should make the permitted design space legible: technical/square, subtle,
   outline, compact, disabled, loading, and focus-visible.
7. Repeat the minimum schema/component/story pattern for Input and Badge only
   after the Button contract is proven. Then add Card as a bounded molecule
   that may host registered element IDs, without inventing a generic layout
   language.
8. Add unit tests for schema/catalog failures and UI tests for native semantics
   and focus behavior. Add Storybook accessibility checks and a small set of
   stable visual-state tests once a browser runner is selected.

## Guardrails

- JSON is the canonical UI state; screenshots are diagnostic projections only.
- AI-facing props are constrained semantic choices. A generator cannot emit
  executable code, event handlers, arbitrary styles, external URLs, or new
  component types.
- Component metadata declares its Atomic Design level. The model never decides
  whether something is an atom or molecule.
- Accessibility and schema validity are hard gates, never weighted against
  visual taste.

## Acceptance criteria

- [ ] A valid flat JSON spec renders its registered Button deterministically in the web canvas. (proof: assertion:ui.valid_spec_renders_deterministically)
- [ ] Invalid shape, unknown props, unknown components, bad references, and cycles are rejected before React rendering. (proof: assertion:ui.invalid_specs_fail_closed)
- [ ] Button states expose native semantics, accessible naming, focus visibility, disabled behavior, and loading behavior. (proof: assertion:ui.button_accessibility_states_pass)
- [ ] Every generated visual choice comes from a documented finite token/enumeration set. (proof: assertion:ui.generated_props_are_constrained)
- [ ] Storybook shows the same registered components and supported states as the product renderer. (proof: assertion:ui.storybook_matches_catalog)

## Verification procedure

1. Run schema tests with fixtures for valid and malformed specs, including a
   cycle and a dangling element ID.
2. Render a Button fixture in the app and Storybook; assert identical props
   are passed to the shared component.
3. Run accessibility tests for the Button states and keyboard focus.
4. Run the factory checks after adding source files; enable and scope the L1
   rules as described in Plan 01.

## Deterministic completion gate

`controlled-ui-language` activates only on catalog, component, canvas, and
Storybook implementation paths. Its evidence command must run schema fixtures,
the shared-component parity check, and accessibility/state tests in a fixed
browser. The raw JSON report must contain these passed assertions:

- `ui.valid_spec_renders_deterministically`
- `ui.invalid_specs_fail_closed`
- `ui.button_accessibility_states_pass`
- `ui.generated_props_are_constrained`
- `ui.storybook_matches_catalog`

The report includes negative fixtures for unknown components/props, invalid
references, cyclic trees, and an inaccessible Button state. It is sealed only
with `sf seal controlled-ui-language`; any activation-path edit stales it.

## Explicit non-goals

- No free-form HTML/CSS, code export, streaming renderer, page generator, or
  visual-taste judge.

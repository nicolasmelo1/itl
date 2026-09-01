# Atomic Design system for ITL

## Product decision

ITL will implement the whole Atomic Design model, not stop at a Button lab.
The Button is simply the first currently editable atom. The system has six
layers: **foundations**, then the five Atomic Design levels — **atoms,
molecules, organisms, templates, and pages**.

Foundations are deliberately listed separately. They are not a sixth stage in
Brad Frost's method; they are the shared design decisions that make every one
of the five stages consistent. The method is also not a one-way waterfall: a
page can expose a missing atom, and an organism can reveal a template rule.

The machine-readable inventory is [atomic-design.v1.json](../contracts/catalog/atomic-design.v1.json).

## The layers

| Layer | What it owns | Examples | What it must not own |
| --- | --- | --- | --- |
| Foundation | The visual and behavioural language | color, type scale, spacing, grid, radius, elevation, motion, breakpoints, focus | Product layout or component-specific content |
| Atom | One accessible primitive with a narrow responsibility | Label, TextInput, Select, Button, Icon, Badge, Text, Avatar | Arbitrary layout or a business flow |
| Molecule | A small, stable composition that does one thing | Field, SearchField, ButtonGroup, Card, Breadcrumbs, Alert | Page sections or route-level layout |
| Organism | A distinct functional section | AppHeader, Hero, Sidebar, FilterPanel, AuthenticationForm, DataTable, Footer | A route's outer layout and concrete business data |
| Template | Responsive layout, regions and information hierarchy | AppShell, Dashboard, Settings, Marketing landing, Checkout | Final copy, data or personalized route decisions |
| Page | A concrete template instance with real content and state | `/projects/acme/settings`, a populated billing page, a specific article | New, unreviewed component structure |

### Foundations: the full first layer

Foundations are not only `font`, margin and border. They include:

- **Token architecture:** primitive values, semantic aliases and the rare
  component token; light/dark or brand modes; aliases rather than duplicated
  raw values.
- **Typography:** font family, weight, size, line height, tracking, text
  styles and semantic roles (display, heading, body, label, caption, code).
- **Spatial system:** spacing scale, sizing, layout grid, container widths,
  breakpoints and responsive rules.
- **Visual language:** color roles, border width/style, radius, opacity,
  elevation, iconography and illustration rules.
- **Interaction language:** focus treatment, states, motion duration/easing,
  reduced-motion alternative, cursor and affordance rules.
- **Cross-cutting constraints:** contrast, keyboard navigation, target size,
  localization, content style and data-density guidance.

Tokens are portable named decisions, not CSS variables by definition. ITL will
store the canonical token source in the Design Tokens Community Group shape,
then compile it to CSS and future platform targets. CSS variables are one
output, not the model-facing source of truth.

### Atoms

The atom catalog is deliberately broader than a few form controls:

| Group | Atoms |
| --- | --- |
| Content | Text, Heading, Label, HelpText, Link, Code, Divider |
| Identity/media | Icon, Avatar, Image, Logo, StatusIndicator |
| Actions/feedback | Button, IconButton, Badge, Tag, Spinner, Skeleton, Progress |
| Text entry | TextInput, Textarea, NumberInput, PasswordInput |
| Choice | Checkbox, Radio, Switch, Select, Combobox, DateInput |
| Accessibility primitives | VisuallyHidden, FocusRing, LiveRegion |

An atom has a documented anatomy, semantic role, variants, states, keyboard
behaviour, content constraints, token dependencies and a finite prop schema.
It can be reviewed in isolation, but a preference recorded for it is always
scoped by role and context.

### Molecules

Molecules are not “anything larger than an input.” They are intentionally
small compositions with one responsibility and named slots. Examples:

- **Field:** Label + control + optional hint/error/status.
- **SearchField:** input, search action and optional clear action.
- **InputGroup / ButtonGroup / FormActions:** related actions or controls.
- **MenuItem, NavItem, Breadcrumbs and Pagination:** a navigational unit.
- **Alert, EmptyState and Card:** bounded feedback or content unit.

A molecule may use atoms; it cannot become an unbounded generic container.
This is why the current Card is a molecule and cannot recursively contain
another Card.

### Organisms

An organism combines molecules and atoms into a recognizable interface
section, with an explicit functional boundary. The initial catalog covers:

- AppHeader and PrimaryNavigation;
- Sidebar and contextual navigation;
- Hero and promotional content block;
- AuthenticationForm and settings form section;
- FilterPanel and DataTable;
- Dialog, ToastRegion and Footer;
- ContentFeed / result-list section.

An organism documents its allowed child compositions, slots, empty/loading/
error states, responsive collapse behaviour, and accessibility ownership. For
example, `AppHeader` owns landmark/navigation semantics while `SearchField`
owns text-entry behaviour.

### Templates and pages

Templates are not generic organisms. They own layout: regions, grid, ordering,
responsive rearrangement and representative content. Initial templates are
AppShell, MarketingLanding, Authentication, Dashboard, Settings, ContentDetail
and Checkout.

Pages are named route instances of a template. They bring real content, data,
permissions, loading/error state and analytics context, but cannot bypass the
catalog by emitting novel layout or styling. Comparing pages is valuable: it
shows whether a rule really survives realistic content and data density.

## What the catalog must contain

Every catalog entry — at any renderable layer — has this contract:

```text
id + Atomic Design level + semantic purpose + anatomy/slots
+ finite variants and states + allowed children
+ token dependencies + responsive policy + accessibility contract
+ content/localization constraints + test fixtures + prompt guidance
```

The current JSON UI registry validates component identity and prop values. It
will be expanded with layer, slot and child-level validation: atoms have no
renderable children; molecules accept allowlisted atoms; organisms accept
allowlisted atoms/molecules; templates accept reviewed sections; pages select a
template and concrete data. No model may use arbitrary CSS, HTML, actions or
unknown components.

## Taste-learning model

The learning unit is a **decision**, not a screenshot and not a universal
“beautiful” score. Each immutable event records:

```text
subject (token | component | composition | template | page)
+ Atomic Design level + semantic role + usage context + project context
+ before/after validated spec + explicit feedback/directives
+ source/confidence + supporting or conflicting event IDs
+ accessibility/responsive validation results
```

### Two context axes

Where a stimulus sits on a screen and what the product is trying to be are
independent questions. `UsageContext` holds surface, semantic role, density and
state; `ProjectContext` holds product kind, visual tone, audience, platform and
brand profile, and belongs to the project or session rather than to the
artifact. Retrieval compares each axis separately, so round buttons in a
playful product and square ones in a serious one are the *same usage under two
product tones* — a compatible relation — instead of one person contradicting
themselves. A judgment that names no project context is read as unspecified and
ranks below one that does; it is never rewritten.

### Shared taste dimensions

A component does not own a private vocabulary. Taste lives in one finite,
versioned space — `shape`, `density`, `emphasis`, `typography`, `surface`,
`motion`, `composition` — declared in
[the dimension contract](../contracts/catalog/taste-dimensions.v1.json). Each
component publishes a **capability manifest**: which dimensions it exposes,
which of its own props expose them, and where each finite value lands on the
shared 0–1 scale. `Button.radius=square` and `Card.radius=none` are different
tokens and the same point on `shape.radius`.

One judgment therefore teaches at two altitudes: the shared dimensions the
stimulus expressed, and a **component residual** — the distance between that
component's own reading and the shared one. A residual is a taste statement in
its own right ("angular everywhere, but pill is fine on chips"), not an error
term. Contradiction is likewise an output: a dimension with conflicting
evidence is reported as conflicting rather than averaged into agreement.

The normalized coordinate stays internal. A model still proposes catalog values
and the engine still validates them; the shared scale never becomes a free
parameter a provider may emit.

Evidence moves upward only by an explicit, inspectable rule:

| Decision | May inform | Must not automatically become |
| --- | --- | --- |
| Foundation token in a compatible theme/context | all layers using that token | a mandate for unrelated themes or semantic roles |
| Atom decision | that atom and mapped roles | a global rule for every control |
| Any decision, at dimension altitude | any component declaring the same dimension | a reading on a dimension that component does not declare |
| Molecule/organism composition decision | the same composition in compatible context | a mutation of its atoms' defaults |
| Template decision | pages using that template | a universal page layout |
| Page outcome | the same task/content context | a template rule without review |

This produces two separate, versioned artifacts for a future UI-generating
model:

1. **Design-system manifest:** allowed tokens, components, levels, slots,
   variants and validation rules.
2. **Taste brief:** only confirmed, contextual decisions with source,
   confidence, evidence IDs, conflicts and explicit exclusions.

The generation request names a task and template. The model receives the
relevant slice of both artifacts, proposes only a validated spec, and logs the
brief/version/event IDs that affected it. It does not receive a vague prose
claim such as “the user likes minimalist UI.”

## Learning loops

The **20–40 minute loop** is a bounded learning session, not an attempt to
finish the hierarchy in one sitting:

| Time | Work | Output |
| --- | --- | --- |
| 0–5 min | Choose task, context, layer and starting reference | session scope and constraints |
| 5–15 min | Review 1–3 foundation/atom decisions | confirmed token or atom evidence |
| 15–30 min | Compose the same decisions into one molecule or organism | bounded, renderable candidate |
| 30–40 min | Test realistic content/state, accept/reject and promote only explicit rules | events + updated taste brief |

When the selected scope is a template or page, the same loop starts from a
reviewed composition instead of revisiting every atom. The user can also stay
at one layer for a whole loop; uncertainty is a valid result and should not be
promoted.

## Delivery sequence

This is the full system; delivery is incremental to preserve testable
boundaries:

1. Canonical DTCG tokens and token compiler; foundation inspector and modes.
2. Complete atom library and state/accessibility fixtures.
3. Molecule library, beginning with Field, search, navigation and feedback.
4. Organism library with responsive and async states.
5. Template registry with named slots, grid and breakpoint contracts.
6. Page adapter connecting routes/data to reviewed templates.
7. Versioned manifest + taste brief injection and audit in every AI request.

Each stage may be built in parallel with the others conceptually, as Atomic
Design intends; it becomes available for learned generation only when its
catalog and validation fixtures are complete.

## References

- Brad Frost, [Atomic Design Methodology](https://atomicdesign.bradfrost.com/chapter-2/)
  — the five levels, their examples, and the explicit warning that the model is
  not a linear process.
- Design Tokens Community Group, [Design Tokens Format Module](https://www.w3.org/community/reports/design-tokens/CG-FINAL-format-20251028/)
  — portable token names, values, types and groups.
- U.S. Web Design System, [Design tokens](https://designsystem.digital.gov/design-tokens/)
  and [component/pattern guidance](https://designsystem.digital.gov/) — a
  practical reference for discrete visual vocabulary and accessibility-aware
  components and patterns.

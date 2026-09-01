# Interactive Taste Learning (ITL)

ITL is a local laboratory for learning a person's UI taste through a constrained refinement loop. It edits registered subjects at two Atomic Design levels today—the `Button` atom and the `FormField` molecule—through one catalog-derived loop. A short session starts with foundations (type, spacing, borders and focus), refines one subject, then eventually composes organisms, templates, and pages. The goal is not a generic style score: it is contextual, reviewable taste evidence that can later guide UI-generation prompts.

The browser renders a finite, schema-validated JSON UI spec. A person selects an editable component in a toolbar, hero, or form, writes a critique, reviews the interpreted visual directives, then asks the API for constrained alternatives. Explicit actions are recorded as append-only SQLite events with typed role, surface, density, evidence, directives, and a spec diff.

The application is deliberately narrow at this stage: two registered editable subjects, controlled JSON UI specs (never screenshots), deterministic validation, and no global "beauty" score or vector database. Each subject's evidence is retrieved separately: an atom decision never becomes a molecule rule by accident. Judgments are *also* recorded in a shared, versioned taste dimension space, so a preference expressed on one component is readable on another that declares the same dimension — and on nothing else. The complete target architecture is documented in [the Atomic Design system](docs/atomic-design-system.md) and its [versioned catalog contract](contracts/catalog/atomic-design.v1.json). Delivery happens in 20–40 minute loops, but the system's target includes every layer through concrete pages.

## Quickstart

### 1. Install

- Node.js 22.22+ and pnpm 11.21+
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)

```sh
pnpm install --frozen-lockfile
uv --directory apps/ai sync --locked
cp apps/web/.env.example apps/web/.env.local
cp apps/ai/.env.example apps/ai/.env
```

### 2. Start the API

```sh
pnpm dev:ai
```

The default is deterministic mode: no key, no network, and the local event log
is written to `apps/ai/data/preferences.db` (gitignored). A relative
`PREFERENCE_DATABASE_PATH` is anchored to the service, so the same corpus is
read and written whatever directory you start from. Confirm the API is live:

```sh
curl http://127.0.0.1:8000/health
```

### 3. Start the web app

```sh
pnpm dev:web
```

Open `http://localhost:3000`.

### 4. Run one refinement session

1. Leave the `Continue` button selected, or click the `Account email` field to refine the molecule instead.
2. Choose a toolbar, hero, or form surface, then enter a critique such as: “I like the recipe and spacing, but it is too rounded.”
3. Click **Review interpretation**. This is transient: no preference event is stored yet.
4. Adjust Keep/Explore if necessary and click **Generate constrained alternatives**. This confirms the critique and persists `confirmed_critique`; a parser result alone is never stored as evidence.
5. Accept an option, reject all, or give attribute feedback. An accepted variant is stored as `candidate_acceptance`; its candidate ID is separate from the UI element ID.

The browser sends interpretation and variant generation to FastAPI. TypeScript owns rendering and validates every returned spec before it is shown. A model proposes catalog-scoped patches; the API applies and validates them deterministically, then owns the SQLite memory boundary. The current spec is never mutated until the user accepts a rendered candidate.

## How it works

```text
subject spec → critique → review → model candidate patches → deterministic materialization → candidates → explicit event
                                     │                         │                                  │
                                     └── context + evidence ───┴──────── deterministic validation ──┘
```

- The editable vocabulary is finite, visual only, and per subject: a Button has `recipe`, `size`, `radius`, `density` and `fontWeight`; a FormField has `labelPlacement`, `gap` and `hintTone`. The model chooses combinations from the selected subject's catalog, but cannot provide CSS, colors, content, semantic state, or unregistered components. Every patch is checked for schema, catalog values, directives, locks, untouched content/state, and duplicate candidates before rendering.
- A raw event is never overwritten. Direct edits have stronger evidence than an inferred critique. Every judgment carries a real session ID; the API refuses a placeholder, because session hold-out is only as good as the identifier.
- Taste lives in a shared, versioned dimension space (`shape`, `density`, `emphasis`, `typography`, `surface`, `motion`, `composition`). Each component declares a capability manifest saying which dimensions it exposes, through which of its props, and where each finite value lands on the shared scale. One judgment produces evidence on those shared dimensions plus a component-scoped residual, and a dimension with conflicting evidence is reported as conflicting.
- Context is two independent axes. `UsageContext` is surface, semantic role, density and state; `ProjectContext` is product kind, visual tone, audience and platform, and belongs to the session rather than the artifact. Retrieval reports each axis separately, so the same usage under two product tones is a compatible relation rather than a contradiction. Preference relations remain supporting/conflicting/unknown.

## Optional model providers

Set provider values in `apps/ai/.env`; restart `pnpm dev:ai` after changing them. Never put provider keys in `apps/web/.env.local`, commit them, or expose them with a `NEXT_PUBLIC_` variable. The application starts safely in fixture mode if no provider is configured. That mode exists for local UI/API development; configure a model provider to dogfood creative alternative generation.

### Ollama Cloud

Ollama Cloud supports an OpenAI-compatible API. Create an Ollama API key and set the following values:

```dotenv
ITL_LLM_PROVIDER=ollama
OLLAMA_API_KEY=your_ollama_key
OLLAMA_BASE_URL=https://ollama.com/v1
OLLAMA_MODEL=gpt-oss:120b-cloud
LLM_TIMEOUT_SECONDS=120
```

Choose a cloud model enabled on your Ollama account. See Ollama's [Cloud API guide](https://docs.ollama.com/cloud) and [OpenAI-compatibility reference](https://docs.ollama.com/api/openai-compatibility).

### OpenAI API and a Codex subscription

A ChatGPT/Codex subscription authenticates the Codex product; it is not a server credential this project can reuse. To call a model from ITL, create an OpenAI API project key and use API credits/billing for that project:

```dotenv
ITL_LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
```

The OpenAI [API quickstart](https://platform.openai.com/docs/quickstart/make-your-first-api-request) explains creating and supplying an API key. Keeping this distinction explicit prevents copying Codex CLI or browser-session credentials into the app.

## Verify

Run all standard checks from the repository root:

```sh
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

The current deterministic completion gates are:

```sh
pnpm verify:controlled-ui-language
pnpm verify:memory-exploration-validation
pnpm verify:button-contextual-lab
pnpm verify:atomic-foundations
# Completion gate for Plan 06; it proves the registered slice and the multi-subject loop,
# not the full catalog inventory.
pnpm verify:atomic-design-system
# Completion gate for Plan 07A; it proves one corpus path with real session IDs, the shared
# dimension space and its capability manifests, dimension-altitude transfer without leakage,
# and the two independent context axes. Sub-phases 07B–07D are still open.
pnpm verify:multi-component-taste
```

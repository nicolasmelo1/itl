# Interactive Taste Learning (ITL)

ITL is a local laboratory for learning a person's UI taste through a constrained refinement loop. Today it deliberately edits only one component—`Button`—so the product can answer a hard question before growing into a design system: after several interactions, can it propose alternatives that fit a person and the current surface without collapsing into one generic style?

The browser renders a finite, schema-validated JSON UI spec. A person selects the Button, writes a critique, reviews the interpreted constraints, then asks the API for constrained alternatives. Explicit actions are recorded as append-only SQLite events. The service retrieves relevant evidence for later requests, while keeping evidence from another context visible rather than pretending it is a global rule.

The application is deliberately narrow at this stage: Button only, controlled JSON UI specs (never screenshots), deterministic validation, and no global "beauty" score or vector database.

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
is written to `data/preferences.db` (gitignored). Confirm the API is live:

```sh
curl http://127.0.0.1:8000/health
```

### 3. Start the web app

```sh
pnpm dev:web
```

Open `http://localhost:3000`.

### 4. Run one refinement session

1. Leave the `Continue` button selected.
2. Enter a critique such as: “I like the color and spacing, but it is too rounded.”
3. Click **Review interpretation**. This is transient: no preference event is stored yet.
4. Adjust Keep/Explore if necessary and click **Generate constrained alternatives**. This confirms the critique and persists `confirmed_critique`.
5. Accept an option, reject all, or give attribute feedback. An accepted variant is stored as `candidate_acceptance`; its candidate ID is separate from the UI element ID.

The browser sends interpretation and variant generation to FastAPI. TypeScript owns rendering and validates every returned spec before it is shown. The API owns the deterministic candidate policy and the SQLite memory boundary.

## How it works

```text
Button spec → critique → review → FastAPI interpretation → candidates → explicit event → SQLite evidence
                                      │                                  │
                                      └──── deterministic validation ─────┘
```

- The editable vocabulary is finite; arbitrary CSS, colors, and unregistered components are rejected.
- A raw event is never overwritten. Direct edits have stronger evidence than an inferred critique.
- Context is retained in memory. A mismatch is not automatically a conflicting preference.
- Current refinement semantics are intentionally conservative. The richer contextual Button contract is tracked in [Plan 05](plans/05-button-contextual-lab.md).

## Optional model providers

Set provider values in `apps/ai/.env`; restart `pnpm dev:ai` after changing them. Never put provider keys in `apps/web/.env.local`, commit them, or expose them with a `NEXT_PUBLIC_` variable. The application starts safely in deterministic mode if no provider is configured.

### Ollama Cloud

Ollama Cloud supports an OpenAI-compatible API. Create an Ollama API key and set the following values:

```dotenv
ITL_LLM_PROVIDER=ollama
OLLAMA_API_KEY=your_ollama_key
OLLAMA_BASE_URL=https://ollama.com/v1
OLLAMA_MODEL=gpt-oss:120b-cloud
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
```

# Interactive Taste Learning (ITL)

ITL is a local prototype for learning a person's UI taste through a constrained refinement loop. It generates and edits schema-validated Button specifications, asks the person what to keep or explore, and keeps an append-only local SQLite history of explicit feedback. Its goal is contextual preference learning: evidence from a dense dashboard must not silently become a rule for a marketing CTA.

The application is deliberately narrow at this stage: Button only, controlled JSON UI specs (never screenshots), deterministic validation, and no global "beauty" score or vector database.

## Requirements

- Node.js 22.22+ and pnpm 11.21+
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)

## Run locally

Install both workspace environments from the repository root:

```sh
pnpm install --frozen-lockfile
uv --directory apps/ai sync --locked
cp apps/web/.env.example apps/web/.env.local
cp apps/ai/.env.example apps/ai/.env
```

Use two terminals:

```sh
pnpm dev:ai
```

```sh
pnpm dev:web
```

Open `http://localhost:3000`. The AI service is available at `http://127.0.0.1:8000`; `GET /health` verifies it is running. With the default configuration, the app uses deterministic local fixtures and writes preference memory to `data/preferences.db` (gitignored), so no key or network connection is required.

## Optional model providers

Set provider values in `apps/ai/.env`; restart `pnpm dev:ai` after changing them. Never put provider keys in `apps/web/.env.local`, commit them, or expose them with a `NEXT_PUBLIC_` variable.

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

The deterministic completion gate for this phase is:

```sh
pnpm verify:memory-exploration-validation
```

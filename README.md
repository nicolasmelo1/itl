# Interactive Taste Learning

Interactive Taste Learning (ITL) is a pnpm workspace with a separate Python
service managed by uv.

## Architecture

Next.js and React render the product UI. FastAPI and DSPy interpret generation
requests. The processes communicate only through documented HTTP JSON routes;
the canonical UI representation is a JSON UI specification, never a screenshot.
SQLite will keep local preference evidence in the gitignored `data/` directory.
The web app never opens that database or imports Python-owned types.

## Local setup

```sh
pnpm install --frozen-lockfile
uv --directory apps/ai sync --locked
```

Copy the local templates when configuration is needed. Provider credentials are
optional: the web shell and `GET /health` run without them.

```sh
cp apps/web/.env.example apps/web/.env.local
cp apps/ai/.env.example apps/ai/.env
pnpm dev:web
pnpm dev:ai
```

Run all checks from the repository root with `pnpm lint`, `pnpm typecheck`,
`pnpm test`, and `pnpm build`.

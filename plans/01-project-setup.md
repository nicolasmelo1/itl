# Plan 01 — Project setup and reproducible guardrails

## Goal

Create a small, reproducible monorepo for the Interactive Taste Learning MVP.
This plan creates infrastructure only: it must not implement UI generation,
design components, or product flows.

**Exit condition:** A fresh checkout can install the pinned JavaScript and
Python dependencies, launch an empty web shell and API health endpoint, run
their quality checks, and pass `sf verify` plus `sf check`.

## Scope and decisions

- Use a pnpm workspace for the Next.js web application and shared TypeScript
  packages.
- Use a Python package managed by uv for the FastAPI/DSPy service. It is a
  separate process with a narrow HTTP contract; no Python code is imported by
  the web application.
- Reserve these package boundaries now, even if their implementation starts
  empty: `apps/web`, `apps/ai`, `packages/design-system`,
  `packages/ui-catalog`, and `packages/preference`.
- Keep persistent data local in a gitignored `data/` directory. SQLite is the
  sole persistence choice for the MVP.
- Do not install GEPA, a vector database, a queue, Redis, or a VLM. They do
  not test the first product hypothesis.
- Pin the package-manager metadata and use lockfiles. Environment variables
  belong in documented local templates, never in committed secret files.

## Work sequence

1. Record the architecture decision in project documentation: Next.js/React
   renders product UI; FastAPI/DSPy interprets requests; JSON UI specs cross
   the boundary; SQLite records preference evidence. State that a spec, not a
   screenshot, is the canonical representation.
2. Initialize the pnpm workspace and the web application with strict
   TypeScript. Configure only the scripts needed to type-check, lint, test,
   build, and run the development server. Do not add product components.
3. Initialize the Python application with a locked uv environment, FastAPI,
   and a minimal health route. Keep provider credentials optional: development
   and contract tests must run without an LLM API key.
4. Add one root task entry point for the common checks. It must run the web
   and Python checks independently so failures identify their owning package.
5. Add `.env.example` files containing names and explanations but no values.
   Validate at application startup that a generation route cannot accidentally
   use an absent provider key; the health route must remain available.
6. Configure formatters, linters, type checkers, and test discovery to ignore
   `.software-factory/mutations/`, whose intentionally invalid fixtures must
   never be interpreted as application defects.
7. Enable the L1 software-factory rules only after the first real TypeScript
   and Python source files exist. Add their scopes deliberately, run
   `sf verify`, then `sf check`; never silence an inert-rule report by adding
   placeholder source.
8. Add CI jobs that run the same install and quality commands from a clean
   checkout. Security tooling is deferred until the real package manifests
   exist, then added as L6 in the same change.

## Guardrails

- The web application may call only documented API routes; it may not open the
  SQLite file or import Python-owned types.
- The API must validate all external input at its boundary and return typed
  error payloads; provider errors must not be forwarded verbatim.
- No secret is committed, logged, or added to a Storybook story.
- No implementation-specific L0 layering rules are adopted yet. We wait for
  repeated structure rather than freezing a speculative architecture.

## Acceptance criteria

- [ ] The workspace has reproducible JS and Python lockfiles and documented local setup commands. (proof: assertion:setup.lockfiles_reproducible)
- [ ] The web shell and API health route run locally without provider credentials. (proof: assertion:setup.shells_start_without_provider)
- [ ] Each application has independent lint, type, unit-test, and production-build commands. (proof: assertion:setup.quality_commands_pass)
- [ ] Factory mutation tests pass and live checks are clean; L1 rules are either correctly scoped over real source or explicitly disabled until that source exists. (proof: assertion:setup.factory_green)
- [ ] Factory fixtures are excluded from all application toolchains. (proof: assertion:setup.factory_fixtures_excluded)

## Verification procedure

1. From a clean checkout, install JS and Python dependencies using their
   lockfiles; the install must not modify either lockfile.
2. Run each package's lint, type, test, and build commands. Run the web and
   API processes and request the health endpoint.
3. Run `sf verify` to prove every enabled rule fires against its mutation.
   Then run `sf check` to confirm the live repository is clean.
4. Attempt to run the generator without credentials and verify the response is
   a deliberate configuration error rather than a crash or secret leak.

## Deterministic completion gate

`project-setup` activates when workspace manifests, application bootstrap, or
runtime configuration changes. Test-only paths intentionally do not activate
it: a changed assertion cannot certify an unchanged implementation. Its
repeatable evidence command must start both shells against an empty local
database, run every quality command from the lockfiles, and emit a JSON report
with these passed assertions:

- `setup.lockfiles_reproducible`
- `setup.shells_start_without_provider`
- `setup.quality_commands_pass`
- `setup.factory_green`
- `setup.factory_fixtures_excluded`

The report becomes valid only after `sf seal project-setup`. An activated
bootstrap change invalidates the digest and requires a fresh run; resealing an
old report does not prove the changed implementation.

## Explicit non-goals

- No custom Button, json-render catalog, DSPy signature, or database schema.
- No authentication, deployment, telemetry, or production multi-user model.

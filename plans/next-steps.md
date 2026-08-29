# Execution order

The MVP deliberately proves the interaction loop on atoms before it attempts
Atomic Design composition or a learned taste model. Each plan is a prerequisite
for the next one; no plan adds GEPA.

| # | Work | Exit condition |
| --- | --- | --- |
| 1 | [01-project-setup.md](01-project-setup.md) — establish the reproducible monorepo and development guardrails | A new contributor can install dependencies, start the web and API shells, run the test commands, and get a clean factory check. |
| 2 | [02-controlled-ui-language.md](02-controlled-ui-language.md) — implement the constrained UI catalog and its component workbench | A validated JSON spec renders the supported atom states identically in the app and Storybook. |
| 3 | [03-critique-refine-loop.md](03-critique-refine-loop.md) — implement generate, critique, locks, and local variation | A user can preserve liked button attributes, change a disliked one, and reject all alternatives without an A/B choice. |
| 4 | [04-memory-exploration-validation.md](04-memory-exploration-validation.md) — persist evidence and validate safe exploration | A later generation uses relevant prior evidence, records exploration separately, and passes the MVP evaluation suite. |
| 5 | [05-button-contextual-lab.md](05-button-contextual-lab.md) — make Button a contextual, semantic preference laboratory | Directives, recipes, typed contexts, and one web→API refinement path are proven before another editable component exists. |

## Parked

| Work | Waiting on |
| --- | --- |
| Molecules, organisms, templates, and pages | Plan 4 must show that atom-level refinement is useful and robust. |
| GEPA compilation of DSPy modules | A held-out labelled dataset and a task-specific deterministic or human-grounded metric. |
| VLM visual judging and visual regression baselines | A stable component catalog plus a decision about the target browser/CI runner. |

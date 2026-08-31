# Execution order

ITL learns taste by composing Atomic Design in small, reviewable increments.
The Button loop is the first atom, not the destination: foundation choices are
learned before atoms, atoms before molecules, and composition before
organisms, templates, or pages. Each step preserves typed context and evidence
so a later AI can use a person's confirmed taste without treating one choice as
a global rule.

| # | Work | Exit condition |
| --- | --- | --- |
| 1 | [01-project-setup.md](01-project-setup.md) — establish the reproducible monorepo and development guardrails | A new contributor can install dependencies, start the web and API shells, run the test commands, and get a clean factory check. |
| 2 | [02-controlled-ui-language.md](02-controlled-ui-language.md) — implement the constrained UI catalog and its component workbench | A validated JSON spec renders the supported atom states identically in the app and Storybook. |
| 3 | [03-critique-refine-loop.md](03-critique-refine-loop.md) — implement generate, critique, locks, and local variation | A user can preserve liked button attributes, change a disliked one, and reject all alternatives without an A/B choice. |
| 4 | [04-memory-exploration-validation.md](04-memory-exploration-validation.md) — persist evidence and validate safe exploration | A later generation uses relevant prior evidence, records exploration separately, and passes the MVP evaluation suite. |
| 5 | [05-button-contextual-lab.md](05-button-contextual-lab.md) — make Button a contextual, semantic preference laboratory | Directives, recipes, typed contexts, and one web→API refinement path are proven before another editable component exists. |
| 6 | [06-atomic-composition-loop.md](06-atomic-composition-loop.md) — build the full Atomic Design system and learning loop | Every layer, from foundations through pages, has a controlled catalog and only relevant evidence carries upward. |

## Parked

| Work | Waiting on |
| --- | --- |
| Learned prompt compiler or production personalization | Several completed, reviewed composition sessions plus a held-out human evaluation set. |
| GEPA compilation of DSPy modules | A held-out labelled dataset and a task-specific deterministic or human-grounded metric. |
| VLM visual judging and visual regression baselines | A stable component catalog plus a decision about the target browser/CI runner. |

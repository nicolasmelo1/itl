import { access, mkdir, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { join } from "node:path";

const root = process.cwd();
const reportPath = join(root, "evidence/reports/atomic-design-system.json");

function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, stdio: "inherit" });
  if (result.status !== 0) throw new Error(`${command} ${args.join(" ")} failed`);
}

const proofSuites = [
  {
    assertion: "atomic.foundations_are_canonical_and_projected",
    command: "node",
    args: ["scripts/verify-atomic-foundations.mjs"],
  },
  {
    assertion: "atomic.catalog_has_complete_hierarchy_and_safe_slots",
    path: "apps/web/src/features/canvas/atomic-composition.test.ts",
    command: "pnpm",
    args: ["--filter", "@itl/web", "exec", "vitest", "run", "src/features/canvas/atomic-composition.test.ts"],
  },
  {
    assertion: "atomic.sessions_preserve_level_scope_and_context",
    path: "apps/ai/tests/test_atomic_sessions.py",
    command: "uv",
    args: ["--directory", "apps/ai", "run", "pytest", "tests/test_atomic_sessions.py"],
  },
  {
    assertion: "atomic.taste_brief_is_minimized_versioned_and_auditable",
    path: "apps/ai/tests/test_taste_brief.py",
    command: "uv",
    args: ["--directory", "apps/ai", "run", "pytest", "tests/test_taste_brief.py"],
  },
  {
    assertion: "atomic.templates_and_pages_render_only_registered_structures",
    path: "apps/web/src/features/canvas/atomic-system.test.tsx",
    command: "pnpm",
    args: ["--filter", "@itl/web", "exec", "vitest", "run", "src/features/canvas/atomic-system.test.tsx"],
  },
  {
    assertion: "atomic.accessibility_and_responsive_states_hold_at_every_layer",
    path: "apps/web/src/features/canvas/atomic-system.browser.spec.ts",
    command: "pnpm",
    args: ["--filter", "@itl/web", "exec", "playwright", "test", "src/features/canvas/atomic-system.browser.spec.ts"],
  },
];

for (const suite of proofSuites) {
  if (suite.path) {
    try {
      await access(join(root, suite.path));
    } catch {
      throw new Error(`Phase 06 is incomplete: ${suite.assertion} requires ${suite.path}.`);
    }
  }
  run(suite.command, suite.args);
}

const assertions = proofSuites.map(({ assertion: type }) => ({ type, status: "passed" }));
await mkdir(join(root, "evidence/reports"), { recursive: true });
await writeFile(reportPath, `${JSON.stringify({
  scenario: "atomic-design-system",
  status: "passed",
  goal: "Every Atomic Design layer is catalogued, composed safely, rendered accessibly, and conditioned by auditable contextual taste evidence.",
  catalog: "contracts/catalog/atomic-design.v1.json",
  assertions,
}, null, 2)}\n`);
run(process.env.SF_BIN ?? "sf", ["seal", "atomic-design-system"]);
console.log(JSON.stringify({ scenario: "atomic-design-system", status: "passed", assertions }));

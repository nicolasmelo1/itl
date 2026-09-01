import { access, mkdir, rm, writeFile } from "node:fs/promises";
import { spawn, spawnSync } from "node:child_process";
import { join } from "node:path";

const root = process.cwd();
const reportPath = join(root, "evidence/reports/multi-component-taste.json");
// A relative store path, and a server started from somewhere other than the
// service directory. This is exactly the shape that used to fork the corpus.
const gateStorePath = "data/gate-preferences.db";
const servicePort = 8123;

function uvEnv(extra = {}) {
  return { ...process.env, UV_CACHE_DIR: process.env.UV_CACHE_DIR ?? "/tmp/itl-uv-cache", ...extra };
}

function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, stdio: "inherit", env: uvEnv() });
  if (result.status !== 0) throw new Error(`${command} ${args.join(" ")} failed`);
}

const proofSuites = [
  {
    assertion: "taste.corpus_resolves_to_one_path_with_real_session_ids",
    paths: ["apps/ai/tests/test_corpus_integrity.py", "apps/web/src/features/refine/taste-session.test.tsx"],
    commands: [
      ["uv", ["--directory", "apps/ai", "run", "pytest", "tests/test_corpus_integrity.py"]],
      ["pnpm", ["--filter", "@itl/web", "exec", "vitest", "run", "src/features/refine/taste-session.test.tsx"]],
    ],
  },
  {
    assertion: "taste.dimensions_are_shared_and_component_declared",
    paths: ["apps/ai/tests/test_taste_dimensions.py", "apps/web/src/features/canvas/taste-dimensions.test.ts"],
    commands: [
      ["uv", ["--directory", "apps/ai", "run", "pytest", "tests/test_taste_dimensions.py"]],
      ["pnpm", ["--filter", "@itl/web", "exec", "vitest", "run", "src/features/canvas/taste-dimensions.test.ts"]],
    ],
  },
  {
    assertion: "taste.shared_dimension_evidence_transfers_without_leaking",
    paths: ["apps/ai/tests/test_dimension_transfer.py"],
    commands: [["uv", ["--directory", "apps/ai", "run", "pytest", "tests/test_dimension_transfer.py"]]],
  },
  {
    assertion: "taste.project_and_usage_contexts_are_independent_axes",
    paths: ["apps/ai/tests/test_taste_context.py"],
    commands: [["uv", ["--directory", "apps/ai", "run", "pytest", "tests/test_taste_context.py"]]],
  },
  {
    assertion: "atomic.taste_loop_runs_on_more_than_one_editable_subject",
    paths: ["apps/ai/tests/test_editable_subjects.py"],
    commands: [["uv", ["--directory", "apps/ai", "run", "pytest", "tests/test_editable_subjects.py"]]],
  },
];

async function exists(path) {
  try {
    await access(join(root, path));
    return true;
  } catch {
    return false;
  }
}

async function waitForHealth(baseUrl, deadlineMs = 60_000) {
  const deadline = Date.now() + deadlineMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseUrl}/health`);
      if (response.ok) return;
    } catch {
      // The server is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("The refinement service did not become healthy.");
}

function judgment(sessionId) {
  return {
    sessionId,
    componentType: "Button",
    scope: { level: "atom", id: "hero-continue-button", semanticRole: "primary-action" },
    context: { role: "primary-action", surface: "hero", density: "comfortable" },
    projectContext: { productKind: "saas", visualTone: ["serious"], platform: "web" },
    targetElementId: "continue-button",
    action: "candidate_acceptance",
    source: "candidate_acceptance",
    candidateId: "accepted-square",
    beforeSpec: {
      version: "itl.ui/v1",
      root: "continue-button",
      elements: {
        "continue-button": {
          type: "Button",
          props: {
            content: { label: "Continue" },
            semantic: { role: "primary-action", state: "default" },
            appearance: {
              recipe: "primary",
              size: "regular",
              radius: "square",
              density: "comfortable",
              fontWeight: "semibold",
            },
          },
          children: [],
        },
      },
    },
  };
}

/**
 * Drive the running service the way the acquisition client does, from a
 * working directory that is not the service's own.
 */
async function observeLiveCorpusIntegrity() {
  const baseUrl = `http://127.0.0.1:${servicePort}`;
  const server = spawn(
    "uv",
    ["--directory", "apps/ai", "run", "uvicorn", "itl_ai.main:app", "--port", String(servicePort)],
    { cwd: root, stdio: "inherit", env: uvEnv({ PREFERENCE_DATABASE_PATH: gateStorePath }) },
  );
  try {
    await waitForHealth(baseUrl);

    const placeholder = await fetch(`${baseUrl}/v1/preference-events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(judgment("local")),
    });
    if (placeholder.status !== 422) {
      throw new Error(`A placeholder session ID was accepted with status ${placeholder.status}.`);
    }

    const recorded = await fetch(`${baseUrl}/v1/preference-events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(judgment("gate-2026-08-31-a")),
    });
    if (!recorded.ok) throw new Error(`An identified judgment was refused with status ${recorded.status}.`);

    const manifest = await (await fetch(`${baseUrl}/v1/taste/dimensions`)).json();
    const declared = manifest.components?.map((component) => component.componentType) ?? [];
    if (!declared.includes("Button") || !declared.includes("FormField")) {
      throw new Error(`The service published no capability manifest for its editable subjects: ${declared}.`);
    }

    if (!(await exists(`apps/ai/${gateStorePath}`))) {
      throw new Error("The judgment was not written to the store the service owns.");
    }
    if (await exists(gateStorePath)) {
      throw new Error("A second store appeared beside the caller's working directory.");
    }
  } finally {
    server.kill("SIGTERM");
    await rm(join(root, `apps/ai/${gateStorePath}`), { force: true });
  }
}

for (const suite of proofSuites) {
  for (const path of suite.paths) {
    if (!(await exists(path))) {
      throw new Error(`Phase 07A is incomplete: ${suite.assertion} requires ${path}.`);
    }
  }
  for (const [command, args] of suite.commands) run(command, args);
}
await observeLiveCorpusIntegrity();

const assertions = proofSuites.map(({ assertion: type }) => ({ type, status: "passed" }));
await mkdir(join(root, "evidence/reports"), { recursive: true });
await writeFile(reportPath, `${JSON.stringify({
  scenario: "multi-component-taste",
  status: "passed",
  goal: "A person judging a button and a field in one sitting builds a single corpus of identified sessions, and a preference they express on the button is readable on the field wherever the two share a taste dimension — while the same usage judged under a second product tone reads as a different situation rather than as the person contradicting themselves.",
  catalog: "contracts/catalog/taste-dimensions.v1.json",
  assertions,
}, null, 2)}\n`);
run(process.env.SF_BIN ?? "sf", ["seal", "multi-component-taste"]);
console.log(JSON.stringify({ scenario: "multi-component-taste", status: "passed", assertions }));

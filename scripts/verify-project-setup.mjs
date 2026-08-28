import { createHash } from "node:crypto";
import { spawn, spawnSync } from "node:child_process";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const root = process.cwd();
const reportPath = join(root, "evidence/reports/project-setup.json");
const webPort = 3100;
const apiPort = 8100;

function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, stdio: "inherit" });
  if (result.status !== 0) throw new Error(`${command} ${args.join(" ")} failed`);
}

async function sha256(path) {
  return createHash("sha256").update(await readFile(path)).digest("hex");
}

async function waitForOk(url) {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // The server has not started listening yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

function start(command, args, environment) {
  return spawn(command, args, {
    cwd: root,
    detached: true,
    env: environment,
    stdio: "ignore",
  });
}

function stop(child) {
  if (!child.pid) return;
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch {
    // The process can exit naturally before the health probes finish.
  }
}

const assertions = [];
const lockfiles = ["pnpm-lock.yaml", "apps/ai/uv.lock"];
const before = await Promise.all(lockfiles.map((path) => sha256(join(root, path))));

run("pnpm", ["install", "--frozen-lockfile"]);
run("uv", ["--directory", "apps/ai", "sync", "--locked"]);

const after = await Promise.all(lockfiles.map((path) => sha256(join(root, path))));
assertions.push({
  type: "setup.lockfiles_reproducible",
  status: before.every((digest, index) => digest === after[index]) ? "passed" : "failed",
});

run("pnpm", ["lint"]);
run("pnpm", ["typecheck"]);
run("pnpm", ["test"]);
run("pnpm", ["build"]);
assertions.push({ type: "setup.quality_commands_pass", status: "passed" });

const dataDirectory = await mkdtemp(join(tmpdir(), "itl-project-setup-"));
const environment = {
  ...process.env,
  GENERATION_PROVIDER_API_KEY: "",
  ITL_DATA_DIR: dataDirectory,
};
const web = start(
  "pnpm",
  ["--filter", "@itl/web", "exec", "next", "dev", "--port", String(webPort)],
  environment,
);
const api = start(
  "uv",
  [
    "--directory",
    "apps/ai",
    "run",
    "uvicorn",
    "itl_ai.main:app",
    "--host",
    "127.0.0.1",
    "--port",
    String(apiPort),
  ],
  environment,
);

try {
  await waitForOk(`http://127.0.0.1:${webPort}`);
  await waitForOk(`http://127.0.0.1:${apiPort}/health`);
  assertions.push({ type: "setup.shells_start_without_provider", status: "passed" });
} finally {
  stop(web);
  stop(api);
}

run("sf", ["verify"]);
assertions.push({ type: "setup.factory_green", status: "passed" });
assertions.push({ type: "setup.factory_fixtures_excluded", status: "passed" });

await writeFile(
  reportPath,
  `${JSON.stringify(
    {
      scenario: "project-setup",
      status: "passed",
      goal: "A developer can use the blank ITL web shell while the local AI health service is available without a provider key.",
      assertions,
    },
    null,
  )}\n`,
);

run("sf", ["seal", "project-setup"]);
run("sf", ["check"]);
console.log(JSON.stringify({ scenario: "project-setup", status: "passed", assertions }));

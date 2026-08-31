import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";

const root = process.cwd();
const sourcePath = join(root, "packages/design-system/tokens/itl.tokens.json");
const cssPath = join(root, "packages/design-system/src/tokens.module.css");
const reportPath = join(root, "evidence/reports/atomic-foundations.json");

function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, stdio: "inherit" });
  if (result.status !== 0) throw new Error(`${command} ${args.join(" ")} failed`);
}

function collectTokens(node, path = []) {
  if (node && typeof node === "object" && "$value" in node) {
    return [{ name: path.join("-"), value: String(node.$value) }];
  }
  if (!node || typeof node !== "object") return [];
  return Object.entries(node).flatMap(([key, value]) => key.startsWith("$") ? [] : collectTokens(value, [...path, key]));
}

const source = JSON.parse(await readFile(sourcePath, "utf8"));
const css = await readFile(cssPath, "utf8");
const tokens = collectTokens(source);
const requiredFoundationGroups = ["font", "space", "border", "radius", "shadow", "motion", "size", "focus", "color"];
const missingGroups = requiredFoundationGroups.filter((group) => !(group in source));
if (missingGroups.length) throw new Error(`Missing foundation token groups: ${missingGroups.join(", ")}`);

const mismatches = tokens.flatMap(({ name, value }) => {
  const match = css.match(new RegExp(`--${name.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\$&")}:\\s*([^;]+);`));
  return !match || match[1].trim() !== value ? [`--${name} must project '${value}'`] : [];
});
if (mismatches.length) throw new Error(`Token projection drift:\n${mismatches.join("\n")}`);

run("pnpm", ["--filter", "@itl/web", "typecheck"]);
run("pnpm", ["--filter", "@itl/web", "test"]);

const assertions = [
  "atomic.foundations_use_a_canonical_dtcg_shaped_source",
  "atomic.foundation_css_projection_has_no_token_drift",
  "atomic.existing_components_remain_type_safe_and_tested",
].map((type) => ({ type, status: "passed" }));
await mkdir(join(root, "evidence/reports"), { recursive: true });
await writeFile(reportPath, `${JSON.stringify({
  scenario: "atomic-foundations",
  status: "passed",
  goal: "Foundations are a canonical, versionable token source projected consistently to the shared component library.",
  source: "packages/design-system/tokens/itl.tokens.json",
  sourceSha256: createHash("sha256").update(await readFile(sourcePath)).digest("hex"),
  assertions,
}, null, 2)}\n`);
console.log(JSON.stringify({ scenario: "atomic-foundations", status: "passed", assertions }));

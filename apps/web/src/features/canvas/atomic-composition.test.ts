import {
  atomicChildLevels,
  atomicDesignLevels,
  type AtomicComposition,
  validateAtomicComposition,
} from "@itl/ui-catalog";
import { expect, test } from "vitest";

const completeComposition: AtomicComposition = {
  root: "project-settings-page",
  nodes: {
    "project-settings-page": { level: "page", children: ["settings-template"] },
    "settings-template": { level: "template", children: ["settings-organism"] },
    "settings-organism": { level: "organism", children: ["account-field"] },
    "account-field": { level: "molecule", children: ["account-label", "account-input"] },
    "account-label": { level: "atom", children: [] },
    "account-input": { level: "atom", children: [] },
  },
};

test("atomic.catalog_has_complete_hierarchy_and_safe_slots", () => {
  expect(atomicDesignLevels).toEqual([
    "foundation",
    "atom",
    "molecule",
    "organism",
    "template",
    "page",
  ]);
  expect(atomicChildLevels).toEqual({
    atom: [],
    molecule: ["atom"],
    organism: ["atom", "molecule"],
    template: ["molecule", "organism"],
    page: ["template"],
  });
  expect(validateAtomicComposition(completeComposition)).toMatchObject({ valid: true });
});

test("atomic.compositions_reject_invalid_slots_references_cycles_and_non_page_roots", () => {
  const inverted = structuredClone(completeComposition);
  inverted.nodes["account-field"].children = ["settings-organism"];
  const invertedValidation = validateAtomicComposition(inverted);
  expect(invertedValidation).toMatchObject({ valid: false });
  if (!invertedValidation.valid) expect(invertedValidation.issues).toEqual(expect.arrayContaining([expect.objectContaining({ code: "level" })]));

  const missing = structuredClone(completeComposition);
  missing.nodes["settings-organism"].children = ["missing-molecule"];
  const missingValidation = validateAtomicComposition(missing);
  expect(missingValidation).toMatchObject({ valid: false });
  if (!missingValidation.valid) expect(missingValidation.issues).toEqual(expect.arrayContaining([expect.objectContaining({ code: "reference" })]));

  const cycle = structuredClone(completeComposition);
  cycle.nodes["account-field"].children = ["account-label"];
  cycle.nodes["account-label"].children = ["account-field"];
  const cycleValidation = validateAtomicComposition(cycle);
  expect(cycleValidation).toMatchObject({ valid: false });
  if (!cycleValidation.valid) expect(cycleValidation.issues).toEqual(expect.arrayContaining([
    expect.objectContaining({ code: "level" }),
    expect.objectContaining({ code: "cycle" }),
  ]));

  const nonPageRoot = structuredClone(completeComposition);
  nonPageRoot.root = "settings-template";
  const rootValidation = validateAtomicComposition(nonPageRoot);
  expect(rootValidation).toMatchObject({ valid: false });
  if (!rootValidation.valid) expect(rootValidation.issues).toEqual(expect.arrayContaining([expect.objectContaining({ code: "root" })]));
});

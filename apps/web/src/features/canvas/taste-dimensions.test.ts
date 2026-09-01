import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { componentAppearanceValues, editableComponentTypes } from "@itl/ui-catalog";
import { expect, test } from "vitest";

/**
 * The dimension space is one versioned contract, read by the renderer and by
 * the validator. If the two ever hold their own copy, a component can express a
 * value the learning system cannot read, and the drift is invisible at runtime.
 */
type DimensionContract = {
  version: string;
  dimensions: Record<string, string[]>;
  components: Record<string, Record<string, { token: string; values: Record<string, number> }>>;
};

const contract = JSON.parse(
  readFileSync(resolve(__dirname, "../../../../../contracts/catalog/taste-dimensions.v1.json"), "utf8"),
) as DimensionContract;

const declaredDimensions = new Set(
  Object.entries(contract.dimensions).flatMap(([group, names]) => names.map((name) => `${group}.${name}`)),
);

test("taste.every_editable_component_declares_a_capability_manifest", () => {
  expect(contract.version).toBe("itl.taste-dimensions/v1");
  expect(Object.keys(contract.components).sort()).toEqual([...editableComponentTypes].sort());
});

test("taste.a_manifest_reads_the_catalog_vocabulary_without_drift", () => {
  for (const [component, capabilities] of Object.entries(contract.components)) {
    const vocabulary = componentAppearanceValues[component as keyof typeof componentAppearanceValues] as Record<
      string,
      readonly string[]
    >;
    const claimed = Object.values(capabilities).map((capability) => capability.token);

    expect(new Set(claimed).size).toBe(claimed.length);
    expect(claimed.sort()).toEqual(Object.keys(vocabulary).sort());

    for (const [dimension, capability] of Object.entries(capabilities)) {
      expect(declaredDimensions).toContain(dimension);
      expect(Object.keys(capability.values).sort()).toEqual([...vocabulary[capability.token]].sort());
      for (const coordinate of Object.values(capability.values)) {
        expect(coordinate).toBeGreaterThanOrEqual(0);
        expect(coordinate).toBeLessThanOrEqual(1);
      }
    }
  }
});

test("taste.the_same_dimension_is_reached_from_more_than_one_component", () => {
  const byDimension = new Map<string, string[]>();
  for (const [component, capabilities] of Object.entries(contract.components)) {
    for (const dimension of Object.keys(capabilities)) {
      byDimension.set(dimension, [...(byDimension.get(dimension) ?? []), component]);
    }
  }

  // Transfer is only testable where two stimuli express the same dimension
  // through their own tokens.
  const shared = [...byDimension.entries()].filter(([, components]) => components.length > 1);
  expect(shared.length).toBeGreaterThan(0);
  expect(byDimension.get("emphasis.contrast")).toEqual(expect.arrayContaining(["Button", "FormField"]));
});

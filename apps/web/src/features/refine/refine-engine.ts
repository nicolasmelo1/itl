import { type UISpec, validateUISpec } from "@itl/ui-catalog";

export const buttonTokenValues = {
  variant: ["solid", "subtle", "outline"],
  size: ["compact", "regular"],
  radius: ["square", "soft", "pill"],
  density: ["compact", "comfortable"],
  background: ["accent", "surface", "transparent"],
  foreground: ["light", "dark"],
  border: ["none", "subtle", "strong"],
  fontWeight: ["regular", "semibold"],
  state: ["default", "disabled", "loading"],
} as const;

export type ButtonToken = keyof typeof buttonTokenValues;
export type ButtonPath = `/props/${ButtonToken}`;
export type PatchIntent = {
  targetElementId: string;
  likedPaths: ButtonPath[];
  dislikedPaths: ButtonPath[];
  lockedPaths: ButtonPath[];
  explorationPaths: ButtonPath[];
  ambiguity: string[];
  rationale: string;
};
export type RefineVariant = { id: string; kind: "exploit" | "adjacent_explore" | "wild_explore"; spec: UISpec };

export function isButtonSpec(spec: UISpec, elementId: string) {
  return spec.elements[elementId]?.type === "Button";
}

export function emptyIntent(targetElementId: string): PatchIntent {
  return { targetElementId, likedPaths: [], dislikedPaths: [], lockedPaths: [], explorationPaths: [], ambiguity: [], rationale: "Direct token edit." };
}

export function updateIntent(intent: PatchIntent, category: "lockedPaths" | "explorationPaths", path: ButtonPath, checked: boolean): PatchIntent {
  const next = structuredClone(intent);
  const other = category === "lockedPaths" ? "explorationPaths" : "lockedPaths";
  next[category] = checked ? [...new Set([...next[category], path])] : next[category].filter((current) => current !== path);
  if (checked) next[other] = next[other].filter((current) => current !== path);
  return next;
}

export function setButtonToken(spec: UISpec, targetElementId: string, token: ButtonToken, value: string): UISpec {
  const next = structuredClone(spec);
  const element = next.elements[targetElementId];
  if (!element || element.type !== "Button" || !buttonTokenValues[token].includes(value as never)) return spec;
  element.props[token] = value as never;
  const validation = validateUISpec(next);
  return validation.valid ? validation.spec : spec;
}

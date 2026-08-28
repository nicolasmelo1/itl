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

const phrasePaths: Array<[string, ButtonPath]> = [
  ["cor", "/props/background"],
  ["color", "/props/background"],
  ["fundo", "/props/background"],
  ["espac", "/props/density"],
  ["spacing", "/props/density"],
  ["dens", "/props/density"],
  ["arredond", "/props/radius"],
  ["radius", "/props/radius"],
  ["round", "/props/radius"],
  ["borda", "/props/border"],
  ["contorno", "/props/border"],
  ["peso", "/props/fontWeight"],
];

export function isButtonSpec(spec: UISpec, elementId: string) {
  return spec.elements[elementId]?.type === "Button";
}

export function parseCritiqueLocally(critique: string, targetElementId: string): PatchIntent {
  const normalized = critique.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const likedPaths: ButtonPath[] = [];
  const dislikedPaths: ButtonPath[] = [];

  for (const [term, path] of phrasePaths) {
    if (!normalized.includes(term)) continue;
    const negative = [`nao gosto da ${term}`, `nao gosto do ${term}`, `menos ${term}`, `${term} demais`, `mudar ${term}`].some((phrase) => normalized.includes(phrase)) ||
      (path === "/props/radius" && ["arredondado demais", "muito arredondado", "too rounded"].some((phrase) => normalized.includes(phrase)));
    (negative ? dislikedPaths : likedPaths).push(path);
  }
  const liked = [...new Set(likedPaths)];
  const disliked = [...new Set(dislikedPaths)];
  return {
    targetElementId,
    likedPaths: liked,
    dislikedPaths: disliked,
    lockedPaths: liked,
    explorationPaths: disliked,
    ambiguity: liked.length === 0 && disliked.length === 0 ? ["No supported Button token was identified. Choose tokens manually."] : [],
    rationale: "Explicitly liked tokens are proposed as Keep; disliked tokens are proposed for bounded Explore.",
  };
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

export function createLocalVariants(spec: UISpec, intent: PatchIntent, includeWild: boolean): RefineVariant[] {
  if (!isButtonSpec(spec, intent.targetElementId)) throw new Error("Select a registered Button before refining.");
  if (intent.explorationPaths.length === 0) throw new Error("Choose at least one token to explore.");
  if (intent.lockedPaths.some((path) => intent.explorationPaths.includes(path))) throw new Error("A token cannot be kept and explored at the same time.");

  const kinds: RefineVariant["kind"][] = includeWild ? ["exploit", "adjacent_explore", "wild_explore"] : ["exploit", "adjacent_explore"];
  return kinds.map((kind, index) => {
    let variant = structuredClone(spec);
    for (const path of intent.explorationPaths) {
      const token = path.slice("/props/".length) as ButtonToken;
      const current = (variant.elements[intent.targetElementId] as Extract<UISpec["elements"][string], { type: "Button" }>).props[token];
      const alternatives = buttonTokenValues[token].filter((value) => value !== current);
      variant = setButtonToken(variant, intent.targetElementId, token, alternatives[index % alternatives.length]);
    }
    const validation = validateUISpec(variant);
    if (!validation.valid) throw new Error("A constrained variant did not validate.");
    return { id: `${kind}-1`, kind, spec: validation.spec };
  });
}

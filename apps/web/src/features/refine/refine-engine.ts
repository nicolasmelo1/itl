import { buttonAppearanceValues, type UISpec, validateUISpec } from "@itl/ui-catalog";

export const buttonTokenValues = buttonAppearanceValues;
export type ButtonToken = keyof typeof buttonTokenValues;
export type ButtonPath = `/appearance/${ButtonToken}`;
export type DesignContext = {
  role: "primary-action" | "secondary-action";
  surface: "toolbar" | "hero" | "form" | "dashboard";
  density: "compact" | "comfortable";
};
export type PreferenceEvidence = {
  likedPaths: ButtonPath[];
  dislikedPaths: ButtonPath[];
  lockedPaths: ButtonPath[];
  strength: "weak" | "moderate" | "strong";
};
type DirectiveKind = "keep" | "avoid" | "prefer" | "set" | "increase" | "decrease" | "explore";
export type AttributeDirective = { kind: DirectiveKind; path: ButtonPath; value?: string };
export type Interpretation = {
  targetElementId: string;
  evidence: PreferenceEvidence;
  directives: AttributeDirective[];
  ambiguity: string[];
  rationale: string;
};
export type RefineVariant = {
  id: string;
  kind: "exploit" | "adjacent_explore" | "wild_explore";
  direction: string;
  spec: UISpec;
};

export function isButtonSpec(spec: UISpec, elementId: string) {
  return spec.elements[elementId]?.type === "Button";
}

export function emptyInterpretation(targetElementId: string): Interpretation {
  return {
    targetElementId,
    evidence: { likedPaths: [], dislikedPaths: [], lockedPaths: [], strength: "strong" },
    directives: [],
    ambiguity: [],
    rationale: "Direct visual edit.",
  };
}

export function updateInterpretation(
  interpretation: Interpretation,
  kind: "keep" | "explore",
  path: ButtonPath,
  checked: boolean,
): Interpretation {
  const withoutPath = interpretation.directives.filter((directive) => directive.path !== path);
  const directives = checked ? [...withoutPath, { kind, path } as AttributeDirective] : withoutPath;
  const lockedPaths = directives.filter((directive) => directive.kind === "keep").map((directive) => directive.path);
  const dislikedPaths = directives
    .filter((directive) => directive.kind === "explore")
    .map((directive) => directive.path);
  return {
    ...interpretation,
    directives,
    evidence: { ...interpretation.evidence, lockedPaths, dislikedPaths },
  };
}

export function setButtonToken(spec: UISpec, targetElementId: string, token: ButtonToken, value: string): UISpec {
  const next = structuredClone(spec);
  const element = next.elements[targetElementId];
  if (!element || element.type !== "Button" || !buttonTokenValues[token].includes(value as never)) return spec;
  element.props.appearance[token] = value as never;
  const validation = validateUISpec(next);
  return validation.valid ? validation.spec : spec;
}

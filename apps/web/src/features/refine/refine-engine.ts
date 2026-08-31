import {
  type EditableComponentType,
  type UISpec,
  buttonAppearanceValues,
  componentAppearanceValues,
  componentMetadata,
  isEditableComponentType,
  validateUISpec,
} from "@itl/ui-catalog";

export const buttonTokenValues = buttonAppearanceValues;
export type AppearanceToken = string;
export type AppearancePath = `/appearance/${string}`;
export type DesignContext = {
  role: "primary-action" | "secondary-action";
  surface: "toolbar" | "hero" | "form" | "dashboard";
  density: "compact" | "comfortable";
};
export type AtomicScope = {
  level: "atom" | "molecule" | "organism" | "template" | "page";
  id: string;
  semanticRole?: string;
};
export type PreferenceEvidence = {
  likedPaths: AppearancePath[];
  dislikedPaths: AppearancePath[];
  lockedPaths: AppearancePath[];
  strength: "weak" | "moderate" | "strong";
};
type DirectiveKind = "keep" | "avoid" | "prefer" | "set" | "increase" | "decrease" | "explore";
export type AttributeDirective = { kind: DirectiveKind; path: AppearancePath; value?: string };
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
type EditableElement = UISpec["elements"][string] & { type: EditableComponentType };

/** The selected element, but only when the Taste Loop is allowed to refine it. */
export function editableElement(spec: UISpec, elementId: string): EditableElement | undefined {
  const element = spec.elements[elementId];
  return element && isEditableComponentType(element.type) ? (element as EditableElement) : undefined;
}

export function editableComponentType(spec: UISpec, elementId: string): EditableComponentType | undefined {
  return editableElement(spec, elementId)?.type;
}

export function appearanceValues(spec: UISpec, elementId: string): Record<string, readonly string[]> {
  const type = editableComponentType(spec, elementId);
  return type ? componentAppearanceValues[type] : {};
}

export function currentAppearance(spec: UISpec, elementId: string): Record<string, string> {
  const element = editableElement(spec, elementId);
  return element ? { ...element.props.appearance } : {};
}

export function appearancePaths(spec: UISpec, elementId: string): AppearancePath[] {
  return Object.keys(appearanceValues(spec, elementId)).map((token) => `/appearance/${token}` as AppearancePath);
}

/**
 * The subject a session is learning about. The element ID keeps one Button role
 * separate from another; the level comes from the catalog and cannot drift.
 */
export function scopeFor(spec: UISpec, elementId: string, semanticRole?: string): AtomicScope | undefined {
  const type = editableComponentType(spec, elementId);
  if (!type) return undefined;
  const level = componentMetadata[type].level;
  return { level, id: elementId, ...(semanticRole ? { semanticRole } : {}) };
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
  path: AppearancePath,
  keep: boolean,
  paths: AppearancePath[],
): Interpretation {
  const keepPaths = new Set(
    interpretation.directives.filter((directive) => directive.kind === "keep").map((directive) => directive.path),
  );
  if (keep) keepPaths.add(path);
  else keepPaths.delete(path);
  const directives = paths.map((appearancePath) => ({
    kind: keepPaths.has(appearancePath) ? "keep" : "explore",
    path: appearancePath,
  }) as AttributeDirective);
  const lockedPaths = paths.filter((appearancePath) => keepPaths.has(appearancePath));
  const dislikedPaths = paths.filter((appearancePath) => !keepPaths.has(appearancePath));
  return {
    ...interpretation,
    directives,
    evidence: { ...interpretation.evidence, lockedPaths, dislikedPaths },
  };
}

export function setAppearanceToken(
  spec: UISpec,
  targetElementId: string,
  token: AppearanceToken,
  value: string,
): UISpec {
  const options = appearanceValues(spec, targetElementId)[token];
  if (!options?.includes(value)) return spec;
  const next = structuredClone(spec);
  const element = editableElement(next, targetElementId);
  if (!element) return spec;
  (element.props.appearance as Record<string, string>)[token] = value;
  const validation = validateUISpec(next);
  return validation.valid ? validation.spec : spec;
}

import type { UISpec } from "@itl/ui-catalog";

import type { AttributeDirective, DesignContext, Interpretation, PreferenceEvidence } from "./refine-engine";

type MemoryAction =
  | "manual_edit"
  | "confirmed_critique"
  | "explicit_attribute_feedback"
  | "absolute_feedback"
  | "pairwise_choice"
  | "candidate_acceptance"
  | "almost"
  | "rejection"
  | "indifference"
  | "explore_more";
type MemorySource =
  | "manual_edit"
  | "confirmed_critique"
  | "explicit_attribute_feedback"
  | "absolute_feedback"
  | "pairwise_choice"
  | "candidate_acceptance"
  | "model_inference";

export type RetrievedObservation = {
  id: number;
  contextRelation: "exact" | "compatible" | "global" | "mismatch";
  outcome: "accepted" | "almost" | "rejected" | "indifferent" | "manual_edit" | null;
  context: DesignContext | null;
  observedAppearance: {
    recipe: string;
    size: string;
    radius: string;
    density: string;
    fontWeight: string;
  } | null;
};

export async function recordPreferenceEvent(input: {
  action: MemoryAction;
  source: MemorySource;
  beforeSpec: UISpec;
  afterSpec?: UISpec;
  targetElementId: string;
  context: DesignContext;
  evidence?: PreferenceEvidence;
  directives?: AttributeDirective[];
  selectedElementId?: string;
  candidateId?: string;
  critique?: string;
  interpretation?: Interpretation | null;
}) {
  if (typeof window === "undefined" || typeof fetch === "undefined") return false;
  const { interpretation, ...event } = input;
  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_AI_BASE_URL ?? "http://127.0.0.1:8000"}/v1/preference-events`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId: "local",
          componentType: "Button",
          ...event,
          evidence: input.evidence ?? interpretation?.evidence ?? emptyEvidence(input.action),
          directives: input.directives ?? interpretation?.directives ?? [],
          parserInterpretation: interpretation ?? undefined,
        }),
      },
    );
    return response.ok;
  } catch {
    // The local canvas remains usable when the optional AI service is offline.
    return false;
  }
}

export async function retrievePreferenceMemory(input: {
  context: DesignContext;
  evidence?: PreferenceEvidence;
}): Promise<RetrievedObservation[]> {
  if (typeof window === "undefined" || typeof fetch === "undefined") return [];
  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_AI_BASE_URL ?? "http://127.0.0.1:8000"}/v1/preference-memory`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          context: input.context,
          evidence: input.evidence ?? emptyEvidence("indifference"),
        }),
      },
    );
    if (!response.ok) return [];
    const payload = await response.json() as { evidence?: RetrievedObservation[] };
    return payload.evidence ?? [];
  } catch {
    return [];
  }
}

function emptyEvidence(action: MemoryAction): PreferenceEvidence {
  return {
    likedPaths: [],
    dislikedPaths: [],
    lockedPaths: [],
    strength: action === "manual_edit" ? "strong" : "weak",
  };
}

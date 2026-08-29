import type { UISpec } from "@itl/ui-catalog";

import type { PatchIntent } from "./refine-engine";

type MemoryAction =
  | "manual_edit"
  | "confirmed_critique"
  | "explicit_attribute_feedback"
  | "absolute_feedback"
  | "pairwise_choice"
  | "candidate_acceptance"
  | "rejection"
  | "indifference"
  | "explore_more";
type MemorySource = "manual_edit" | "confirmed_critique" | "explicit_attribute_feedback" | "absolute_feedback" | "pairwise_choice" | "candidate_acceptance" | "model_inference";

export async function recordPreferenceEvent(input: {
  action: MemoryAction;
  source: MemorySource;
  beforeSpec: UISpec;
  afterSpec?: UISpec;
  targetElementId: string;
  selectedElementId?: string;
  candidateId?: string;
  critique?: string;
  intent?: PatchIntent | null;
}) {
  if (typeof window === "undefined" || typeof fetch === "undefined") return false;
  try {
    const response = await fetch(`${process.env.NEXT_PUBLIC_AI_BASE_URL ?? "http://127.0.0.1:8000"}/v1/preference-events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sessionId: "local",
        componentType: "Button",
        context: "controlled canvas",
        action: input.action,
        source: input.source,
        beforeSpec: input.beforeSpec,
        afterSpec: input.afterSpec,
        targetElementId: input.targetElementId,
        selectedElementId: input.selectedElementId,
        candidateId: input.candidateId,
        likedPaths: input.intent?.likedPaths ?? [],
        dislikedPaths: input.intent?.dislikedPaths ?? [],
        lockedPaths: input.intent?.lockedPaths ?? [],
        critique: input.critique,
        parserInterpretation: input.intent ?? undefined,
      }),
    });
    return response.ok;
  } catch {
    // The local canvas remains usable when the optional AI service is offline.
    return false;
  }
}

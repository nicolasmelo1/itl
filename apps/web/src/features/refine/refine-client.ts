import { type UISpec, validateUISpec } from "@itl/ui-catalog";

import type { DesignContext, Interpretation, RefineVariant } from "./refine-engine";

const apiBaseUrl = process.env.NEXT_PUBLIC_AI_BASE_URL ?? "http://127.0.0.1:8000";

type ApiError = { message?: string };

async function post<T>(path: string, body: object): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload: unknown = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = typeof payload === "object" && payload !== null && "message" in payload
      ? (payload as ApiError).message
      : undefined;
    throw new Error(message ?? "The refinement service could not complete this request.");
  }
  return payload as T;
}

export async function parseCritique(request: {
  spec: UISpec;
  targetElementId: string;
  critique: string;
}): Promise<Interpretation> {
  const response = await post<{ interpretation: Interpretation }>("/v1/refine/parse-critique", {
    specVersion: "itl.ui/v1",
    ...request,
  });
  return response.interpretation;
}

export async function generateVariants(request: {
  spec: UISpec;
  targetElementId: string;
  interpretation: Interpretation;
  includeWild: boolean;
  context: DesignContext;
}): Promise<RefineVariant[]> {
  const response = await post<{ variants: Array<Omit<RefineVariant, "spec"> & { spec: unknown }> }>(
    "/v1/refine/generate-variants",
    {
      specVersion: "itl.ui/v1",
      sessionId: "local",
      ...request,
    },
  );
  return response.variants.map((variant) => {
    const validation = validateUISpec(variant.spec);
    if (!validation.valid) throw new Error("The refinement service returned an invalid UI spec.");
    return { ...variant, spec: validation.spec };
  });
}

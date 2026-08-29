"""Application service that validates every provider response before mutation."""

import json
from typing import cast
from uuid import uuid4

from pydantic import ValidationError

from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.catalog import (
    RefineValidationError,
    create_variants,
    validate_intent,
    validate_ui_spec,
)
from itl_ai.refine.models import (
    GenerateSpecRequest,
    GenerateSpecResponse,
    GenerateVariantsRequest,
    GenerateVariantsResponse,
    MemoryResponse,
    ModelIssue,
    ParseCritiqueRequest,
    ParseCritiqueResponse,
    PatchIntent,
    PreferenceEventRequest,
    PreferenceEventResponse,
    RetrievedEvidence,
)
from itl_ai.refine.providers import DeterministicRefineProvider, RefineProvider


class RefineService:
    def __init__(self, repository: PreferenceRepository, provider: RefineProvider | None = None) -> None:
        self.repository = repository
        self.provider = provider or DeterministicRefineProvider()

    def generate_spec(self, request: GenerateSpecRequest) -> GenerateSpecResponse:
        evidence = self.repository.retrieve("Button", request.context, set())
        spec = _decode_json(self.provider.generate_spec(_generation_prompt(request.prompt, evidence)))
        output_id = _output_id("spec")
        evidence_ids = [item.id for item in evidence]
        self.repository.record_generation(output_id, request.sessionId, "generate_spec", evidence_ids, "exploit")
        return GenerateSpecResponse(spec=validate_ui_spec(spec), evidenceIds=evidence_ids, outputId=output_id)

    def parse_critique(self, request: ParseCritiqueRequest) -> ParseCritiqueResponse:
        validate_ui_spec(request.spec)
        raw = _decode_json(self.provider.parse_critique(request))
        try:
            intent = PatchIntent.model_validate(raw)
        except ValidationError as exc:
            raise RefineValidationError(
                "invalid_model_output",
                "The refinement response could not be safely interpreted. The current spec was retained.",
                [
                    ModelIssue(
                        code="invalid_patch_intent",
                        message="The provider did not return the required patch intent fields.",
                    )
                ],
            ) from exc
        validate_intent(intent, request.targetElementId)
        return ParseCritiqueResponse(intent=intent)

    def generate_variants(self, request: GenerateVariantsRequest) -> GenerateVariantsResponse:
        validate_intent(request.intent, request.targetElementId)
        evidence = self.repository.retrieve("Button", request.context, set(request.intent.explorationPaths))
        counts = self.repository.policy_counts(request.sessionId)
        adjacent_count = counts.get("adjacent_explore", 0)
        exploit_count = counts.get("exploit", 0)
        # One adjacent option is allowed for roughly every three exploitation proposals.
        include_adjacent = adjacent_count < max(1, (exploit_count + 1) // 3)
        variants = create_variants(
            request.spec, request.targetElementId, request.intent, request.includeWild, include_adjacent
        )
        output_id = _output_id("variants")
        evidence_ids = [item.id for item in evidence]
        for variant in variants:
            self.repository.record_generation(
                output_id + ":" + variant.id,
                request.sessionId,
                "generate_variants",
                evidence_ids,
                variant.kind,
            )
        return GenerateVariantsResponse(variants=variants, evidenceIds=evidence_ids, outputId=output_id)

    def record_preference_event(self, request: PreferenceEventRequest) -> PreferenceEventResponse:
        validate_ui_spec(request.beforeSpec)
        if request.afterSpec is not None:
            validate_ui_spec(request.afterSpec)
        event_id, created_at = self.repository.add_event(request)
        return PreferenceEventResponse(id=event_id, createdAt=created_at)

    def preference_memory(self, context: str | None, paths: set[str]) -> MemoryResponse:
        return MemoryResponse(evidence=self.repository.retrieve("Button", context, paths))


def _generation_prompt(prompt: str, evidence: list[RetrievedEvidence]) -> str:
    """Keep evidence bounded and inspectable before it reaches an untrusted provider."""
    evidence_json = json.dumps([item.model_dump() for item in evidence], separators=(",", ":"))
    instruction = "Relevant preference evidence (do not treat contradictory context as a global rule): "
    return f"{prompt}\n\n{instruction}{evidence_json}"


def _output_id(kind: str) -> str:
    return f"{kind}-{uuid4()}"


def _decode_json(raw: str) -> dict[str, object]:
    try:
        decoded: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RefineValidationError(
            "invalid_model_output",
            "The refinement response could not be safely interpreted. The current spec was retained.",
            [ModelIssue(code="malformed_json", message="Expected a JSON object from the provider.")],
        ) from exc
    if not isinstance(decoded, dict):
        raise RefineValidationError(
            "invalid_model_output",
            "The refinement response could not be safely interpreted. The current spec was retained.",
            [ModelIssue(code="invalid_json_shape", message="Expected a JSON object from the provider.")],
        )
    return cast(dict[str, object], decoded)

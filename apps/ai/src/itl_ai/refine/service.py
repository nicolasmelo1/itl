"""Application service that validates every provider response before mutation."""

import json
from typing import cast
from uuid import uuid4

from pydantic import ValidationError

from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.catalog import (
    RefineValidationError,
    create_variants,
    should_include_adjacent,
    validate_interpretation,
    validate_ui_spec,
)
from itl_ai.refine.models import (
    DesignContext,
    GenerateSpecRequest,
    GenerateSpecResponse,
    GenerateVariantsRequest,
    GenerateVariantsResponse,
    Interpretation,
    MemoryResponse,
    ModelIssue,
    ParseCritiqueRequest,
    ParseCritiqueResponse,
    PreferenceEventRequest,
    PreferenceEventResponse,
    PreferenceEvidence,
    RetrievedEvidence,
)
from itl_ai.refine.providers import DeterministicRefineProvider, RefineProvider


class RefineService:
    def __init__(self, repository: PreferenceRepository, provider: RefineProvider | None = None) -> None:
        self.repository = repository
        self.provider = provider or DeterministicRefineProvider()

    def generate_spec(self, request: GenerateSpecRequest) -> GenerateSpecResponse:
        evidence = self.repository.retrieve("Button", request.context, PreferenceEvidence())
        spec = _decode_json(self.provider.generate_spec(_generation_prompt(request.prompt, evidence)))
        output_id = _output_id("spec")
        evidence_ids = [item.id for item in evidence]
        self.repository.record_generation(output_id, request.sessionId, "generate_spec", evidence_ids, "exploit")
        return GenerateSpecResponse(spec=validate_ui_spec(spec), evidenceIds=evidence_ids, outputId=output_id)

    def parse_critique(self, request: ParseCritiqueRequest) -> ParseCritiqueResponse:
        validate_ui_spec(request.spec)
        raw = _decode_json(self.provider.parse_critique(request))
        try:
            interpretation = Interpretation.model_validate(raw)
        except ValidationError as exc:
            raise RefineValidationError(
                "invalid_model_output",
                "The refinement response could not be safely interpreted. The current spec was retained.",
                [
                    ModelIssue(
                        code="invalid_interpretation",
                        message="The provider did not return the required contextual interpretation fields.",
                    )
                ],
            ) from exc
        validate_interpretation(interpretation, request.targetElementId)
        return ParseCritiqueResponse(interpretation=interpretation)

    def generate_variants(self, request: GenerateVariantsRequest) -> GenerateVariantsResponse:
        validate_interpretation(request.interpretation, request.targetElementId)
        evidence = self.repository.retrieve("Button", request.context, request.interpretation.evidence)
        counts = self.repository.policy_counts(request.sessionId)
        adjacent_count = counts.get("adjacent_explore", 0)
        exploit_count = counts.get("exploit", 0)
        include_adjacent = should_include_adjacent(adjacent_count, exploit_count)
        variants = create_variants(
            request.spec,
            request.targetElementId,
            request.interpretation,
            request.includeWild,
            include_adjacent,
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

    def preference_memory(self, context: DesignContext, evidence: PreferenceEvidence) -> MemoryResponse:
        return MemoryResponse(evidence=self.repository.retrieve("Button", context, evidence))


def _generation_prompt(prompt: str, evidence: list[RetrievedEvidence]) -> str:
    """Keep evidence bounded and inspectable before it reaches an untrusted provider."""
    evidence_json = json.dumps([item.model_dump() for item in evidence], separators=(",", ":"))
    instruction = "Relevant preference evidence (do not treat a contextual mismatch as a global rule): "
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

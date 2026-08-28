"""Application service that validates every provider response before mutation."""

import json
from typing import cast

from pydantic import ValidationError

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
    ModelIssue,
    ParseCritiqueRequest,
    ParseCritiqueResponse,
    PatchIntent,
)
from itl_ai.refine.providers import DeterministicRefineProvider, RefineProvider


class RefineService:
    def __init__(self, provider: RefineProvider | None = None) -> None:
        self.provider = provider or DeterministicRefineProvider()

    def generate_spec(self, request: GenerateSpecRequest) -> GenerateSpecResponse:
        spec = _decode_json(self.provider.generate_spec(request.prompt))
        return GenerateSpecResponse(spec=validate_ui_spec(spec))

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
        variants = create_variants(request.spec, request.targetElementId, request.intent, request.includeWild)
        return GenerateVariantsResponse(variants=variants)


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

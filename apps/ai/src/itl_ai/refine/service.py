"""Application service that validates every provider response before mutation."""

import json
from typing import cast
from uuid import uuid4

from pydantic import ValidationError

from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.catalog import (
    RefineValidationError,
    apply_and_validate_candidate_patch,
    assert_scope_matches_element,
    element_component_type,
    should_include_adjacent,
    validate_interpretation,
    validate_ui_spec,
)
from itl_ai.refine.models import (
    DEFAULT_BUTTON_SCOPE,
    AtomicScope,
    CandidateProposal,
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
    TasteBrief,
    TasteBriefDecision,
    TasteStimulus,
    Variant,
    level_for_component,
)
from itl_ai.refine.providers import DeterministicRefineProvider, ProviderUnavailableError, RefineProvider


class RefineService:
    def __init__(self, repository: PreferenceRepository, provider: RefineProvider | None = None) -> None:
        self.repository = repository
        self.provider = provider or DeterministicRefineProvider()

    def generate_spec(self, request: GenerateSpecRequest) -> GenerateSpecResponse:
        scope = _scope_for_target(request.target, request.scope)
        evidence = self.repository.retrieve(request.target, request.context, PreferenceEvidence(), scope)
        brief = _taste_brief(request.context, scope, evidence)
        spec = _decode_json(self.provider.generate_spec(request.prompt, request.target, brief))
        output_id = _output_id("spec")
        evidence_ids = [item.id for item in evidence]
        self.repository.record_generation(
            output_id, request.sessionId, "generate_spec", evidence_ids, "exploit", brief.version
        )
        return GenerateSpecResponse(spec=validate_ui_spec(spec), evidenceIds=evidence_ids, outputId=output_id)

    def parse_critique(self, request: ParseCritiqueRequest) -> ParseCritiqueResponse:
        component_type = element_component_type(request.spec, request.targetElementId)
        try:
            raw = self.provider.parse_critique(request, component_type)
            interpretation = _validated_interpretation(raw, request, component_type)
        except (ProviderUnavailableError, RefineValidationError):
            fallback = DeterministicRefineProvider().parse_critique(request, component_type)
            interpretation = _validated_interpretation(fallback, request, component_type)
        return ParseCritiqueResponse(interpretation=interpretation)

    def generate_variants(self, request: GenerateVariantsRequest) -> GenerateVariantsResponse:
        component_type = assert_scope_matches_element(request.spec, request.targetElementId, request.scope)
        validate_interpretation(request.interpretation, request.targetElementId, component_type)
        evidence = self.repository.retrieve(
            component_type, request.context, request.interpretation.evidence, request.scope
        )
        brief = _taste_brief(request.context, request.scope, evidence)
        counts = self.repository.policy_counts(request.sessionId)
        adjacent_count = counts.get("adjacent_explore", 0)
        exploit_count = counts.get("exploit", 0)
        include_adjacent = should_include_adjacent(adjacent_count, exploit_count)
        policies = _candidate_policies(request, include_adjacent)
        try:
            raw_candidates = self.provider.generate_candidate_patches(request, component_type, brief, policies)
            variants = validate_and_materialize_candidates(raw_candidates, request, policies)
        except RefineValidationError as first_error:
            raw_candidates = self.provider.generate_candidate_patches(
                request, component_type, brief, policies, _repair_feedback(first_error)
            )
            variants = validate_and_materialize_candidates(raw_candidates, request, policies)
        output_id = _output_id("variants")
        evidence_ids = [item.id for item in evidence]
        for variant in variants:
            self.repository.record_generation(
                output_id + ":" + variant.id,
                request.sessionId,
                "generate_variants",
                evidence_ids,
                variant.kind,
                brief.version,
            )
        return GenerateVariantsResponse(variants=variants, evidenceIds=evidence_ids, outputId=output_id)

    def record_preference_event(self, request: PreferenceEventRequest) -> PreferenceEventResponse:
        validate_ui_spec(request.beforeSpec)
        if request.afterSpec is not None:
            validate_ui_spec(request.afterSpec)
        event_id, created_at = self.repository.add_event(request)
        return PreferenceEventResponse(id=event_id, createdAt=created_at)

    def preference_memory(
        self,
        context: DesignContext,
        evidence: PreferenceEvidence,
        scope: AtomicScope = DEFAULT_BUTTON_SCOPE,
        component_type: str = "Button",
    ) -> MemoryResponse:
        return MemoryResponse(evidence=self.repository.retrieve(component_type, context, evidence, scope))

    def taste_brief(
        self,
        context: DesignContext,
        evidence: PreferenceEvidence,
        scope: AtomicScope = DEFAULT_BUTTON_SCOPE,
        component_type: str = "Button",
    ) -> TasteBrief:
        return _taste_brief(context, scope, self.repository.retrieve(component_type, context, evidence, scope))


def _scope_for_target(target: str, requested: AtomicScope) -> AtomicScope:
    """Refuse to learn about a subject at a level it does not belong to."""
    level = level_for_component(target)
    if requested.level != level:
        raise RefineValidationError(
            "scope_mismatch",
            f"A {target} request must use a {level}-level scope.",
            [ModelIssue(code="scope_mismatch", message="The requested scope does not describe the target subject.")],
        )
    return requested


def _taste_brief(context: DesignContext, scope: AtomicScope, evidence: list[RetrievedEvidence]) -> TasteBrief:
    return TasteBrief(
        scope=scope,
        context=context,
        evidenceIds=[item.id for item in evidence],
        decisions=[
            TasteBriefDecision(
                eventId=item.id,
                scope=item.scope,
                contextRelation=item.contextRelation,
                preferenceRelation=item.preferenceRelation,
                outcome=item.outcome,
                stimulus=(
                    TasteStimulus(
                        componentType=item.observedAppearance.componentType,
                        appearance=item.observedAppearance.appearance,
                        candidateId=item.candidateId,
                    )
                    if item.observedAppearance is not None
                    else None
                ),
                source=item.source,
                strength=item.evidence.strength,
                directives=item.directives,
            )
            for item in evidence
        ],
    )


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


def validate_and_materialize_candidates(
    raw: str | None, request: GenerateVariantsRequest, policies: list[str]
) -> list[Variant]:
    """Materialize untrusted model patches only after catalog and directive validation."""
    try:
        if raw is None:
            raise ValueError("The provider did not return candidate patches.")
        decoded = _decode_json(raw)
        raw_candidates = decoded.get("candidates")
        if not isinstance(raw_candidates, list):
            raise ValueError("The model did not return a candidates array.")
        proposals = [CandidateProposal.model_validate(item) for item in cast(list[object], raw_candidates)]
        by_kind = {proposal.kind: proposal for proposal in proposals}
        if len(proposals) != len(policies) or set(by_kind) != set(policies):
            raise ValueError("The model returned an unexpected candidate set.")
        ordered = [by_kind[kind] for kind in policies]
        signatures = {_appearance_signature(request.spec, request.targetElementId)}
        materialized: list[Variant] = []
        for proposal in ordered:
            spec = apply_and_validate_candidate_patch(
                request.spec, request.targetElementId, request.interpretation, proposal.patch
            )
            signature = _appearance_signature(spec, request.targetElementId)
            if signature in signatures:
                raise ValueError("The model returned a duplicate or unchanged candidate.")
            signatures.add(signature)
            materialized.append(
                Variant(
                    id=_canonical_variant_id(proposal.kind),
                    kind=proposal.kind,
                    direction=proposal.patch.rationale,
                    spec=spec,
                )
            )
        return materialized
    except RefineValidationError:
        raise
    except (ValidationError, ValueError) as exc:
        raise RefineValidationError(
            "invalid_candidate_patch",
            "The model proposed invalid candidate patches. The current spec was retained.",
            [ModelIssue(code="invalid_candidate_patch", message=str(exc))],
        ) from exc


def _candidate_policies(request: GenerateVariantsRequest, include_adjacent: bool) -> list[str]:
    policies = ["exploit"]
    if include_adjacent:
        policies.append("adjacent_explore")
    if request.includeWild:
        policies.append("wild_explore")
    return policies


def _repair_feedback(error: RefineValidationError) -> str:
    return json.dumps(
        {
            "message": "Repair the rejected proposal. Return a complete replacement candidates array only.",
            "rejection": error.message,
            "issues": [issue.model_dump() for issue in error.issues],
        },
        separators=(",", ":"),
    )


def _appearance_signature(spec: object, target_element_id: str) -> tuple[tuple[str, object], ...]:
    validated = validate_ui_spec(spec)
    elements = cast(dict[str, object], validated["elements"])
    element = cast(dict[str, object], elements[target_element_id])
    props = cast(dict[str, object], element["props"])
    appearance = cast(dict[str, object], props["appearance"])
    return tuple(sorted(appearance.items()))


def _canonical_variant_id(kind: str) -> str:
    return f"{kind.replace('_', '-')}-1"


def _validated_interpretation(raw: str, request: ParseCritiqueRequest, component_type: str) -> Interpretation:
    decoded = _decode_json(raw)
    candidate = decoded.get("interpretation", decoded)
    try:
        interpretation = Interpretation.model_validate(candidate)
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
    validate_interpretation(interpretation, request.targetElementId, component_type)
    return interpretation

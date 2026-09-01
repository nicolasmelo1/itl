import json
from pathlib import Path

from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.models import (
    AtomicScope,
    DecreaseDirective,
    DesignContext,
    GenerateVariantsRequest,
    Interpretation,
    PreferenceEventRequest,
    PreferenceEvidence,
)
from itl_ai.refine.service import RefineService


def button_spec(radius: str = "soft") -> dict[str, object]:
    return {
        "version": "itl.ui/v1",
        "root": "continue-button",
        "elements": {
            "continue-button": {
                "type": "Button",
                "props": {
                    "content": {"label": "Continue"},
                    "semantic": {"role": "primary-action", "state": "default"},
                    "appearance": {
                        "recipe": "primary",
                        "size": "regular",
                        "radius": radius,
                        "density": "comfortable",
                        "fontWeight": "semibold",
                    },
                },
                "children": [],
            }
        },
    }


def context(surface: str, density: str = "comfortable") -> DesignContext:
    return DesignContext(role="primary-action", surface=surface, density=density)


def event(surface: str, radius: str, strength: str = "moderate") -> PreferenceEventRequest:
    evidence = PreferenceEvidence(
        likedPaths=["/appearance/radius"],
        lockedPaths=["/appearance/radius"],
        strength=strength,
    )
    return PreferenceEventRequest(
        sessionId="evaluation",
        componentType="Button",
        context=context(surface),
        targetElementId="continue-button",
        action="confirmed_critique",
        source="confirmed_critique",
        beforeSpec=button_spec(),
        afterSpec=button_spec(radius=radius),
        evidence=evidence,
        directives=[DecreaseDirective(kind="decrease", path="/appearance/radius")],
        critique=f"Use {radius} buttons here.",
    )


def service(tmp_path: Path) -> tuple[RefineService, PreferenceRepository]:
    repository = PreferenceRepository(tmp_path / "preferences.sqlite")
    return RefineService(repository), repository


def test_memory_events_persist_typed_context_evidence_directives_and_diff(tmp_path: Path) -> None:
    refine, repository = service(tmp_path)
    recorded = refine.record_preference_event(event("hero", "square", "strong"))
    with repository._connection() as connection:
        row = connection.execute(
            "SELECT context_json, evidence_json, directives_json, spec_diff_json FROM preference_events WHERE id = 1"
        ).fetchone()
    assert recorded.id == 1
    assert row is not None
    assert '"surface":"hero"' in row["context_json"]
    assert '"strength":"strong"' in row["evidence_json"]
    assert '"kind":"decrease"' in row["directives_json"]
    assert "/appearance/radius" in row["spec_diff_json"]


def test_button_retrieval_is_contextual_and_keeps_mismatches_visible(tmp_path: Path) -> None:
    refine, _ = service(tmp_path)
    toolbar = refine.record_preference_event(event("toolbar", "square", "strong"))
    hero = refine.record_preference_event(event("hero", "pill", "moderate"))
    query = PreferenceEvidence(likedPaths=["/appearance/radius"], strength="moderate")
    evidence = refine.preference_memory(context("hero"), query).evidence
    assert evidence[0].id == hero.id
    assert evidence[0].contextRelation == "exact"
    assert evidence[0].preferenceRelation == "supporting"
    assert any(item.id == toolbar.id and item.contextRelation == "mismatch" for item in evidence)


def test_button_retrieval_reports_compatible_and_conflicting_relations(tmp_path: Path) -> None:
    refine, _ = service(tmp_path)
    refine.record_preference_event(event("form", "square"))
    compatible = refine.preference_memory(context("form", "compact"), PreferenceEvidence()).evidence[0]
    conflicting = refine.preference_memory(
        context("form"), PreferenceEvidence(dislikedPaths=["/appearance/radius"])
    ).evidence[0]
    assert compatible.contextRelation == "compatible"
    assert conflicting.preferenceRelation == "conflicting"


def test_retrieval_projects_the_concrete_design_and_auditable_feedback(tmp_path: Path) -> None:
    refine, _ = service(tmp_path)
    request = PreferenceEventRequest(
        sessionId="evaluation",
        componentType="Button",
        context=context("hero"),
        targetElementId="continue-button",
        action="candidate_acceptance",
        source="candidate_acceptance",
        beforeSpec=button_spec(),
        afterSpec=button_spec(radius="pill"),
        candidateId="exploit-1",
        evidence=PreferenceEvidence(likedPaths=["/appearance/radius"], strength="strong"),
        directives=[DecreaseDirective(kind="decrease", path="/appearance/radius")],
        critique="Use a pill treatment in the hero.",
    )
    recorded = refine.record_preference_event(request)

    retrieved = refine.preference_memory(context("hero"), PreferenceEvidence()).evidence[0]

    assert retrieved.id == recorded.id
    assert retrieved.outcome == "accepted"
    assert retrieved.candidateId == "exploit-1"
    assert retrieved.observedAppearance is not None
    assert retrieved.observedAppearance.componentType == "Button"
    assert retrieved.observedAppearance.appearance["radius"] == "pill"
    assert [(change.path, change.before, change.after) for change in retrieved.diff] == [
        ("/elements/continue-button/props/appearance/radius", "soft", "pill")
    ]
    assert retrieved.directives == [DecreaseDirective(kind="decrease", path="/appearance/radius")]


def test_retrieval_projects_almost_and_rejected_candidate_appearances(tmp_path: Path) -> None:
    refine, _ = service(tmp_path)
    for action, radius in (("almost", "square"), ("rejection", "pill")):
        refine.record_preference_event(
            PreferenceEventRequest(
                sessionId="evaluation",
                componentType="Button",
                context=context("hero"),
                targetElementId="continue-button",
                action=action,
                source="explicit_attribute_feedback" if action == "almost" else "absolute_feedback",
                beforeSpec=button_spec(),
                afterSpec=button_spec(radius=radius),
                candidateId=f"{action}-1",
            )
        )

    retrieved = refine.preference_memory(context("hero"), PreferenceEvidence()).evidence
    outcomes = {
        item.outcome: item.observedAppearance.appearance["radius"] for item in retrieved if item.observedAppearance
    }
    assert outcomes == {"almost": "square", "rejected": "pill"}


def test_relevance_ranks_a_high_confidence_rejection_without_changing_its_polarity(tmp_path: Path) -> None:
    refine, _ = service(tmp_path)
    scope = AtomicScope(level="atom", id="hero-continue-button", semanticRole="primary-action")
    refine.record_preference_event(
        PreferenceEventRequest(
            sessionId="evaluation",
            componentType="Button",
            scope=scope,
            context=context("hero"),
            targetElementId="continue-button",
            action="candidate_acceptance",
            source="candidate_acceptance",
            beforeSpec=button_spec("square"),
            candidateId="accepted-square",
            evidence=PreferenceEvidence(strength="weak"),
        )
    )
    rejected = refine.record_preference_event(
        PreferenceEventRequest(
            sessionId="evaluation",
            componentType="Button",
            scope=scope,
            context=context("hero"),
            targetElementId="continue-button",
            action="rejection",
            source="manual_edit",
            beforeSpec=button_spec("pill"),
            candidateId="rejected-pill",
            evidence=PreferenceEvidence(strength="strong"),
        )
    )

    evidence = refine.preference_memory(context("hero"), PreferenceEvidence(), scope).evidence
    assert evidence[0].id == rejected.id
    assert evidence[0].outcome == "rejected"
    assert evidence[0].preferenceRelation == "unknown"


def test_wild_policy_preserves_explicit_keeps(tmp_path: Path) -> None:
    refine, _ = service(tmp_path)
    request = Interpretation(
        targetElementId="continue-button",
        evidence=PreferenceEvidence(lockedPaths=["/appearance/recipe"]),
        directives=[
            {"kind": "keep", "path": "/appearance/recipe"},
            {"kind": "decrease", "path": "/appearance/radius"},
        ],
        rationale="Keep primary recipe while reducing radius.",
    )
    result = refine.generate_variants(
        GenerateVariantsRequest(
            sessionId="evaluation",
            specVersion="itl.ui/v1",
            spec=button_spec(),
            targetElementId="continue-button",
            interpretation=request,
            includeWild=True,
            context=context("hero"),
        )
    )
    assert [variant.kind for variant in result.variants] == ["exploit", "adjacent_explore", "wild_explore"]
    assert all(
        variant.spec["elements"]["continue-button"]["props"]["appearance"]["recipe"] == "primary"
        for variant in result.variants
    )


def test_live_provider_candidates_are_used_when_they_are_valid_and_distinct(tmp_path: Path) -> None:
    class ModelProvider:
        def generate_candidate_patches(self, request, component_type, taste_brief, policies, repair_feedback=None):
            del taste_brief
            return json.dumps(
                {
                    "candidates": [
                        {
                            "kind": "exploit",
                            "patch": {
                                "changes": [{"path": "/appearance/radius", "value": "square"}],
                                "rationale": "model radius",
                            },
                        },
                        {
                            "kind": "adjacent_explore",
                            "patch": {
                                "changes": [{"path": "/appearance/density", "value": "compact"}],
                                "rationale": "model density",
                            },
                        },
                    ]
                }
            )

    request = GenerateVariantsRequest(
        sessionId="evaluation",
        specVersion="itl.ui/v1",
        spec=button_spec(),
        targetElementId="continue-button",
        interpretation=Interpretation(
            targetElementId="continue-button",
            evidence=PreferenceEvidence(lockedPaths=["/appearance/recipe"]),
            directives=[
                {"kind": "keep", "path": "/appearance/recipe"},
                {"kind": "explore", "path": "/appearance/radius"},
            ],
            rationale="Keep the recipe and explore shape.",
        ),
        context=context("hero"),
    )
    refine = RefineService(PreferenceRepository(tmp_path / "preferences.sqlite"), ModelProvider())

    result = refine.generate_variants(request)

    assert [variant.id for variant in result.variants] == ["exploit-1", "adjacent-explore-1"]
    assert [variant.direction for variant in result.variants] == ["model radius", "model density"]


def test_invalid_candidate_patches_are_repaired_once_before_rendering(tmp_path: Path) -> None:
    class RepairingProvider:
        calls = 0

        def generate_candidate_patches(self, request, component_type, taste_brief, policies, repair_feedback=None):
            del taste_brief
            self.calls += 1
            value = "ghost" if repair_feedback is None else "primary"
            return json.dumps(
                {
                    "candidates": [
                        {
                            "kind": "exploit",
                            "patch": {
                                "changes": [
                                    {"path": "/appearance/recipe", "value": value},
                                    {"path": "/appearance/density", "value": "compact"},
                                ],
                                "rationale": "repairable recipe proposal",
                            },
                        },
                        {
                            "kind": "adjacent_explore",
                            "patch": {
                                "changes": [{"path": "/appearance/radius", "value": "square"}],
                                "rationale": "repairable radius proposal",
                            },
                        },
                    ]
                }
            )

    provider = RepairingProvider()
    request = GenerateVariantsRequest(
        sessionId="evaluation",
        specVersion="itl.ui/v1",
        spec=button_spec(),
        targetElementId="continue-button",
        interpretation=Interpretation(
            targetElementId="continue-button",
            evidence=PreferenceEvidence(lockedPaths=["/appearance/recipe"]),
            directives=[
                {"kind": "keep", "path": "/appearance/recipe"},
                {"kind": "explore", "path": "/appearance/radius"},
            ],
            rationale="Keep the recipe and explore shape.",
        ),
        context=context("hero"),
    )

    result = RefineService(PreferenceRepository(tmp_path / "preferences.sqlite"), provider).generate_variants(request)

    assert provider.calls == 2
    appearance = result.variants[0].spec["elements"]["continue-button"]["props"]["appearance"]
    assert appearance["recipe"] == "primary"
    assert appearance["density"] == "compact"

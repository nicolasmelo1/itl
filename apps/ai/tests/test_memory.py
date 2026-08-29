from pathlib import Path
from typing import Literal, cast

from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.models import GenerateSpecRequest, GenerateVariantsRequest, PatchIntent, PreferenceEventRequest
from itl_ai.refine.service import RefineService


def button_spec(label: str = "Continue", radius: str = "soft") -> dict[str, object]:
    return {
        "version": "itl.ui/v1",
        "root": "continue-button",
        "elements": {
            "continue-button": {
                "type": "Button",
                "props": {
                    "label": label,
                    "variant": "solid",
                    "size": "regular",
                    "radius": radius,
                    "density": "comfortable",
                    "background": "accent",
                    "foreground": "light",
                    "border": "none",
                    "fontWeight": "semibold",
                    "state": "default",
                },
                "children": [],
            }
        },
    }


def event(
    context: str,
    radius: str,
    source: Literal[
        "manual_edit",
        "confirmed_critique",
        "explicit_attribute_feedback",
        "absolute_feedback",
        "pairwise_choice",
        "candidate_acceptance",
        "model_inference",
    ] = "confirmed_critique",
) -> PreferenceEventRequest:
    return PreferenceEventRequest(
        sessionId="evaluation",
        componentType="Button",
        context=context,
        targetElementId="continue-button",
        action="confirmed_critique",
        source=source,
        beforeSpec=button_spec(),
        afterSpec=button_spec(radius=radius),
        likedPaths=["/props/radius"],
        lockedPaths=["/props/radius"],
        critique=f"Use {radius} buttons here.",
    )


def service(tmp_path: Path) -> tuple[RefineService, PreferenceRepository]:
    repository = PreferenceRepository(tmp_path / "preferences.sqlite")
    return RefineService(repository), repository


def test_memory_explicit_feedback_is_immutable_and_queryable(tmp_path: Path) -> None:
    refine, _ = service(tmp_path)
    recorded = refine.record_preference_event(event("dashboard", "square", "manual_edit"))

    evidence = refine.preference_memory("dashboard", {"/props/radius"}).evidence

    assert recorded.id == 1
    assert evidence[0].id == recorded.id
    assert evidence[0].lockedPaths == ["/props/radius"]
    # A subsequent action produces a new ID rather than updating the original raw evidence.
    assert refine.record_preference_event(event("dashboard", "soft")).id == 2


def test_memory_retrieval_is_auditable_and_contextual(tmp_path: Path) -> None:
    refine, repository = service(tmp_path)
    dashboard = refine.record_preference_event(event("dense dashboard", "square"))
    cta = refine.record_preference_event(event("marketing CTA", "pill", "manual_edit"))

    generated = refine.generate_spec(GenerateSpecRequest(context="marketing CTA", sessionId="marketing"))
    evidence = refine.preference_memory("marketing CTA", {"/props/radius"}).evidence

    assert generated.evidenceIds == repository.evidence_for_output(generated.outputId)
    assert evidence[0].id == cta.id
    assert evidence[0].contextRelation == "exact"
    assert evidence[0].preferenceRelation == "supporting"
    assert any(
        item.id == dashboard.id and item.contextRelation == "mismatch" and item.preferenceRelation == "unknown"
        for item in evidence
    )


def test_candidate_acceptance_keeps_candidate_identity_separate_from_element_identity(tmp_path: Path) -> None:
    refine, repository = service(tmp_path)
    accepted = event("marketing CTA", "pill").model_copy(
        update={
            "action": "candidate_acceptance",
            "source": "candidate_acceptance",
            "selectedElementId": "continue-button",
            "candidateId": "wild-explore-1",
        }
    )

    refine.record_preference_event(accepted)
    with repository._connection() as connection:
        row = connection.execute(
            "SELECT selected_element_id, candidate_id FROM preference_events WHERE id = 1"
        ).fetchone()

    assert row is not None
    assert row["selected_element_id"] == "continue-button"
    assert row["candidate_id"] == "wild-explore-1"


def test_exploration_policies_are_distinct_and_non_coercive(tmp_path: Path) -> None:
    refine, _ = service(tmp_path)
    request = GenerateVariantsRequest(
        specVersion="itl.ui/v1",
        spec=button_spec(),
        targetElementId="continue-button",
        sessionId="exploration",
        intent=PatchIntent(
            targetElementId="continue-button",
            likedPaths=[],
            dislikedPaths=["/props/radius"],
            lockedPaths=[],
            explorationPaths=["/props/radius"],
            ambiguity=[],
            rationale="Explore radius.",
        ),
        includeWild=True,
    )

    generated = refine.generate_variants(request)

    assert [variant.kind for variant in generated.variants] == ["exploit", "adjacent_explore", "wild_explore"]
    assert len({variant.direction for variant in generated.variants}) == 3
    # A follow-up respects the session budget: exploitation remains available without inventing a winner.
    assert [variant.kind for variant in refine.generate_variants(request).variants] == ["exploit", "wild_explore"]


def test_evaluation_counterfactual_constraints_hold(tmp_path: Path) -> None:
    refine, _ = service(tmp_path)
    request = GenerateVariantsRequest(
        specVersion="itl.ui/v1",
        spec=button_spec(label="Pay $12.00"),
        targetElementId="continue-button",
        intent=PatchIntent(
            targetElementId="continue-button",
            likedPaths=["/props/background"],
            dislikedPaths=["/props/radius"],
            lockedPaths=["/props/background"],
            explorationPaths=["/props/radius"],
            ambiguity=[],
            rationale="Keep the accent, vary radius.",
        ),
    )
    counterfactual = request.model_copy(update={"spec": button_spec(label="Transfer R$ 1.999,00")})

    for variant in refine.generate_variants(counterfactual).variants:
        elements = cast(dict[str, object], variant.spec["elements"])
        button = cast(dict[str, object], elements["continue-button"])
        props = cast(dict[str, str], button["props"])
        assert props["label"] == "Transfer R$ 1.999,00"
        assert props["background"] == "accent"


def test_evaluation_holdout_is_excluded_from_optimization() -> None:
    corpus = Path(__file__).parent / "fixtures" / "memory" / "evaluation-corpus.json"
    contents = corpus.read_text()

    assert '"split": "hidden_human_review"' in contents
    assert '"optimizerTrainingIds": []' in contents

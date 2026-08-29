from pathlib import Path

from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.models import (
    DecreaseDirective,
    DesignContext,
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


def test_explicit_recipe_centroid_is_opt_in_and_preserves_keeps(tmp_path: Path) -> None:
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
    from itl_ai.refine.models import GenerateVariantsRequest

    result = refine.generate_variants(
        GenerateVariantsRequest(
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

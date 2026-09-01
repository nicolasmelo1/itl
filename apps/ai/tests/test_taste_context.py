"""Product tone and screen position are two axes, compared independently.

Round buttons in a playful product and square ones in a serious one used to
read as one context, and therefore as the person contradicting themselves. The
system now has an axis on which those two rows legitimately differ.
"""

from pathlib import Path

from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.models import (
    AtomicScope,
    DesignContext,
    PreferenceEventRequest,
    PreferenceEvidence,
    ProjectContext,
    RetrievedEvidence,
)
from itl_ai.refine.service import RefineService

SCOPE = AtomicScope(level="atom", id="hero-continue-button", semanticRole="primary-action")
SERIOUS = ProjectContext(productKind="saas", visualTone=["serious", "minimal"], platform="web")
PLAYFUL = ProjectContext(productKind="marketing", visualTone=["playful"], platform="web")
SERIOUS_SIBLING = ProjectContext(productKind="saas", visualTone=["serious", "calm"], platform="web")
HERO = DesignContext(role="primary-action", surface="hero", density="comfortable")


def button_spec(radius: str = "square") -> dict[str, object]:
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


def serious_hero_judgment(refine: RefineService) -> int:
    return refine.record_preference_event(
        PreferenceEventRequest(
            sessionId="context-session-1",
            componentType="Button",
            scope=SCOPE,
            context=HERO,
            projectContext=SERIOUS,
            targetElementId="continue-button",
            action="candidate_acceptance",
            source="candidate_acceptance",
            beforeSpec=button_spec("square"),
            candidateId="accepted-square",
        )
    ).id


def only(evidence: list[RetrievedEvidence]) -> RetrievedEvidence:
    if len(evidence) != 1:
        raise AssertionError(f"Expected exactly one retrieved row, got {len(evidence)}.")
    return evidence[0]


def retrieve(
    repository: PreferenceRepository, context: DesignContext, project: ProjectContext | None
) -> RetrievedEvidence:
    return only(repository.retrieve("Button", context, PreferenceEvidence(), SCOPE, project))


def test_the_same_usage_under_two_product_tones_is_compatible_not_a_contradiction(tmp_path: Path) -> None:
    repository = PreferenceRepository(tmp_path / "preferences.sqlite")
    serious_hero_judgment(RefineService(repository))

    retrieved = retrieve(repository, HERO, PLAYFUL)

    assert retrieved.relations.usage == "exact"
    assert retrieved.relations.project == "mismatch"
    assert retrieved.relations.overall == "compatible"
    assert retrieved.contextRelation == "compatible"


def test_each_axis_moves_only_when_its_own_axis_changes(tmp_path: Path) -> None:
    repository = PreferenceRepository(tmp_path / "preferences.sqlite")
    serious_hero_judgment(RefineService(repository))

    same = retrieve(repository, HERO, SERIOUS)
    assert (same.relations.usage, same.relations.project, same.relations.overall) == ("exact", "exact", "exact")

    # Only the product tone moves.
    other_tone = retrieve(repository, HERO, PLAYFUL)
    assert other_tone.relations.usage == same.relations.usage
    assert other_tone.relations.project == "mismatch"

    # Only the position on the screen moves.
    compact_hero = HERO.model_copy(update={"density": "compact"})
    other_usage = retrieve(repository, compact_hero, SERIOUS)
    assert other_usage.relations.project == same.relations.project
    assert other_usage.relations.usage == "compatible"

    toolbar = HERO.model_copy(update={"surface": "toolbar"})
    assert retrieve(repository, toolbar, SERIOUS).relations.usage == "mismatch"


def test_a_neighbouring_product_tone_is_compatible_and_an_unnamed_one_is_global(tmp_path: Path) -> None:
    repository = PreferenceRepository(tmp_path / "preferences.sqlite")
    serious_hero_judgment(RefineService(repository))

    assert retrieve(repository, HERO, SERIOUS_SIBLING).relations.project == "compatible"
    # An unspecified product tone is unknown, never a contradiction, and the
    # usage axis still answers on its own.
    unnamed = retrieve(repository, HERO, None)
    assert unnamed.relations.project == "global"
    assert unnamed.relations.overall == "exact"


def test_a_contested_product_tone_still_reaches_the_shared_dimension_space(tmp_path: Path) -> None:
    """A different tone discounts a reading; it does not delete the evidence."""
    repository = PreferenceRepository(tmp_path / "preferences.sqlite")
    refine = RefineService(repository)
    event_id = serious_hero_judgment(refine)

    same_tone = refine.preference_memory(HERO, PreferenceEvidence(), SCOPE, "Button", SERIOUS)
    other_tone = refine.preference_memory(HERO, PreferenceEvidence(), SCOPE, "Button", PLAYFUL)

    radius = {reading.dimension: reading for reading in same_tone.dimensions}["shape.radius"]
    contested = {reading.dimension: reading for reading in other_tone.dimensions}["shape.radius"]
    assert radius.coordinate == contested.coordinate == 0.0
    assert radius.eventIds == contested.eventIds == [event_id]

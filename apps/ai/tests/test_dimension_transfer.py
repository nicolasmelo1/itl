"""A judgment transfers along a shared dimension, and along nothing else.

This is the difference between a system that learned Button trivia and one that
learned taste. The event log stays partitioned by subject — an atom decision is
still never retrieved as a molecule's decision — but the dimension altitude is
readable across components that declare the same dimension.
"""

from pathlib import Path

from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.dimensions import dimensions_for
from itl_ai.refine.models import (
    AtomicScope,
    DesignContext,
    DimensionEvidence,
    PreferenceEventRequest,
    PreferenceEvidence,
    ProjectContext,
)
from itl_ai.refine.service import RefineService

BUTTON_SCOPE = AtomicScope(level="atom", id="hero-continue-button", semanticRole="primary-action")
FIELD_SCOPE = AtomicScope(level="molecule", id="settings-email-field", semanticRole="account-email")
PROJECT = ProjectContext(productKind="saas", visualTone=["serious"], platform="web")
# Button reads this through `recipe`; FormField reads it through `hintTone`.
SHARED = "emphasis.contrast"
# Declared by FormField alone, so a Button judgment must never move it.
FIELD_ONLY = "density.spacing"


def button_spec(recipe: str = "ghost") -> dict[str, object]:
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
                        "recipe": recipe,
                        "size": "regular",
                        "radius": "pill",
                        "density": "comfortable",
                        "fontWeight": "semibold",
                    },
                },
                "children": [],
            }
        },
    }


def field_spec(hint_tone: str = "strong") -> dict[str, object]:
    return {
        "version": "itl.ui/v1",
        "root": "email-field",
        "elements": {
            "email-field": {
                "type": "FormField",
                "props": {
                    "label": "Account email",
                    "hint": "We use this address for essential project notifications.",
                    "appearance": {"labelPlacement": "above", "gap": "regular", "hintTone": hint_tone},
                },
                "children": ["account-email"],
            },
            "account-email": {
                "type": "Input",
                "props": {
                    "label": "Email address",
                    "placeholder": "you@example.com",
                    "value": "",
                    "tone": "quiet",
                    "state": "default",
                },
                "children": [],
            },
        },
    }


def context() -> DesignContext:
    return DesignContext(role="primary-action", surface="hero", density="comfortable")


def accepted_button(refine: RefineService) -> int:
    return refine.record_preference_event(
        PreferenceEventRequest(
            sessionId="transfer-session-1",
            componentType="Button",
            scope=BUTTON_SCOPE,
            context=context(),
            projectContext=PROJECT,
            targetElementId="continue-button",
            action="candidate_acceptance",
            source="candidate_acceptance",
            beforeSpec=button_spec("ghost"),
            candidateId="accepted-ghost",
            evidence=PreferenceEvidence(strength="strong"),
        )
    ).id


def field_readings(refine: RefineService) -> dict[str, DimensionEvidence]:
    memory = refine.preference_memory(context(), PreferenceEvidence(), FIELD_SCOPE, "FormField", PROJECT)
    return {item.dimension: item for item in memory.dimensions}


def test_a_button_judgment_moves_a_field_dimension_they_both_declare(tmp_path: Path) -> None:
    refine = RefineService(PreferenceRepository(tmp_path / "preferences.sqlite"))

    before = field_readings(refine)
    assert before[SHARED].support == 0
    assert before[SHARED].coordinate is None
    assert before[SHARED].agreement == "unknown"

    event_id = accepted_button(refine)
    after = field_readings(refine)

    assert after[SHARED].support > before[SHARED].support
    assert after[SHARED].coordinate == 0.0
    # The Field expresses that same point through its own catalog value.
    assert after[SHARED].token == "hintTone"
    assert after[SHARED].nearestValue == "quiet"
    assert after[SHARED].eventIds == [event_id]
    assert [source.componentType for source in after[SHARED].sources] == ["Button"]


def test_a_button_judgment_moves_no_dimension_the_field_does_not_share(tmp_path: Path) -> None:
    refine = RefineService(PreferenceRepository(tmp_path / "preferences.sqlite"))

    before = field_readings(refine)
    accepted_button(refine)
    after = field_readings(refine)

    assert set(after) == dimensions_for("FormField")
    # `shape.radius` was part of the very same judgment. The Field does not
    # declare it, so it is not even a readable dimension here.
    assert "shape.radius" not in after
    assert after[FIELD_ONLY].support == before[FIELD_ONLY].support == 0
    assert after[FIELD_ONLY].coordinate is None


def test_a_field_judgment_and_a_button_judgment_can_contradict_on_the_shared_dimension(tmp_path: Path) -> None:
    """Contradiction is an output, not a failure, and it names its residual."""
    refine = RefineService(PreferenceRepository(tmp_path / "preferences.sqlite"))
    accepted_button(refine)
    refine.record_preference_event(
        PreferenceEventRequest(
            sessionId="transfer-session-1",
            componentType="FormField",
            scope=FIELD_SCOPE,
            context=context(),
            projectContext=PROJECT,
            targetElementId="email-field",
            action="candidate_acceptance",
            source="candidate_acceptance",
            beforeSpec=field_spec("strong"),
            candidateId="accepted-strong",
            evidence=PreferenceEvidence(strength="strong"),
        )
    )

    reading = field_readings(refine)[SHARED]
    assert reading.agreement == "contradictory"
    assert [source.componentType for source in reading.sources] == ["Button", "FormField"]

    residual = reading.residual
    assert residual is not None
    assert residual.componentType == "FormField"
    # The Field sits high on contrast while the shared reading sits between the
    # two: an exception that does not generalize, kept as its own statement.
    assert residual.componentCoordinate == 1.0
    assert residual.isException is True


def test_the_event_log_stays_partitioned_by_subject(tmp_path: Path) -> None:
    """Sharing happens at the dimension altitude only, never at event altitude."""
    refine = RefineService(PreferenceRepository(tmp_path / "preferences.sqlite"))
    button_event = accepted_button(refine)

    field_memory = refine.preference_memory(context(), PreferenceEvidence(), FIELD_SCOPE, "FormField", PROJECT)
    assert [item.id for item in field_memory.evidence] == []

    button_memory = refine.preference_memory(context(), PreferenceEvidence(), BUTTON_SCOPE, "Button", PROJECT)
    assert [item.id for item in button_memory.evidence] == [button_event]

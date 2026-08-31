from pathlib import Path

from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.models import (
    AtomicScope,
    DecreaseDirective,
    DesignContext,
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


def context(surface: str = "hero") -> DesignContext:
    return DesignContext(role="primary-action", surface=surface, density="comfortable")


def test_taste_brief_is_minimized_versioned_and_auditable(tmp_path: Path) -> None:
    repository = PreferenceRepository(tmp_path / "preferences.sqlite")
    refine = RefineService(repository)
    scope = AtomicScope(level="atom", id="hero-continue-button", semanticRole="primary-action")
    recorded = refine.record_preference_event(
        PreferenceEventRequest(
            sessionId="taste-brief-session",
            componentType="Button",
            scope=scope,
            context=context(),
            targetElementId="continue-button",
            action="confirmed_critique",
            source="confirmed_critique",
            beforeSpec=button_spec(),
            afterSpec=button_spec("square"),
            evidence=PreferenceEvidence(lockedPaths=["/appearance/radius"], strength="strong"),
            directives=[DecreaseDirective(kind="decrease", path="/appearance/radius")],
            critique="Do not expose this private critique to the model.",
        )
    )

    brief = refine.taste_brief(context(), PreferenceEvidence(), scope)
    serialized = brief.model_dump_json()
    assert brief.version == "itl.taste-brief/v1"
    assert brief.evidenceIds == [recorded.id]
    assert brief.decisions[0].eventId == recorded.id
    assert brief.decisions[0].directives == [DecreaseDirective(kind="decrease", path="/appearance/radius")]
    assert "private critique" not in serialized
    assert "beforeSpec" not in serialized
    assert "afterSpec" not in serialized

    repository.record_generation(
        "taste-brief-output", "taste-brief-session", "generate_spec", brief.evidenceIds, "exploit", brief.version
    )
    assert repository.evidence_for_output("taste-brief-output") == [recorded.id]
    assert repository.brief_version_for_output("taste-brief-output") == "itl.taste-brief/v1"

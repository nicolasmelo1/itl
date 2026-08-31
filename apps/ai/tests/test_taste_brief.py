import json
from pathlib import Path
from typing import cast

import httpx

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
from itl_ai.refine.providers import OpenAICompatibleRefineProvider
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


def assert_private_event_fields_stay_server_side(serialized: str) -> None:
    """A brief may name a decision; it may never carry that decision's raw record."""
    for forbidden in ("private critique", "beforeSpec", "afterSpec", "parserInterpretation"):
        assert forbidden not in serialized


def test_taste_brief_is_minimized_versioned_auditable_and_provider_bounded(tmp_path: Path) -> None:
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
    assert brief.version == "itl.taste-brief/v3"
    assert brief.evidenceIds == [recorded.id]
    assert brief.decisions[0].eventId == recorded.id
    assert brief.decisions[0].outcome == "manual_edit"
    assert brief.decisions[0].stimulus is not None
    assert brief.decisions[0].stimulus.componentType == "Button"
    assert brief.decisions[0].stimulus.appearance["radius"] == "square"
    assert brief.decisions[0].directives == [DecreaseDirective(kind="decrease", path="/appearance/radius")]
    assert_private_event_fields_stay_server_side(serialized)

    repository.record_generation(
        "taste-brief-output", "taste-brief-session", "generate_spec", brief.evidenceIds, "exploit", brief.version
    )
    assert repository.evidence_for_output("taste-brief-output") == [recorded.id]
    assert repository.brief_version_for_output("taste-brief-output") == "itl.taste-brief/v3"


def test_taste_brief_preserves_every_human_outcome_and_shown_candidate(tmp_path: Path) -> None:
    repository = PreferenceRepository(tmp_path / "preferences.sqlite")
    refine = RefineService(repository)
    scope = AtomicScope(level="atom", id="settings-save-button", semanticRole="primary-action")
    reactions = [
        ("candidate_acceptance", "accepted", "square", "accepted-square"),
        ("almost", "almost", "soft", "almost-soft"),
        ("rejection", "rejected", "pill", "rejected-pill"),
        ("indifference", "indifferent", "square", "indifferent-square"),
        ("manual_edit", "manual_edit", "pill", "manual-pill"),
    ]
    for action, _, radius, candidate_id in reactions:
        refine.record_preference_event(
            PreferenceEventRequest(
                componentType="Button",
                scope=scope,
                context=context(),
                targetElementId="continue-button",
                action=action,
                source="candidate_acceptance" if action == "candidate_acceptance" else "manual_edit",
                beforeSpec=button_spec(radius),
                candidateId=candidate_id,
            )
        )

    decisions = {
        decision.outcome: decision for decision in refine.taste_brief(context(), PreferenceEvidence(), scope).decisions
    }
    assert decisions["accepted"].stimulus.appearance["radius"] == "square"
    assert decisions["almost"].stimulus.appearance["radius"] == "soft"
    assert decisions["rejected"].stimulus.appearance["radius"] == "pill"
    assert decisions["indifferent"].stimulus.candidateId == "indifferent-square"
    assert decisions["manual_edit"].stimulus.candidateId == "manual-pill"


def test_remote_provider_payload_contains_only_the_taste_brief_memory_boundary(monkeypatch, tmp_path: Path) -> None:
    repository = PreferenceRepository(tmp_path / "preferences.sqlite")
    refine = RefineService(repository)
    scope = AtomicScope(level="atom", id="settings-save-button", semanticRole="primary-action")
    refine.record_preference_event(
        PreferenceEventRequest(
            componentType="Button",
            scope=scope,
            context=context(),
            targetElementId="continue-button",
            action="rejection",
            source="absolute_feedback",
            beforeSpec=button_spec("pill"),
            candidateId="rejected-pill",
            critique="Private critique must stay server-side.",
        )
    )
    brief = refine.taste_brief(context(), PreferenceEvidence(), scope)
    provider = OpenAICompatibleRefineProvider("https://provider.example/v1", "test-key", "test-model")
    captured: dict[str, object] = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": '{"candidates":[]}'}}]}

    def fake_post(*args, **kwargs):
        del args
        captured["body"] = json.loads(kwargs["content"])
        return Response()

    monkeypatch.setattr(httpx, "post", fake_post)
    provider.generate_candidate_patches(
        component_type="Button",
        request=GenerateVariantsRequest(
            specVersion="itl.ui/v1",
            spec=button_spec(),
            targetElementId="continue-button",
            interpretation=Interpretation(
                targetElementId="continue-button",
                evidence=PreferenceEvidence(),
                directives=[{"kind": "explore", "path": "/appearance/radius"}],
                rationale="Explore shape.",
            ),
            context=context(),
            scope=scope,
        ),
        taste_brief=brief,
        policies=["exploit"],
    )

    body = cast(dict[str, object], captured["body"])
    messages = cast(list[dict[str, str]], body["messages"])
    payload = json.dumps(body)
    user_content = messages[1]["content"]
    assert '"tasteBrief"' in user_content
    assert "retrievedEvidence" not in payload
    for forbidden in ("critique", "beforeSpec", "afterSpec", "parserInterpretation"):
        assert forbidden not in payload

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.models import (
    AtomicScope,
    DesignContext,
    GenerateSpecRequest,
    GenerateVariantsRequest,
    Interpretation,
    PreferenceEventRequest,
    PreferenceEvidence,
)
from itl_ai.refine.service import RefineService


def button_spec() -> dict[str, object]:
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
                        "radius": "soft",
                        "density": "comfortable",
                        "fontWeight": "semibold",
                    },
                },
                "children": [],
            }
        },
    }


def context() -> DesignContext:
    return DesignContext(role="primary-action", surface="hero", density="comfortable")


def test_atomic_sessions_preserve_level_scope_context_and_outcome(tmp_path: Path) -> None:
    repository = PreferenceRepository(tmp_path / "preferences.sqlite")
    refine = RefineService(repository)
    scope = AtomicScope(level="atom", id="hero-continue-button", semanticRole="primary-action")
    recorded = refine.record_preference_event(
        PreferenceEventRequest(
            sessionId="atomic-session-1",
            componentType="Button",
            scope=scope,
            context=context(),
            targetElementId="continue-button",
            action="manual_edit",
            source="manual_edit",
            beforeSpec=button_spec(),
        )
    )

    with repository._connection() as connection:
        row = connection.execute(
            "SELECT atomic_level, scope_json, context_json FROM preference_events WHERE id = ?", (recorded.id,)
        ).fetchone()
    assert row is not None
    assert row["atomic_level"] == "atom"
    assert '"id":"hero-continue-button"' in row["scope_json"]
    assert '"surface":"hero"' in row["context_json"]

    evidence = refine.preference_memory(context(), evidence=PreferenceEvidence(), scope=scope).evidence
    assert evidence[0].scope == scope
    assert evidence[0].outcome == "manual_edit"
    assert evidence[0].context == context()


def test_button_events_cannot_be_recorded_under_a_non_atom_scope() -> None:
    with pytest.raises(ValidationError, match="atom-level scope"):
        PreferenceEventRequest(
            sessionId="atomic-session-1",
            componentType="Button",
            scope=AtomicScope(level="organism", id="hero-section"),
            context=context(),
            targetElementId="continue-button",
            action="manual_edit",
            source="manual_edit",
            beforeSpec=button_spec(),
        )


def test_generation_requests_keep_their_explicit_scope_for_retrieval_and_audit(tmp_path: Path) -> None:
    class CapturingProvider:
        def __init__(self) -> None:
            self.spec_brief = None
            self.variant_brief = None

        def generate_spec(self, prompt, target, taste_brief):
            del prompt, target
            self.spec_brief = taste_brief
            return json.dumps(button_spec())

        def parse_critique(self, request, component_type):
            raise AssertionError(f"parse_critique should not run: {request}")

        def generate_candidate_patches(self, request, component_type, taste_brief, policies, repair_feedback=None):
            del request, component_type, policies, repair_feedback
            self.variant_brief = taste_brief
            return json.dumps(
                {
                    "candidates": [
                        {
                            "kind": "exploit",
                            "patch": {
                                "changes": [{"path": "/appearance/radius", "value": "square"}],
                                "rationale": "square",
                            },
                        },
                        {
                            "kind": "adjacent_explore",
                            "patch": {
                                "changes": [{"path": "/appearance/density", "value": "compact"}],
                                "rationale": "compact",
                            },
                        },
                    ]
                }
            )

    repository = PreferenceRepository(tmp_path / "preferences.sqlite")
    provider = CapturingProvider()
    refine = RefineService(repository, provider)
    scope = AtomicScope(level="atom", id="settings-save-button", semanticRole="primary-action")
    refine.record_preference_event(
        PreferenceEventRequest(
            sessionId="atomic-session-1",
            componentType="Button",
            scope=scope,
            context=context(),
            targetElementId="continue-button",
            action="rejection",
            source="absolute_feedback",
            beforeSpec=button_spec(),
            candidateId="pill-candidate",
        )
    )

    generated = refine.generate_spec(GenerateSpecRequest(sessionId="atomic-session-1", context=context(), scope=scope))
    variants = refine.generate_variants(
        GenerateVariantsRequest(
            sessionId="atomic-session-1",
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
        )
    )

    assert provider.spec_brief.scope == scope
    assert provider.variant_brief.scope == scope
    assert provider.variant_brief.decisions[0].scope == scope
    assert repository.brief_version_for_output(generated.outputId) == "itl.taste-brief/v3"
    assert repository.evidence_for_output(f"{variants.outputId}:exploit-1") == [1]

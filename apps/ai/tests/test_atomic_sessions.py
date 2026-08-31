from pathlib import Path

import pytest
from pydantic import ValidationError

from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.models import AtomicScope, DesignContext, PreferenceEventRequest, PreferenceEvidence
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


def test_atomic_sessions_persist_and_retrieve_level_scope_and_context(tmp_path: Path) -> None:
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
    assert evidence[0].context == context()

def test_button_events_cannot_be_recorded_under_a_non_atom_scope() -> None:
    with pytest.raises(ValidationError, match="atom-level scope"):
        PreferenceEventRequest(
            componentType="Button",
            scope=AtomicScope(level="organism", id="hero-section"),
            context=context(),
            targetElementId="continue-button",
            action="manual_edit",
            source="manual_edit",
            beforeSpec=button_spec(),
        )

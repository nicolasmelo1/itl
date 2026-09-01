"""The Taste Loop must run on more than one subject, at more than one level."""

from pathlib import Path

import pytest

from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.catalog import RefineValidationError, validate_ui_spec
from itl_ai.refine.models import (
    AtomicScope,
    DesignContext,
    GenerateVariantsRequest,
    Interpretation,
    ParseCritiqueRequest,
    PreferenceEventRequest,
    PreferenceEvidence,
)
from itl_ai.refine.service import RefineService

BUTTON_SCOPE = AtomicScope(level="atom", id="settings-save-button", semanticRole="primary-action")
FIELD_SCOPE = AtomicScope(level="molecule", id="settings-email-field", semanticRole="account-email")


def field_spec(gap: str = "regular") -> dict[str, object]:
    return {
        "version": "itl.ui/v1",
        "root": "email-field",
        "elements": {
            "email-field": {
                "type": "FormField",
                "props": {
                    "label": "Account email",
                    "hint": "We use this address for essential project notifications.",
                    "appearance": {"labelPlacement": "above", "gap": gap, "hintTone": "quiet"},
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


def button_spec(radius: str = "soft") -> dict[str, object]:
    return {
        "version": "itl.ui/v1",
        "root": "continue-button",
        "elements": {
            "continue-button": {
                "type": "Button",
                "props": {
                    "content": {"label": "Save changes"},
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


def settings_page_spec() -> dict[str, object]:
    elements = dict(field_spec()["elements"])  # type: ignore[arg-type]
    elements.update(button_spec()["elements"])  # type: ignore[arg-type]
    elements["account-settings"] = {
        "type": "SettingsForm",
        "props": {"title": "Account", "description": "Choose where project updates are sent."},
        "children": ["email-field", "continue-button"],
    }
    elements["settings-template"] = {
        "type": "SettingsTemplate",
        "props": {"title": "Project settings"},
        "children": ["account-settings"],
    }
    elements["project-settings-page"] = {
        "type": "ProjectSettingsPage",
        "props": {"title": "Project settings"},
        "children": ["settings-template"],
    }
    return {"version": "itl.ui/v1", "root": "project-settings-page", "elements": elements}


def context(surface: str = "form") -> DesignContext:
    return DesignContext(role="secondary-action", surface=surface, density="comfortable")


def service(tmp_path: Path) -> tuple[RefineService, PreferenceRepository]:
    repository = PreferenceRepository(tmp_path / "preferences.sqlite")
    return RefineService(repository), repository


def test_a_molecule_completes_the_same_critique_variant_and_outcome_loop(tmp_path: Path) -> None:
    refine, _ = service(tmp_path)

    interpretation = refine.parse_critique(
        ParseCritiqueRequest(
            specVersion="itl.ui/v1",
            spec=field_spec(),
            targetElementId="email-field",
            critique="Quero menos espaçamento entre rótulo e campo.",
        )
    ).interpretation
    assert {directive.kind: directive.path for directive in interpretation.directives} == {
        "keep": "/appearance/labelPlacement",
        "decrease": "/appearance/gap",
    }

    variants = refine.generate_variants(
        GenerateVariantsRequest(
            sessionId="subjects-session-1",
            specVersion="itl.ui/v1",
            spec=field_spec(),
            targetElementId="email-field",
            interpretation=interpretation,
            context=context(),
            scope=FIELD_SCOPE,
        )
    ).variants
    accepted = variants[0]
    appearance = accepted.spec["elements"]["email-field"]["props"]["appearance"]  # type: ignore[index]
    assert appearance["gap"] == "tight"
    assert appearance["labelPlacement"] == "above"

    refine.record_preference_event(
        PreferenceEventRequest(
            sessionId="subjects-session-1",
            componentType="FormField",
            scope=FIELD_SCOPE,
            context=context(),
            targetElementId="email-field",
            action="candidate_acceptance",
            source="candidate_acceptance",
            beforeSpec=field_spec(),
            afterSpec=accepted.spec,
            candidateId=accepted.id,
            evidence=interpretation.evidence,
            directives=interpretation.directives,
        )
    )

    decision = refine.taste_brief(context(), PreferenceEvidence(), FIELD_SCOPE, "FormField").decisions[0]
    assert decision.outcome == "accepted"
    assert decision.stimulus is not None
    assert decision.stimulus.componentType == "FormField"
    assert decision.stimulus.appearance["gap"] == "tight"


def test_a_subject_cannot_be_refined_under_another_levels_scope(tmp_path: Path) -> None:
    refine, _ = service(tmp_path)
    request = GenerateVariantsRequest(
        sessionId="subjects-session-1",
        specVersion="itl.ui/v1",
        spec=field_spec(),
        targetElementId="email-field",
        interpretation=Interpretation(
            targetElementId="email-field",
            evidence=PreferenceEvidence(),
            directives=[{"kind": "explore", "path": "/appearance/gap"}],
            rationale="Explore the field rhythm.",
        ),
        context=context(),
        scope=BUTTON_SCOPE,
    )

    with pytest.raises(RefineValidationError) as error:
        refine.generate_variants(request)
    assert error.value.code == "scope_mismatch"


def test_a_subject_cannot_borrow_another_subjects_vocabulary(tmp_path: Path) -> None:
    refine, _ = service(tmp_path)
    request = GenerateVariantsRequest(
        sessionId="subjects-session-1",
        specVersion="itl.ui/v1",
        spec=field_spec(),
        targetElementId="email-field",
        interpretation=Interpretation(
            targetElementId="email-field",
            evidence=PreferenceEvidence(),
            directives=[{"kind": "decrease", "path": "/appearance/radius"}],
            rationale="Radius belongs to the Button, not to the Field.",
        ),
        context=context(),
        scope=FIELD_SCOPE,
    )

    with pytest.raises(RefineValidationError) as error:
        refine.generate_variants(request)
    assert error.value.code == "unsupported_path"


def test_atom_and_molecule_evidence_never_enter_each_others_retrieval(tmp_path: Path) -> None:
    refine, _ = service(tmp_path)
    button_event = refine.record_preference_event(
        PreferenceEventRequest(
            sessionId="subjects-session-1",
            componentType="Button",
            scope=BUTTON_SCOPE,
            context=context(),
            targetElementId="continue-button",
            action="candidate_acceptance",
            source="candidate_acceptance",
            beforeSpec=button_spec("square"),
            candidateId="accepted-square",
        )
    )
    field_event = refine.record_preference_event(
        PreferenceEventRequest(
            sessionId="subjects-session-1",
            componentType="FormField",
            scope=FIELD_SCOPE,
            context=context(),
            targetElementId="email-field",
            action="rejection",
            source="absolute_feedback",
            beforeSpec=field_spec("loose"),
            candidateId="rejected-loose",
        )
    )

    button_memory = refine.preference_memory(context(), PreferenceEvidence(), BUTTON_SCOPE, "Button").evidence
    field_memory = refine.preference_memory(context(), PreferenceEvidence(), FIELD_SCOPE, "FormField").evidence

    assert [item.id for item in button_memory] == [button_event.id]
    assert [item.id for item in field_memory] == [field_event.id]
    assert field_memory[0].outcome == "rejected"
    assert field_memory[0].observedAppearance is not None
    assert field_memory[0].observedAppearance.appearance["gap"] == "loose"


def test_the_registered_settings_composition_validates_on_the_api_side() -> None:
    validated = validate_ui_spec(settings_page_spec())
    assert validated["root"] == "project-settings-page"

    inverted = settings_page_spec()
    inverted["elements"]["email-field"]["children"] = ["account-settings"]  # type: ignore[index]
    with pytest.raises(RefineValidationError) as error:
        validate_ui_spec(inverted)
    assert error.value.code == "invalid_spec"

"""Taste lives in one shared space, and each component declares its part of it.

A component that owned its own appearance vocabulary could teach nothing to any
other component, and every new component needed a hand-written ontology. Here a
component is a stimulus with a capability manifest instead.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import itl_ai.main as main
from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.dimensions import (
    CONTRACT_PATH,
    DIMENSION_SPACE_VERSION,
    TASTE_DIMENSIONS,
    ManifestError,
    capabilities_for,
    dimensions_for,
    validate_capability_manifests,
)
from itl_ai.refine.models import (
    EDITABLE_COMPONENTS,
    AtomicScope,
    CandidateChange,
    DesignContext,
    MemoryResponse,
    PreferenceEventRequest,
    PreferenceEvidence,
    ProjectContext,
)
from itl_ai.refine.service import RefineService

SCOPE = AtomicScope(level="atom", id="hero-continue-button", semanticRole="primary-action")
PROJECT = ProjectContext(productKind="saas", visualTone=["serious"], platform="web")
client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_preference_memory(tmp_path: Path) -> None:
    """Never let a proof write into the corpus it is reasoning about."""
    main.refine_service = RefineService(PreferenceRepository(tmp_path / "preferences.sqlite"))


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
                        "size": "compact",
                        "radius": radius,
                        "density": "compact",
                        "fontWeight": "regular",
                    },
                },
                "children": [],
            }
        },
    }


def context() -> DesignContext:
    return DesignContext(role="primary-action", surface="hero", density="comfortable")


def test_every_editable_component_declares_capabilities_that_cover_its_vocabulary() -> None:
    for component, entry in EDITABLE_COMPONENTS.items():
        capabilities = capabilities_for(component)
        assert capabilities, f"{component} declares no taste capabilities."
        assert {capability.token for capability in capabilities} == set(entry.vocabulary)
        for capability in capabilities:
            assert capability.dimension in TASTE_DIMENSIONS
            assert set(capability.projection) == set(entry.vocabulary[capability.token])
            assert all(0.0 <= point <= 1.0 for point in capability.projection.values())


def test_the_dimension_space_is_shared_rather_than_owned_by_one_component() -> None:
    """Two components at two levels reach the same point through different tokens."""
    shared = dimensions_for("Button").intersection(dimensions_for("FormField"))
    assert "emphasis.contrast" in shared

    button = capabilities_for("Button")
    field = capabilities_for("FormField")
    contrast = {capability.dimension: capability for capability in button + field if capability.dimension in shared}
    assert contrast["emphasis.contrast"].token in {"recipe", "hintTone"}
    # The tokens differ; the scale they land on does not.
    button_contrast = next(item for item in button if item.dimension == "emphasis.contrast")
    field_contrast = next(item for item in field if item.dimension == "emphasis.contrast")
    assert button_contrast.token != field_contrast.token
    assert button_contrast.coordinate("ghost") == field_contrast.coordinate("quiet") == 0.0


def test_the_published_manifest_matches_the_versioned_contract() -> None:
    contract = json.loads(Path(CONTRACT_PATH).read_text())
    response = client.get("/v1/taste/dimensions")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dimensionSpaceVersion"] == DIMENSION_SPACE_VERSION == contract["version"]
    assert sorted(payload["dimensions"]) == sorted(TASTE_DIMENSIONS)
    published = {component["componentType"]: component for component in payload["components"]}
    assert set(published) == set(EDITABLE_COMPONENTS)
    for component, declared in contract["components"].items():
        capabilities = {item["dimension"]: item for item in published[component]["capabilities"]}
        assert set(capabilities) == set(declared)
        for dimension, projection in declared.items():
            assert capabilities[dimension]["token"] == projection["token"]
            assert capabilities[dimension]["values"] == projection["values"]


def one_accepted_square_button(tmp_path: Path) -> tuple[int, MemoryResponse]:
    """Accept one compact, square, regular-weight Button, then read memory back."""
    refine = RefineService(PreferenceRepository(tmp_path / "preferences.sqlite"))
    recorded = refine.record_preference_event(
        PreferenceEventRequest(
            sessionId="dimension-session-1",
            componentType="Button",
            scope=SCOPE,
            context=context(),
            projectContext=PROJECT,
            targetElementId="continue-button",
            action="candidate_acceptance",
            source="candidate_acceptance",
            beforeSpec=button_spec(),
            candidateId="accepted-square",
            evidence=PreferenceEvidence(strength="strong"),
        )
    )
    return recorded.id, refine.preference_memory(context(), PreferenceEvidence(), SCOPE, "Button", PROJECT)


def test_one_judgment_records_evidence_on_every_shared_dimension_it_expressed(tmp_path: Path) -> None:
    event_id, memory = one_accepted_square_button(tmp_path)
    readings = {item.dimension: item for item in memory.dimensions}

    assert memory.dimensionSpaceVersion == DIMENSION_SPACE_VERSION
    # One accepted stimulus is evidence on several dimensions at once.
    assert readings["shape.radius"].coordinate == 0.0
    assert readings["shape.radius"].nearestValue == "square"
    assert readings["density.padding"].coordinate == 0.0
    assert readings["emphasis.weight"].coordinate == 0.0
    # A compiled preference that cannot name its evidence does not ship.
    assert readings["shape.radius"].eventIds == [event_id]


def test_the_same_judgment_also_records_a_component_scoped_residual(tmp_path: Path) -> None:
    event_id, memory = one_accepted_square_button(tmp_path)
    residual = {item.dimension: item for item in memory.dimensions}["shape.radius"].residual

    assert residual is not None
    assert residual.componentType == "Button"
    assert residual.eventIds == [event_id]
    # One judgment on one component cannot yet be an exception to anything.
    assert residual.delta == 0.0
    assert residual.isException is False


def test_a_manifest_that_disagrees_with_the_component_registry_fails_closed() -> None:
    with pytest.raises(ManifestError):
        validate_capability_manifests({"Button": {"radius": ("square", "soft")}}, {})
    with pytest.raises(ManifestError):
        validate_capability_manifests({"Slider": {"track": ("thin", "thick")}}, {})


def test_a_normalized_coordinate_is_never_a_value_a_model_may_emit() -> None:
    """Coordinates are an internal representation, not a widened vocabulary."""
    change = CandidateChange(path="/appearance/radius", value="0.5")
    response = client.post(
        "/v1/refine/generate-variants",
        json={
            "sessionId": "dimension-session-1",
            "specVersion": "itl.ui/v1",
            "spec": button_spec(),
            "targetElementId": "continue-button",
            "interpretation": {
                "targetElementId": "continue-button",
                "evidence": {"likedPaths": [], "dislikedPaths": [], "lockedPaths": [], "strength": "weak"},
                "directives": [{"kind": "set", "path": change.path, "value": change.value}],
                "ambiguity": [],
                "rationale": "A coordinate is not a catalog value.",
            },
            "context": context().model_dump(),
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_value"

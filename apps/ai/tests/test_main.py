import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import itl_ai.main as main
from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.catalog import visual_values
from itl_ai.refine.providers import ProviderUnavailableError
from itl_ai.refine.service import RefineService

client = TestClient(main.app)
context = {"role": "primary-action", "surface": "hero", "density": "comfortable"}


@pytest.fixture(autouse=True)
def isolated_preference_memory(tmp_path) -> None:
    main.refine_service = RefineService(PreferenceRepository(tmp_path / "preferences.sqlite"))


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


def interpretation() -> dict[str, object]:
    return {
        "targetElementId": "continue-button",
        "evidence": {
            "likedPaths": ["/appearance/recipe"],
            "dislikedPaths": ["/appearance/radius"],
            "lockedPaths": ["/appearance/recipe"],
            "strength": "moderate",
        },
        "directives": [
            {"kind": "keep", "path": "/appearance/recipe"},
            {"kind": "decrease", "path": "/appearance/radius"},
        ],
        "ambiguity": [],
        "rationale": "Keep the recipe and decrease radius.",
    }


def test_refine_critique_yields_reviewable_contextual_interpretation() -> None:
    response = client.post(
        "/v1/refine/parse-critique",
        json={
            "specVersion": "itl.ui/v1",
            "spec": button_spec(),
            "targetElementId": "continue-button",
            "critique": "Too rounded.",
        },
    )
    assert response.status_code == 200
    result = response.json()["interpretation"]
    assert result["directives"] == [{"kind": "decrease", "path": "/appearance/radius"}]


def test_button_catalog_manifest_matches_the_python_visual_vocabulary() -> None:
    catalog = json.loads((Path(__file__).parents[3] / "contracts/catalog/button.v1.json").read_text())
    assert {key: tuple(values) for key, values in catalog["appearance"].items()} == visual_values("Button")


def test_button_directives_preserve_direction_and_recipes_are_coherent() -> None:
    response = client.post(
        "/v1/refine/generate-variants",
        json={
            "specVersion": "itl.ui/v1",
            "spec": button_spec(),
            "targetElementId": "continue-button",
            "interpretation": interpretation(),
            "includeWild": True,
            "context": context,
        },
    )
    assert response.status_code == 200
    variants = response.json()["variants"]
    for variant in variants:
        appearance = variant["spec"]["elements"]["continue-button"]["props"]["appearance"]
        assert appearance["radius"] == "square"
        assert appearance["recipe"] == "primary" or variant["kind"] == "wild_explore"
        assert set(appearance) == {"recipe", "size", "radius", "density", "fontWeight"}


def test_button_taste_space_rejects_state_and_content_paths() -> None:
    invalid = interpretation()
    invalid["directives"] = [{"kind": "explore", "path": "/semantic/state"}]
    response = client.post(
        "/v1/refine/generate-variants",
        json={
            "specVersion": "itl.ui/v1",
            "spec": button_spec(),
            "targetElementId": "continue-button",
            "interpretation": invalid,
            "context": context,
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_candidate_acceptance_keeps_candidate_identity_separate_from_element_identity() -> None:
    response = client.post(
        "/v1/preference-events",
        json={
            "context": context,
            "targetElementId": "continue-button",
            "selectedElementId": "continue-button",
            "candidateId": "exploit-1",
            "action": "candidate_acceptance",
            "source": "candidate_acceptance",
            "beforeSpec": button_spec(),
            "afterSpec": button_spec(radius="square"),
        },
    )
    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_provider_timeout_returns_unavailable_for_candidates_but_keeps_parse_fallback(tmp_path) -> None:
    class UnavailableProvider:
        def generate_spec(self, prompt: str, target: str, taste_brief) -> str:
            del taste_brief
            raise ProviderUnavailableError("timed out")

        def parse_critique(self, request, component_type) -> str:
            raise ProviderUnavailableError("timed out")

        def generate_candidate_patches(
            self, request, component_type, taste_brief, policies, repair_feedback=None
        ) -> str:
            del taste_brief
            raise ProviderUnavailableError("timed out")

    main.refine_service = RefineService(PreferenceRepository(tmp_path / "preferences.sqlite"), UnavailableProvider())
    parse_response = client.post(
        "/v1/refine/parse-critique",
        json={
            "specVersion": "itl.ui/v1",
            "spec": button_spec(),
            "targetElementId": "continue-button",
            "critique": "Too rounded.",
        },
    )
    variants_response = client.post(
        "/v1/refine/generate-variants",
        json={
            "specVersion": "itl.ui/v1",
            "spec": button_spec(),
            "targetElementId": "continue-button",
            "interpretation": interpretation(),
            "context": context,
        },
    )

    assert parse_response.status_code == 200
    assert parse_response.json()["interpretation"]["directives"]
    assert variants_response.status_code == 503
    assert variants_response.json()["code"] == "provider_unavailable"


def test_parse_critique_accepts_a_provider_interpretation_wrapper(tmp_path) -> None:
    class WrappedInterpretationProvider:
        def parse_critique(self, request, component_type) -> str:
            return json.dumps({"interpretation": interpretation()})

        def generate_candidate_patches(
            self, request, component_type, taste_brief, policies, repair_feedback=None
        ) -> None:
            del taste_brief
            return None

    main.refine_service = RefineService(
        PreferenceRepository(tmp_path / "preferences.sqlite"), WrappedInterpretationProvider()
    )
    response = client.post(
        "/v1/refine/parse-critique",
        json={
            "specVersion": "itl.ui/v1",
            "spec": button_spec(),
            "targetElementId": "continue-button",
            "critique": "Too rounded.",
        },
    )

    assert response.status_code == 200
    assert response.json()["interpretation"]["targetElementId"] == "continue-button"

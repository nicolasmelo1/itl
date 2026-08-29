import pytest
from fastapi.testclient import TestClient

import itl_ai.main as main
from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.service import RefineService

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_preference_memory(tmp_path) -> None:
    main.refine_service = RefineService(PreferenceRepository(tmp_path / "preferences.sqlite"))


def test_health_is_available_without_provider_credentials(monkeypatch) -> None:
    monkeypatch.delenv("GENERATION_PROVIDER_API_KEY", raising=False)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_generation_without_credentials_returns_a_safe_configuration_error(
    monkeypatch,
) -> None:
    monkeypatch.delenv("GENERATION_PROVIDER_API_KEY", raising=False)

    response = client.post("/v1/generate", json={"prompt": "Make a card"})

    assert response.status_code == 503
    assert response.json()["code"] == "provider_not_configured"


def test_invalid_generation_request_returns_a_typed_error() -> None:
    response = client.post("/v1/generate", json={"prompt": ""})

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def button_spec() -> dict[str, object]:
    return {
        "version": "itl.ui/v1",
        "root": "continue-button",
        "elements": {
            "continue-button": {
                "type": "Button",
                "props": {
                    "label": "Continue",
                    "variant": "solid",
                    "size": "regular",
                    "radius": "soft",
                    "density": "comfortable",
                    "background": "accent",
                    "foreground": "light",
                    "border": "none",
                    "fontWeight": "semibold",
                    "state": "default",
                },
                "children": [],
            }
        },
    }


def critique_payload(critique: str) -> dict[str, object]:
    return {
        "specVersion": "itl.ui/v1",
        "spec": button_spec(),
        "targetElementId": "continue-button",
        "critique": critique,
    }


def test_refine_critique_yields_reviewable_patch_intent() -> None:
    response = client.post(
        "/v1/refine/parse-critique",
        json=critique_payload("Gosto da cor e do espaçamento, mas está arredondado demais."),
    )

    assert response.status_code == 200
    intent = response.json()["intent"]
    assert intent["lockedPaths"] == ["/props/background", "/props/density"]
    assert intent["explorationPaths"] == ["/props/radius"]


def test_refine_locks_are_preserved_and_explored_values_are_valid() -> None:
    intent = {
        "targetElementId": "continue-button",
        "likedPaths": ["/props/background", "/props/density"],
        "dislikedPaths": ["/props/radius"],
        "lockedPaths": ["/props/background", "/props/density"],
        "explorationPaths": ["/props/radius"],
        "ambiguity": [],
        "rationale": "Keep color and spacing; explore radius.",
    }
    response = client.post(
        "/v1/refine/generate-variants",
        json={
            "specVersion": "itl.ui/v1",
            "spec": button_spec(),
            "targetElementId": "continue-button",
            "intent": intent,
            "includeWild": True,
        },
    )

    assert response.status_code == 200
    variants = response.json()["variants"]
    assert [variant["kind"] for variant in variants] == ["exploit", "adjacent_explore", "wild_explore"]
    for variant in variants:
        props = variant["spec"]["elements"]["continue-button"]["props"]
        assert props["background"] == "accent"
        assert props["density"] == "comfortable"
        assert props["radius"] in {"square", "pill"}


def test_refine_conflicting_locks_and_unknown_paths_fail_closed() -> None:
    intent = {
        "targetElementId": "continue-button",
        "likedPaths": [],
        "dislikedPaths": [],
        "lockedPaths": ["/props/radius"],
        "explorationPaths": ["/props/radius"],
        "ambiguity": [],
        "rationale": "Contradictory fixture.",
    }
    response = client.post(
        "/v1/refine/generate-variants",
        json={
            "specVersion": "itl.ui/v1",
            "spec": button_spec(),
            "targetElementId": "continue-button",
            "intent": intent,
        },
    )
    unknown_path = client.post("/v1/refine/parse-critique", json=critique_payload("__unknown_path__"))

    assert response.status_code == 422
    assert response.json()["code"] == "conflicting_paths"
    assert unknown_path.status_code == 422
    assert unknown_path.json()["code"] == "unsupported_path"


def test_refine_invalid_model_output_preserves_current_spec() -> None:
    original = button_spec()
    response = client.post("/v1/refine/parse-critique", json=critique_payload("__malformed_model_output__"))

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_model_output"
    assert button_spec() == original

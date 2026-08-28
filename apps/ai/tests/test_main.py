from fastapi.testclient import TestClient

from itl_ai.main import app

client = TestClient(app)


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

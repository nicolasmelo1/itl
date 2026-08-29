# DSPy does not publish pyright stubs; the optional live-provider boundary is isolated here.
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Provider adapter: deterministic fixtures locally, DSPy signatures for models."""

import json
import unicodedata
from typing import Protocol
from urllib.parse import urlparse

import httpx

from itl_ai.config.settings import Settings
from itl_ai.refine.models import ParseCritiqueRequest


def _dspy_operations() -> tuple[object, type[object], type[object], type[object]]:
    """Declare the three typed DSPy operations only when a live provider is enabled."""
    import dspy  # type: ignore[import-untyped]  # DSPy does not publish pyright stubs.

    class GenerateSpec(dspy.Signature):  # type: ignore[misc]
        """Produce one schema-valid, catalog-constrained Button UI spec as JSON."""

        prompt: str = dspy.InputField()
        spec_json: str = dspy.OutputField(desc="A complete JSON UI spec and nothing else.")

    class ParseCritique(dspy.Signature):  # type: ignore[misc]
        """Interpret critique into reviewable Button patch intent JSON, never CSS."""

        spec_json: str = dspy.InputField()
        target_element_id: str = dspy.InputField()
        critique: str = dspy.InputField()
        patch_intent_json: str = dspy.OutputField(desc="A JSON PatchIntent object and nothing else.")

    class GenerateVariants(dspy.Signature):  # type: ignore[misc]
        """Suggest constrained Button variants as JSON; deterministic validation is mandatory."""

        spec_json: str = dspy.InputField()
        patch_intent_json: str = dspy.InputField()
        variants_json: str = dspy.OutputField(desc="A JSON object containing variants and nothing else.")

    return dspy, GenerateSpec, ParseCritique, GenerateVariants


class RefineProvider(Protocol):
    def generate_spec(self, prompt: str) -> str: ...

    def parse_critique(self, request: ParseCritiqueRequest) -> str: ...


class DeterministicRefineProvider:
    """Fixture-backed provider used by tests and local development without credentials."""

    def generate_spec(self, prompt: str) -> str:
        return json.dumps(
            {
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
        )

    def parse_critique(self, request: ParseCritiqueRequest) -> str:
        normalized = unicodedata.normalize("NFKD", request.critique).encode("ascii", "ignore").decode().lower()
        if "__malformed_model_output__" in normalized:
            return "this is not JSON"
        if "__unknown_path__" in normalized:
            return json.dumps(
                {
                    "targetElementId": request.targetElementId,
                    "likedPaths": ["/props/magic"],
                    "dislikedPaths": [],
                    "lockedPaths": ["/props/magic"],
                    "explorationPaths": ["/props/radius"],
                    "ambiguity": [],
                    "rationale": "Fixture invalid path.",
                }
            )
        liked: list[str] = []
        disliked: list[str] = []
        terms = (
            ("cor", "/props/background"), ("color", "/props/background"), ("fundo", "/props/background"),
            ("espac", "/props/density"), ("spacing", "/props/density"), ("dens", "/props/density"),
            ("arredond", "/props/radius"), ("radius", "/props/radius"), ("round", "/props/radius"),
            ("borda", "/props/border"), ("contorno", "/props/border"), ("peso", "/props/fontWeight"),
            ("negrito", "/props/fontWeight"),
        )
        for term, path in terms:
            if term not in normalized:
                continue
            negative = any(
                phrase in normalized
                for phrase in (
                    f"nao gosto da {term}",
                    f"nao gosto do {term}",
                    f"menos {term}",
                    f"{term} demais",
                    f"mudar {term}",
                )
            ) or (
                path == "/props/radius"
                and any(
                    phrase in normalized
                    for phrase in ("arredondado demais", "muito arredondado", "too rounded")
                )
            )
            (disliked if negative else liked).append(path)
        liked = list(dict.fromkeys(liked))
        disliked = list(dict.fromkeys(disliked))
        ambiguity = [] if liked or disliked else ["No supported Button token was identified. Choose tokens manually."]
        return json.dumps(
            {
                "targetElementId": request.targetElementId,
                "likedPaths": liked,
                "dislikedPaths": disliked,
                "lockedPaths": liked,
                "explorationPaths": disliked,
                "ambiguity": ambiguity,
                "rationale": (
                    "Explicitly liked tokens are proposed as locks; "
                    "disliked tokens are proposed for bounded exploration."
                ),
            }
        )


class OpenAICompatibleRefineProvider:
    """Minimal JSON-only adapter for Ollama Cloud or the OpenAI API."""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("A remote model provider must use an absolute HTTPS URL.")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def generate_spec(self, prompt: str) -> str:
        return self._complete(
            "Return exactly one JSON UI spec for a Button from the supplied request. No markdown.",
            prompt,
        )

    def parse_critique(self, request: ParseCritiqueRequest) -> str:
        return self._complete(
            "Return exactly one JSON PatchIntent. Only use documented /props Button paths; no markdown.",
            json.dumps(
                {
                    "spec": request.spec,
                    "targetElementId": request.targetElementId,
                    "critique": request.critique,
                }
            ),
        )

    def _complete(self, instructions: str, input_text: str) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": input_text},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,
            }
        ).encode()
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                content=body,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                timeout=45,
            )
            response.raise_for_status()
            decoded = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError("The configured model provider could not complete the request.") from exc
        content = decoded.get("choices", [{}])[0].get("message", {}).get("content")
        if not isinstance(content, str):
            raise RuntimeError("The configured model provider returned no text completion.")
        return content


def configured_provider(settings: Settings) -> RefineProvider:
    """Choose an opt-in remote provider; deterministic fixtures stay the safe default."""
    if settings.llm_provider == "ollama" and settings.ollama_api_key:
        return OpenAICompatibleRefineProvider(settings.ollama_base_url, settings.ollama_api_key, settings.ollama_model)
    if settings.llm_provider == "openai" and settings.openai_api_key:
        return OpenAICompatibleRefineProvider(
            "https://api.openai.com/v1", settings.openai_api_key, settings.openai_model
        )
    return DeterministicRefineProvider()


class DSPyRefineProvider:
    """Thin adapter for a configured DSPy runtime. Output remains untrusted JSON."""

    def __init__(self) -> None:
        dspy, generate_spec, parse_critique, _ = _dspy_operations()
        self._generate_spec = dspy.Predict(generate_spec)  # type: ignore[union-attr]
        self._parse_critique = dspy.Predict(parse_critique)  # type: ignore[union-attr]

    def generate_spec(self, prompt: str) -> str:
        return str(self._generate_spec(prompt=prompt).spec_json)

    def parse_critique(self, request: ParseCritiqueRequest) -> str:
        completion = self._parse_critique(
            spec_json=json.dumps(request.spec), target_element_id=request.targetElementId, critique=request.critique
        )
        return str(completion.patch_intent_json)

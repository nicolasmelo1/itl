# DSPy does not publish pyright stubs; the optional live-provider boundary is isolated here.
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Provider adapter: direct live JSON calls plus optional DSPy experiments."""

import json
import unicodedata
from typing import Protocol
from urllib.parse import urlparse

import httpx

from itl_ai.config.settings import Settings
from itl_ai.refine.catalog import VISUAL_VALUES
from itl_ai.refine.models import GenerateVariantsRequest, ParseCritiqueRequest, RetrievedEvidence

CRITIQUE_TERMS = (
    ("cor", "/appearance/recipe"),
    ("color", "/appearance/recipe"),
    ("fundo", "/appearance/recipe"),
    ("espac", "/appearance/density"),
    ("spacing", "/appearance/density"),
    ("dens", "/appearance/density"),
    ("arredond", "/appearance/radius"),
    ("radius", "/appearance/radius"),
    ("round", "/appearance/radius"),
    ("peso", "/appearance/fontWeight"),
    ("negrito", "/appearance/fontWeight"),
)


class ProviderUnavailableError(RuntimeError):
    """A configured remote provider failed without producing a usable completion."""


def _dspy_operations() -> tuple[object, type[object], type[object], type[object]]:
    """Declare optional DSPy operations without making them the live runtime path."""
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

    class GenerateCandidatePatches(dspy.Signature):  # type: ignore[misc]
        """Propose catalog-constrained Button patches; never mutate a UI spec directly."""

        current_spec_json: str = dspy.InputField()
        interpretation_json: str = dspy.InputField()
        context_json: str = dspy.InputField()
        taste_evidence_json: str = dspy.InputField()
        catalog_json: str = dspy.InputField()
        policies_json: str = dspy.InputField()
        repair_feedback: str = dspy.InputField()
        candidate_patches_json: str = dspy.OutputField(
            desc="A JSON object with candidate patches, policy labels, and rationales only."
        )

    return dspy, GenerateSpec, ParseCritique, GenerateCandidatePatches


class RefineProvider(Protocol):
    def generate_spec(self, prompt: str) -> str: ...

    def parse_critique(self, request: ParseCritiqueRequest) -> str: ...

    def generate_candidate_patches(
        self,
        request: GenerateVariantsRequest,
        evidence: list[RetrievedEvidence],
        policies: list[str],
        repair_feedback: str | None = None,
    ) -> str | None: ...


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
        )

    def parse_critique(self, request: ParseCritiqueRequest) -> str:
        normalized = _normalise_critique(request.critique)
        if "__malformed_model_output__" in normalized:
            return "this is not JSON"
        if "__unknown_path__" in normalized:
            return _invalid_path_fixture(request.targetElementId)
        return _interpretation_json(request.targetElementId, normalized)

    def generate_candidate_patches(
        self,
        request: GenerateVariantsRequest,
        evidence: list[RetrievedEvidence],
        policies: list[str],
        repair_feedback: str | None = None,
    ) -> str:
        """Return static fixture patches only; real candidate search requires a model provider."""
        del request, evidence, repair_feedback
        fixture_patches = {
            "exploit": {
                "changes": [{"path": "/appearance/radius", "value": "square"}],
                "rationale": "Fixture: reduce the visual roundness.",
            },
            "adjacent_explore": {
                "changes": [
                    {"path": "/appearance/radius", "value": "square"},
                    {"path": "/appearance/density", "value": "compact"},
                ],
                "rationale": "Fixture: explore a nearby denser treatment.",
            },
            "wild_explore": {
                "changes": [
                    {"path": "/appearance/radius", "value": "square"},
                    {"path": "/appearance/fontWeight", "value": "regular"},
                ],
                "rationale": "Fixture: explore a clearly different emphasis treatment.",
            },
        }
        return json.dumps({"candidates": [{"kind": policy, "patch": fixture_patches[policy]} for policy in policies]})


def _normalise_critique(critique: str) -> str:
    return unicodedata.normalize("NFKD", critique).encode("ascii", "ignore").decode().lower()


def _invalid_path_fixture(target_element_id: str) -> str:
    return json.dumps(
        {
            "targetElementId": target_element_id,
            "evidence": {"likedPaths": ["/appearance/magic"], "dislikedPaths": [], "lockedPaths": []},
            "directives": [{"kind": "decrease", "path": "/appearance/radius"}],
            "ambiguity": [],
            "rationale": "Fixture invalid path.",
        }
    )


def _interpretation_json(target_element_id: str, critique: str) -> str:
    liked, disliked = _evidence_paths(critique)
    directives = [
        *[{"kind": "keep", "path": path} for path in liked],
        *[_directive_for_dislike(path) for path in disliked],
    ]
    ambiguity = [] if liked or disliked else ["No supported Button token was identified. Choose tokens manually."]
    if not directives:
        directives = [{"kind": "explore", "path": "/appearance/recipe"}]
    return json.dumps(
        {
            "targetElementId": target_element_id,
            "evidence": {
                "likedPaths": liked,
                "dislikedPaths": disliked,
                "lockedPaths": liked,
                "strength": "moderate",
            },
            "directives": directives,
            "ambiguity": ambiguity,
            "rationale": (
                "Explicitly liked visual attributes are kept; directional critique becomes a visual directive."
            ),
        }
    )


def _evidence_paths(critique: str) -> tuple[list[str], list[str]]:
    liked: list[str] = []
    disliked: list[str] = []
    for term, path in CRITIQUE_TERMS:
        if term in critique:
            (disliked if _is_negative(term, path, critique) else liked).append(path)
    return list(dict.fromkeys(liked)), list(dict.fromkeys(disliked))


def _is_negative(term: str, path: str, critique: str) -> bool:
    ordinary_negative = any(
        phrase in critique
        for phrase in (
            f"nao gosto da {term}",
            f"nao gosto do {term}",
            f"menos {term}",
            f"{term} demais",
            f"mudar {term}",
        )
    )
    radius_negative = path == "/appearance/radius" and any(
        phrase in critique for phrase in ("arredondado demais", "muito arredondado", "too rounded")
    )
    return ordinary_negative or radius_negative


def _directive_for_dislike(path: str) -> dict[str, str]:
    return {"kind": "decrease" if path == "/appearance/radius" else "explore", "path": path}


class OpenAICompatibleRefineProvider:
    """Minimal JSON-only adapter for Ollama Cloud or the OpenAI API."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout_seconds: float = 120) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("A remote model provider must use an absolute HTTPS URL.")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate_spec(self, prompt: str) -> str:
        return self._complete(
            "Return exactly one JSON UI spec for a Button from the supplied request. No markdown.",
            prompt,
        )

    def parse_critique(self, request: ParseCritiqueRequest) -> str:
        return self._complete(
            (
                "Return exactly one JSON object and no markdown. It must have exactly these fields: "
                "targetElementId (copy the supplied ID), evidence ({likedPaths:string[], dislikedPaths:string[], "
                "lockedPaths:string[], strength:weak|moderate|strong}), directives (non-empty array of objects with "
                "kind and path), ambiguity (string[]), and rationale (non-empty string). "
                "Use only /appearance/recipe, /appearance/size, /appearance/radius, /appearance/density, or "
                "/appearance/fontWeight as paths. Valid directive kinds are keep, avoid, prefer, set, increase, "
                "decrease, and explore. Do not wrap the object in an interpretation field."
            ),
            json.dumps(
                {
                    "spec": request.spec,
                    "targetElementId": request.targetElementId,
                    "critique": request.critique,
                }
            ),
        )

    def generate_candidate_patches(
        self,
        request: GenerateVariantsRequest,
        evidence: list[RetrievedEvidence],
        policies: list[str],
        repair_feedback: str | None = None,
    ) -> str:
        return self._complete(
            (
                "Return exactly one JSON object with a candidates array and no markdown. Do not return UI specs, "
                "CSS, or arbitrary values. Each candidate is {kind, patch:{changes:[{path,value}],rationale}}. "
                "A patch can modify only the supplied Button appearance catalog paths. The engine applies it to the "
                "current spec, so content and semantic state are inherently untouched. Generate exactly one distinct "
                "candidate for every requested kind. Treat interpretation directives as hard constraints: keep is "
                "immutable; set and prefer require their value; avoid must change the current value; increase and "
                "decrease must move in the requested catalog direction. Use these strategies: exploit = strongest "
                "candidate from matching taste evidence with the minimum coherent changes; adjacent_explore = a "
                "coherent, nearby direction that explores one or two uncertain visual dimensions; wild_explore = a "
                "coherent direction meaningfully different from known preferences while respecting hard constraints. "
                f"The required kinds, in order, are {policies}."
            ),
            json.dumps(
                {
                    "currentSpec": request.spec,
                    "interpretation": request.interpretation.model_dump(),
                    "context": request.context.model_dump(),
                    "retrievedEvidence": [item.model_dump() for item in evidence],
                    "catalog": VISUAL_VALUES,
                    "repairFeedback": repair_feedback,
                }
            ),
            temperature=0.7,
        )

    def _complete(self, instructions: str, input_text: str, temperature: float = 0) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": input_text},
                ],
                "response_format": {"type": "json_object"},
                "temperature": temperature,
            }
        ).encode()
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                content=body,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            decoded = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailableError("The configured model provider could not complete the request.") from exc
        content = decoded.get("choices", [{}])[0].get("message", {}).get("content")
        if not isinstance(content, str):
            raise ProviderUnavailableError("The configured model provider returned no text completion.")
        return content


def configured_provider(settings: Settings) -> RefineProvider:
    """Choose an opt-in remote provider; deterministic fixtures stay the safe default."""
    if settings.llm_provider == "ollama" and settings.ollama_api_key:
        return OpenAICompatibleRefineProvider(
            settings.ollama_base_url,
            settings.ollama_api_key,
            settings.ollama_model,
            settings.model_timeout_seconds,
        )
    if settings.llm_provider == "openai" and settings.openai_api_key:
        return OpenAICompatibleRefineProvider(
            "https://api.openai.com/v1", settings.openai_api_key, settings.openai_model, settings.model_timeout_seconds
        )
    return DeterministicRefineProvider()


class DSPyRefineProvider:
    """Thin adapter for a configured DSPy runtime. Output remains untrusted JSON."""

    def __init__(self) -> None:
        dspy, generate_spec, parse_critique, generate_candidate_patches = _dspy_operations()
        self._generate_spec = dspy.Predict(generate_spec)  # type: ignore[union-attr]
        self._parse_critique = dspy.Predict(parse_critique)  # type: ignore[union-attr]
        self._generate_candidate_patches = dspy.Predict(generate_candidate_patches)  # type: ignore[union-attr]

    def generate_spec(self, prompt: str) -> str:
        return str(self._generate_spec(prompt=prompt).spec_json)

    def parse_critique(self, request: ParseCritiqueRequest) -> str:
        completion = self._parse_critique(
            spec_json=json.dumps(request.spec), target_element_id=request.targetElementId, critique=request.critique
        )
        return str(completion.patch_intent_json)

    def generate_candidate_patches(
        self,
        request: GenerateVariantsRequest,
        evidence: list[RetrievedEvidence],
        policies: list[str],
        repair_feedback: str | None = None,
    ) -> str:
        completion = self._generate_candidate_patches(
            current_spec_json=json.dumps(request.spec),
            interpretation_json=request.interpretation.model_dump_json(),
            context_json=request.context.model_dump_json(),
            taste_evidence_json=json.dumps([item.model_dump() for item in evidence]),
            catalog_json=json.dumps(VISUAL_VALUES),
            policies_json=json.dumps(policies),
            repair_feedback=repair_feedback or "",
        )
        return str(completion.candidate_patches_json)

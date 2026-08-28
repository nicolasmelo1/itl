# pyright: reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownMemberType=false
"""Provider adapter: deterministic fixtures locally, DSPy signatures for models."""

import json
import unicodedata
from typing import Protocol

import dspy

from itl_ai.refine.models import ParseCritiqueRequest


class GenerateSpec(dspy.Signature):
    """Produce one schema-valid, catalog-constrained Button UI spec as JSON."""

    prompt: str = dspy.InputField()
    spec_json: str = dspy.OutputField(desc="A complete JSON UI spec and nothing else.")


class ParseCritique(dspy.Signature):
    """Interpret critique into reviewable Button patch intent JSON, never CSS."""

    spec_json: str = dspy.InputField()
    target_element_id: str = dspy.InputField()
    critique: str = dspy.InputField()
    patch_intent_json: str = dspy.OutputField(desc="A JSON PatchIntent object and nothing else.")


class GenerateVariants(dspy.Signature):
    """Suggest constrained Button variants as JSON; deterministic validation is mandatory."""

    spec_json: str = dspy.InputField()
    patch_intent_json: str = dspy.InputField()
    variants_json: str = dspy.OutputField(desc="A JSON object containing variants and nothing else.")


class RefineProvider(Protocol):
    def generate_spec(self, prompt: str) -> str: ...

    def parse_critique(self, request: ParseCritiqueRequest) -> str: ...


class DeterministicRefineProvider:
    """Fixture-backed provider used by tests and local development without credentials."""

    def generate_spec(self, _: str) -> str:
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
            ("cor", "/props/background"),
            ("color", "/props/background"),
            ("fundo", "/props/background"),
            ("espac", "/props/density"),
            ("spacing", "/props/density"),
            ("dens", "/props/density"),
            ("arredond", "/props/radius"),
            ("radius", "/props/radius"),
            ("round", "/props/radius"),
            ("borda", "/props/border"),
            ("contorno", "/props/border"),
            ("peso", "/props/fontWeight"),
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
                and any(phrase in normalized for phrase in ("arredondado demais", "muito arredondado", "too rounded"))
            )
            if negative:
                disliked.append(path)
            else:
                liked.append(path)
        liked = list(dict.fromkeys(liked))
        disliked = list(dict.fromkeys(disliked))
        ambiguity: list[str] = []
        if not liked and not disliked:
            ambiguity.append("No supported Button token was identified. Choose tokens manually.")
        return json.dumps(
            {
                "targetElementId": request.targetElementId,
                "likedPaths": liked,
                "dislikedPaths": disliked,
                "lockedPaths": liked,
                "explorationPaths": disliked,
                "ambiguity": ambiguity,
                "rationale": (
                    "Explicitly liked tokens are proposed as locks; disliked tokens are "
                    "proposed for bounded exploration."
                ),
            }
        )


class DSPyRefineProvider:
    """Thin adapter for a configured DSPy runtime. Output remains untrusted JSON."""

    def __init__(self) -> None:
        self._generate_spec = dspy.Predict(GenerateSpec)
        self._parse_critique = dspy.Predict(ParseCritique)

    def generate_spec(self, prompt: str) -> str:
        return str(self._generate_spec(prompt=prompt).spec_json)

    def parse_critique(self, request: ParseCritiqueRequest) -> str:
        completion = self._parse_critique(
            spec_json=json.dumps(request.spec), target_element_id=request.targetElementId, critique=request.critique
        )
        return str(completion.patch_intent_json)

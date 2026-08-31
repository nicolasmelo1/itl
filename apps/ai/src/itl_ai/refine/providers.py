# DSPy does not publish pyright stubs; the optional live-provider boundary is isolated here.
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Provider adapter: direct live JSON calls plus optional DSPy experiments.

No provider here knows which component it is refining. The subject arrives as a
`component_type` and its vocabulary is read from the catalog, so a new editable
subject needs no new provider branch.
"""

import json
import unicodedata
from collections.abc import Iterator
from typing import Protocol, cast
from urllib.parse import urlparse

import httpx

from itl_ai.config.settings import Settings
from itl_ai.refine.catalog import editable_entry, editable_props, ordered_visual_paths, visual_values
from itl_ai.refine.models import GenerateVariantsRequest, ParseCritiqueRequest, TasteBrief

# A critique term maps to the first candidate token the selected subject
# actually has, so "spacing" means density on a Button and gap on a Field.
CRITIQUE_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cor", ("recipe", "hintTone")),
    ("color", ("recipe", "hintTone")),
    ("fundo", ("recipe",)),
    ("espac", ("density", "gap")),
    ("spacing", ("density", "gap")),
    ("dens", ("density", "gap")),
    ("gap", ("gap", "density")),
    ("arredond", ("radius",)),
    ("radius", ("radius",)),
    ("round", ("radius",)),
    ("peso", ("fontWeight", "hintTone")),
    ("negrito", ("fontWeight", "hintTone")),
    ("rotulo", ("labelPlacement",)),
    ("label", ("labelPlacement",)),
    ("dica", ("hintTone",)),
    ("hint", ("hintTone",)),
    ("tom", ("hintTone", "recipe")),
    ("tone", ("hintTone", "recipe")),
)
POLICY_RATIONALES = {
    "exploit": "Fixture: apply the interpreted directives with the minimum coherent change.",
    "adjacent_explore": "Fixture: explore one nearby uncertain visual dimension.",
    "wild_explore": "Fixture: explore a clearly different coherent treatment.",
}


class ProviderUnavailableError(RuntimeError):
    """A configured remote provider failed without producing a usable completion."""


def _dspy_operations() -> tuple[object, type[object], type[object], type[object]]:
    """Declare optional DSPy operations without making them the live runtime path."""
    import dspy  # type: ignore[import-untyped]  # DSPy does not publish pyright stubs.

    class GenerateSpec(dspy.Signature):  # type: ignore[misc]
        """Produce one schema-valid, catalog-constrained UI spec as JSON."""

        prompt: str = dspy.InputField()
        target: str = dspy.InputField()
        tasteBrief: str = dspy.InputField()
        spec_json: str = dspy.OutputField(desc="A complete JSON UI spec and nothing else.")

    class ParseCritique(dspy.Signature):  # type: ignore[misc]
        """Interpret critique into reviewable patch intent JSON, never CSS."""

        spec_json: str = dspy.InputField()
        target_element_id: str = dspy.InputField()
        component_type: str = dspy.InputField()
        critique: str = dspy.InputField()
        patch_intent_json: str = dspy.OutputField(desc="A JSON PatchIntent object and nothing else.")

    class GenerateCandidatePatches(dspy.Signature):  # type: ignore[misc]
        """Propose catalog-constrained patches; never mutate a UI spec directly."""

        current_spec_json: str = dspy.InputField()
        component_type: str = dspy.InputField()
        interpretation_json: str = dspy.InputField()
        context_json: str = dspy.InputField()
        tasteBrief: str = dspy.InputField()
        catalog_json: str = dspy.InputField()
        policies_json: str = dspy.InputField()
        repair_feedback: str = dspy.InputField()
        candidate_patches_json: str = dspy.OutputField(
            desc="A JSON object with candidate patches, policy labels, and rationales only."
        )

    return dspy, GenerateSpec, ParseCritique, GenerateCandidatePatches


class RefineProvider(Protocol):
    def generate_spec(self, prompt: str, target: str, taste_brief: TasteBrief) -> str: ...

    def parse_critique(self, request: ParseCritiqueRequest, component_type: str) -> str: ...

    def generate_candidate_patches(
        self,
        request: GenerateVariantsRequest,
        component_type: str,
        taste_brief: TasteBrief,
        policies: list[str],
        repair_feedback: str | None = None,
    ) -> str | None: ...


FIXTURE_SPECS: dict[str, dict[str, object]] = {
    "Button": {
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
    },
    "FormField": {
        "version": "itl.ui/v1",
        "root": "email-field",
        "elements": {
            "email-field": {
                "type": "FormField",
                "props": {
                    "label": "Account email",
                    "hint": "We use this address for essential project notifications.",
                    "appearance": {"labelPlacement": "above", "gap": "regular", "hintTone": "quiet"},
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
    },
}


class DeterministicRefineProvider:
    """Fixture-backed provider used by tests and local development without credentials."""

    def generate_spec(self, prompt: str, target: str, taste_brief: TasteBrief) -> str:
        del prompt, taste_brief
        return json.dumps(FIXTURE_SPECS[target])

    def parse_critique(self, request: ParseCritiqueRequest, component_type: str) -> str:
        normalized = _normalise_critique(request.critique)
        if "__malformed_model_output__" in normalized:
            return "this is not JSON"
        if "__unknown_path__" in normalized:
            return _invalid_path_fixture(request.targetElementId)
        return _interpretation_json(request.targetElementId, normalized, component_type)

    def generate_candidate_patches(
        self,
        request: GenerateVariantsRequest,
        component_type: str,
        taste_brief: TasteBrief,
        policies: list[str],
        repair_feedback: str | None = None,
    ) -> str:
        """Derive fixture patches from the catalog; real candidate search needs a provider."""
        del taste_brief, repair_feedback
        values = visual_values(component_type)
        current = cast(dict[str, str], editable_props(request.spec, request.targetElementId)["appearance"])
        base, mutable = _directive_constraints(request, component_type, values, current)
        changes = _distinct_change_sets(values, current, base, mutable, len(policies))
        if len(changes) < len(policies):
            raise ProviderUnavailableError("The catalog vocabulary cannot produce that many distinct candidates.")
        return json.dumps(
            {
                "candidates": [
                    {
                        "kind": policy,
                        "patch": {
                            "changes": [
                                {"path": f"/appearance/{token}", "value": value} for token, value in change_set.items()
                            ],
                            "rationale": POLICY_RATIONALES[policy],
                        },
                    }
                    for policy, change_set in zip(policies, changes, strict=True)
                ]
            }
        )


def _directive_constraints(
    request: GenerateVariantsRequest,
    component_type: str,
    values: dict[str, tuple[str, ...]],
    current: dict[str, str],
) -> tuple[dict[str, str], list[str]]:
    """Turn hard directives into required changes and rank the remaining tokens."""
    base: dict[str, str] = {}
    kept: set[str] = set()
    explored: list[str] = []
    ordered = {path.removeprefix("/appearance/") for path in ordered_visual_paths(component_type)}
    for directive in request.interpretation.directives:
        token = directive.path.removeprefix("/appearance/")
        options = values[token]
        if directive.kind == "keep":
            kept.add(token)
        elif directive.kind in {"set", "prefer"}:
            base[token] = cast(str, getattr(directive, "value"))
        elif directive.kind == "avoid":
            base[token] = _other_value(options, current[token])
        elif directive.kind in {"increase", "decrease"} and token in ordered:
            step = 1 if directive.kind == "increase" else -1
            index = min(max(options.index(current[token]) + step, 0), len(options) - 1)
            base[token] = options[index]
        elif directive.kind == "explore":
            explored.append(token)
    mutable = [token for token in [*explored, *values] if token not in kept and token not in base]
    return base, list(dict.fromkeys(mutable))


def _other_value(options: tuple[str, ...], current: str) -> str:
    return next((option for option in options if option != current), current)


def _change_set_candidates(
    values: dict[str, tuple[str, ...]], current: dict[str, str], mutable: list[str]
) -> Iterator[dict[str, str]]:
    """Enumerate deterministic extra changes, smallest and nearest first."""
    yield {}
    for token in mutable:
        for value in values[token]:
            if value != current[token]:
                yield {token: value}
    for token in mutable:
        for second in mutable:
            if second == token:
                continue
            yield {
                token: _other_value(values[token], current[token]),
                second: _other_value(values[second], current[second]),
            }


def _distinct_change_sets(
    values: dict[str, tuple[str, ...]],
    current: dict[str, str],
    base: dict[str, str],
    mutable: list[str],
    count: int,
) -> list[dict[str, str]]:
    seen = {tuple(sorted(current.items()))}
    results: list[dict[str, str]] = []
    for extra in _change_set_candidates(values, current, mutable):
        change_set = {**base, **extra}
        if not change_set:
            continue
        signature = tuple(sorted({**current, **change_set}.items()))
        if signature in seen:
            continue
        seen.add(signature)
        results.append(change_set)
        if len(results) == count:
            break
    return results


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


def _interpretation_json(target_element_id: str, critique: str, component_type: str) -> str:
    entry = editable_entry(component_type)
    liked, disliked = _evidence_paths(critique, component_type)
    directives = [
        *[{"kind": "keep", "path": path} for path in liked],
        *[_directive_for_dislike(path, component_type) for path in disliked],
    ]
    ambiguity = (
        [] if liked or disliked else [f"No supported {component_type} token was identified. Choose tokens manually."]
    )
    if not directives:
        directives = [{"kind": "explore", "path": f"/appearance/{next(iter(entry.vocabulary))}"}]
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


def _evidence_paths(critique: str, component_type: str) -> tuple[list[str], list[str]]:
    vocabulary = editable_entry(component_type).vocabulary
    liked: list[str] = []
    disliked: list[str] = []
    for term, tokens in CRITIQUE_TERMS:
        token = next((candidate for candidate in tokens if candidate in vocabulary), None)
        if token is None or term not in critique:
            continue
        path = f"/appearance/{token}"
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


def _directive_for_dislike(path: str, component_type: str) -> dict[str, str]:
    """Only an ordered token can be pushed in a direction; the rest are explored."""
    kind = "decrease" if path in ordered_visual_paths(component_type) else "explore"
    return {"kind": kind, "path": path}


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

    def generate_spec(self, prompt: str, target: str, taste_brief: TasteBrief) -> str:
        return self._complete(
            f"Return exactly one JSON UI spec for a {target} from the supplied request. No markdown.",
            json.dumps({"prompt": prompt, "target": target, "tasteBrief": taste_brief.model_dump()}),
        )

    def parse_critique(self, request: ParseCritiqueRequest, component_type: str) -> str:
        paths = sorted(f"/appearance/{token}" for token in visual_values(component_type))
        return self._complete(
            (
                "Return exactly one JSON object and no markdown. It must have exactly these fields: "
                "targetElementId (copy the supplied ID), evidence ({likedPaths:string[], dislikedPaths:string[], "
                "lockedPaths:string[], strength:weak|moderate|strong}), directives (non-empty array of objects with "
                "kind and path), ambiguity (string[]), and rationale (non-empty string). "
                f"The selected component is a {component_type}. Use only {', '.join(paths)} as paths. "
                "Valid directive kinds are keep, avoid, prefer, set, increase, "
                "decrease, and explore. Do not wrap the object in an interpretation field."
            ),
            json.dumps(
                {
                    "spec": request.spec,
                    "targetElementId": request.targetElementId,
                    "componentType": component_type,
                    "critique": request.critique,
                }
            ),
        )

    def generate_candidate_patches(
        self,
        request: GenerateVariantsRequest,
        component_type: str,
        taste_brief: TasteBrief,
        policies: list[str],
        repair_feedback: str | None = None,
    ) -> str:
        return self._complete(
            (
                "Return exactly one JSON object with a candidates array and no markdown. Do not return UI specs, "
                "CSS, or arbitrary values. Each candidate is {kind, patch:{changes:[{path,value}],rationale}}. "
                f"A patch can modify only the supplied {component_type} appearance catalog paths. The engine applies "
                "it to the current spec, so content and semantic state are inherently untouched. Generate exactly "
                "one distinct candidate for every requested kind. Treat interpretation directives as hard "
                "constraints: keep is immutable; set and prefer require their value; avoid must change the current "
                "value; increase and decrease must move in the requested catalog direction. Use these strategies: "
                "exploit = strongest candidate from matching taste evidence with the minimum coherent changes; "
                "adjacent_explore = a coherent, nearby direction that explores one or two uncertain visual "
                "dimensions; wild_explore = a coherent direction meaningfully different from known preferences "
                f"while respecting hard constraints. The required kinds, in order, are {policies}."
            ),
            json.dumps(
                {
                    "currentSpec": request.spec,
                    "componentType": component_type,
                    "interpretation": request.interpretation.model_dump(),
                    "context": request.context.model_dump(),
                    "tasteBrief": taste_brief.model_dump(),
                    "catalog": visual_values(component_type),
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

    def generate_spec(self, prompt: str, target: str, taste_brief: TasteBrief) -> str:
        completion = self._generate_spec(prompt=prompt, target=target, tasteBrief=taste_brief.model_dump_json())
        return str(completion.spec_json)

    def parse_critique(self, request: ParseCritiqueRequest, component_type: str) -> str:
        completion = self._parse_critique(
            spec_json=json.dumps(request.spec),
            target_element_id=request.targetElementId,
            component_type=component_type,
            critique=request.critique,
        )
        return str(completion.patch_intent_json)

    def generate_candidate_patches(
        self,
        request: GenerateVariantsRequest,
        component_type: str,
        taste_brief: TasteBrief,
        policies: list[str],
        repair_feedback: str | None = None,
    ) -> str:
        completion = self._generate_candidate_patches(
            current_spec_json=json.dumps(request.spec),
            component_type=component_type,
            interpretation_json=request.interpretation.model_dump_json(),
            context_json=request.context.model_dump_json(),
            tasteBrief=taste_brief.model_dump_json(),
            catalog_json=json.dumps(visual_values(component_type)),
            policies_json=json.dumps(policies),
            repair_feedback=repair_feedback or "",
        )
        return str(completion.candidate_patches_json)

"""Deterministic validation and patching for the finite Button catalog."""

from copy import deepcopy
from typing import Literal, cast

from pydantic import BaseModel, ValidationError

from itl_ai.refine.models import (
    BUTTON_TOKEN_PATHS,
    BUTTON_TOKEN_VALUES,
    UI_SPEC_VERSION,
    BadgeProps,
    ButtonProps,
    CardProps,
    InputProps,
    ModelIssue,
    PatchIntent,
    Variant,
)


class RefineValidationError(Exception):
    """An expected, recoverable error that retains the current spec."""

    def __init__(self, code: str, message: str, issues: list[ModelIssue]) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.issues = issues


def _error(code: str, message: str, path: str | None = None) -> RefineValidationError:
    return RefineValidationError(code, message, [ModelIssue(code=code, message=message, path=path)])


def _elements(spec: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], spec["elements"])


def _element_props(element: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], element["props"])


def _validate_elements(elements: dict[str, object]) -> None:
    props_models: dict[str, type[BaseModel]] = {
        "Button": ButtonProps,
        "Input": InputProps,
        "Badge": BadgeProps,
        "Card": CardProps,
    }
    for element_id, raw_element in elements.items():
        if not isinstance(raw_element, dict):
            raise _error("invalid_spec", "Element IDs and elements must be JSON objects.")
        element = cast(dict[str, object], raw_element)
        element_type = element.get("type")
        children = element.get("children")
        if element_type not in props_models or not isinstance(children, list):
            raise _error(
                "invalid_spec", "An element is not registered in the controlled catalog.", f"/elements/{element_id}"
            )
        registered_type = cast(str, element_type)
        child_ids = cast(list[object], children)
        if not all(isinstance(child, str) for child in child_ids):
            raise _error(
                "invalid_spec", "Element children must be stable element IDs.", f"/elements/{element_id}/children"
            )
        if registered_type != "Card" and child_ids:
            raise _error(
                "invalid_spec", f"{registered_type} cannot host child elements.", f"/elements/{element_id}/children"
            )
        if any(cast(str, child) not in elements for child in child_ids):
            raise _error("invalid_spec", "An element references a missing child.", f"/elements/{element_id}/children")
        try:
            element["props"] = props_models[registered_type].model_validate(element.get("props")).model_dump()
        except ValidationError as exc:
            raise _error(
                "invalid_spec",
                "An element has unsupported properties or token values.",
                f"/elements/{element_id}/props",
            ) from exc


def _assert_acyclic(root: str, elements: dict[str, object]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(element_id: str) -> None:
        if element_id in visiting:
            raise _error("invalid_spec", "The UI spec contains a cycle.", f"/elements/{element_id}")
        if element_id in visited:
            return
        visiting.add(element_id)
        raw_element = elements[element_id]
        if not isinstance(raw_element, dict):
            raise _error("invalid_spec", "An element is not a JSON object.", f"/elements/{element_id}")
        children = cast(list[str], cast(dict[str, object], raw_element)["children"])
        for child in children:
            visit(child)
        visiting.remove(element_id)
        visited.add(element_id)

    visit(root)


def validate_ui_spec(input_spec: object) -> dict[str, object]:
    """Validate the full existing catalog before accepting a refinement."""
    if not isinstance(input_spec, dict):
        raise _error("invalid_spec", "A UI spec must be a JSON object.")
    raw_spec = cast(dict[str, object], input_spec)
    root = raw_spec.get("root")
    raw_elements = raw_spec.get("elements")
    if raw_spec.get("version") != UI_SPEC_VERSION:
        raise _error("invalid_spec", "The UI spec version is unsupported.", "/version")
    if not isinstance(root, str) or not isinstance(raw_elements, dict) or root not in raw_elements:
        raise _error("invalid_spec", "The UI spec must have a root element in its elements map.")
    result = deepcopy(raw_spec)
    elements = _elements(result)
    _validate_elements(elements)
    _assert_acyclic(root, elements)
    return result


def button_props(spec: object, target_element_id: str) -> dict[str, object]:
    valid_spec = validate_ui_spec(spec)
    element = _elements(valid_spec).get(target_element_id)
    if not isinstance(element, dict):
        raise _error("invalid_target", "Select a registered Button before refining.", f"/elements/{target_element_id}")
    element_data = cast(dict[str, object], element)
    if element_data.get("type") != "Button":
        raise _error("invalid_target", "Select a registered Button before refining.", f"/elements/{target_element_id}")
    return _element_props(element_data)


def validate_intent(intent: PatchIntent, target_element_id: str) -> None:
    if intent.targetElementId != target_element_id:
        raise _error("invalid_target", "The patch intent targets a different element.")
    all_paths = [*intent.likedPaths, *intent.dislikedPaths, *intent.lockedPaths, *intent.explorationPaths]
    unknown = next((path for path in all_paths if path not in BUTTON_TOKEN_PATHS), None)
    if unknown is not None:
        raise _error("unsupported_path", "The patch intent contains an unsupported Button token path.", unknown)
    has_duplicates = len(set(intent.lockedPaths)) != len(intent.lockedPaths) or len(
        set(intent.explorationPaths)
    ) != len(intent.explorationPaths)
    if has_duplicates:
        raise _error("conflicting_paths", "A path may appear only once in locks or exploration.")
    conflict = set(intent.lockedPaths).intersection(intent.explorationPaths)
    if conflict:
        raise _error("conflicting_paths", "A path cannot be kept and explored at the same time.", sorted(conflict)[0])
    if not intent.explorationPaths:
        raise _error("missing_exploration", "Choose at least one token path to explore.")


def create_variants(
    spec: object, target_element_id: str, intent: PatchIntent, include_wild: bool, include_adjacent: bool = True
) -> list[Variant]:
    current = validate_ui_spec(spec)
    original_props = button_props(current, target_element_id)
    validate_intent(intent, target_element_id)
    kinds: list[tuple[str, Literal["exploit", "adjacent_explore", "wild_explore"], str]] = [
        ("exploit-1", "exploit", "evidence-led refinement")
    ]
    if include_adjacent:
        kinds.append(("adjacent-explore-1", "adjacent_explore", "adjacent catalog alternative"))
    if include_wild:
        kinds.append(("wild-explore-1", "wild_explore", "high-contrast editorial direction"))
    return [
        _create_variant(current, original_props, intent, index, variant_id, kind, direction)
        for index, (variant_id, kind, direction) in enumerate(kinds)
    ]


def _create_variant(
    current: dict[str, object],
    original_props: dict[str, object],
    intent: PatchIntent,
    variant_index: int,
    variant_id: str,
    kind: Literal["exploit", "adjacent_explore", "wild_explore"],
    direction: str,
) -> Variant:
    candidate = deepcopy(current)
    raw_target = _elements(candidate)[intent.targetElementId]
    if not isinstance(raw_target, dict):
        raise _error("invalid_target", "Select a registered Button before refining.")
    candidate_props = _element_props(cast(dict[str, object], raw_target))
    for path in intent.explorationPaths:
        token = path.removeprefix("/props/")
        alternatives = [value for value in BUTTON_TOKEN_VALUES[token] if value != original_props[token]]
        if not alternatives:
            raise _error("unexplorable_path", "This token has no valid alternative.", path)
        candidate_props[token] = alternatives[variant_index % len(alternatives)]
    validated = validate_ui_spec(candidate)
    validated_props = button_props(validated, intent.targetElementId)
    _assert_paths_preserved(validated_props, original_props, intent)
    return Variant(id=variant_id, kind=kind, direction=direction, spec=validated)


def _assert_paths_preserved(candidate: dict[str, object], original: dict[str, object], intent: PatchIntent) -> None:
    for path in intent.lockedPaths:
        token = path.removeprefix("/props/")
        if candidate[token] != original[token]:
            raise _error("lock_broken", "A generated variant changed a locked token.", path)
    for path in intent.explorationPaths:
        token = path.removeprefix("/props/")
        if candidate[token] == original[token]:
            raise _error("unchanged_exploration", "An explored token did not change.", path)

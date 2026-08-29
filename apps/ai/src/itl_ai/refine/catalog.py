"""Deterministic Button catalog validation and candidate-patch materialization."""

from copy import deepcopy
from typing import cast

from pydantic import BaseModel, ValidationError

from itl_ai.refine.models import (
    AttributeDirective,
    BadgeProps,
    ButtonProps,
    CandidatePatch,
    CardProps,
    InputProps,
    Interpretation,
    ModelIssue,
    PreferDirective,
    SetDirective,
)

VISUAL_VALUES: dict[str, tuple[str, ...]] = {
    "recipe": ("primary", "secondary", "outline", "ghost"),
    "size": ("compact", "regular"),
    "radius": ("square", "soft", "pill"),
    "density": ("compact", "comfortable"),
    "fontWeight": ("regular", "semibold"),
}
VISUAL_PATHS = frozenset(f"/appearance/{name}" for name in VISUAL_VALUES)
ORDERED_VISUAL_PATHS = frozenset(
    {"/appearance/size", "/appearance/radius", "/appearance/density", "/appearance/fontWeight"}
)
ADJACENT_TO_EXPLOIT_RATIO = 1 / 3


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


def _appearance(props: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], props["appearance"])


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
        for child in cast(list[str], cast(dict[str, object], raw_element)["children"]):
            visit(child)
        visiting.remove(element_id)
        visited.add(element_id)

    visit(root)


def validate_ui_spec(input_spec: object) -> dict[str, object]:
    if not isinstance(input_spec, dict):
        raise _error("invalid_spec", "A UI spec must be a JSON object.")
    raw_spec = cast(dict[str, object], input_spec)
    root = raw_spec.get("root")
    raw_elements = raw_spec.get("elements")
    if raw_spec.get("version") != "itl.ui/v1":
        raise _error("invalid_spec", "The UI spec version is unsupported.", "/version")
    if not isinstance(root, str) or not isinstance(raw_elements, dict) or root not in raw_elements:
        raise _error("invalid_spec", "The UI spec must have a root element in its elements map.")
    result = deepcopy(raw_spec)
    elements = _elements(result)
    _validate_elements(elements)
    _assert_acyclic(root, elements)
    return result


def button_props(spec: object, target_element_id: str) -> dict[str, object]:
    element = _elements(validate_ui_spec(spec)).get(target_element_id)
    if not isinstance(element, dict):
        raise _error("invalid_target", "Select a registered Button before refining.", f"/elements/{target_element_id}")
    element_data = cast(dict[str, object], element)
    if element_data.get("type") != "Button":
        raise _error("invalid_target", "Select a registered Button before refining.", f"/elements/{target_element_id}")
    return _element_props(element_data)


def validate_interpretation(interpretation: Interpretation, target_element_id: str) -> None:
    if interpretation.targetElementId != target_element_id:
        raise _error("invalid_target", "The interpretation targets a different element.")
    evidence_paths = [
        *interpretation.evidence.likedPaths,
        *interpretation.evidence.dislikedPaths,
        *interpretation.evidence.lockedPaths,
    ]
    if unknown := next((path for path in evidence_paths if path not in VISUAL_PATHS), None):
        raise _error("unsupported_path", "Evidence is scoped only to Button appearance paths.", unknown)
    keep_paths: set[str] = set()
    for directive in interpretation.directives:
        _validate_directive(directive)
        if directive.kind == "keep":
            keep_paths.add(directive.path)
    conflicts = keep_paths.intersection(
        {directive.path for directive in interpretation.directives if directive.kind != "keep"}
    )
    if conflicts:
        raise _error(
            "conflicting_paths", "A visual path cannot be kept and mutated at the same time.", sorted(conflicts)[0]
        )
    if not any(directive.kind != "keep" for directive in interpretation.directives):
        raise _error("missing_directive", "Choose at least one visual attribute directive.")


def _validate_directive(directive: AttributeDirective) -> None:
    if directive.path not in VISUAL_PATHS:
        raise _error("unsupported_path", "Directives may target only Button appearance paths.", directive.path)
    if directive.kind in {"increase", "decrease"} and directive.path not in ORDERED_VISUAL_PATHS:
        raise _error(
            "unsupported_direction", "Only ordered visual attributes can increase or decrease.", directive.path
        )
    if isinstance(directive, (PreferDirective, SetDirective)):
        token = directive.path.removeprefix("/appearance/")
        if directive.value not in VISUAL_VALUES[token]:
            raise _error(
                "unsupported_value", "A directive value is outside the Button visual vocabulary.", directive.path
            )


def should_include_adjacent(adjacent_count: int, exploit_count: int) -> bool:
    """Use an explicit proposal ratio, not accidental ordering of token enums."""
    return adjacent_count < max(1, round((exploit_count + 1) * ADJACENT_TO_EXPLOIT_RATIO))


def apply_and_validate_candidate_patch(
    original_spec: object,
    target_element_id: str,
    interpretation: Interpretation,
    patch: CandidatePatch,
) -> dict[str, object]:
    """Apply only visual catalog patches, then enforce every hard directive locally."""
    current = validate_ui_spec(original_spec)
    original = button_props(current, target_element_id)
    validate_interpretation(interpretation, target_element_id)
    candidate = deepcopy(current)
    candidate_element = _elements(candidate).get(target_element_id)
    if not isinstance(candidate_element, dict):
        raise _error("invalid_target", "Select a registered Button before refining.", f"/elements/{target_element_id}")
    candidate_appearance = _appearance(_element_props(cast(dict[str, object], candidate_element)))
    changed_paths: set[str] = set()
    for change in patch.changes:
        if change.path in changed_paths:
            raise _error(
                "duplicate_patch_path", "A candidate patch may change each visual path only once.", change.path
            )
        changed_paths.add(change.path)
        candidate_appearance[change.path.removeprefix("/appearance/")] = change.value
    candidate = validate_ui_spec(candidate)
    _assert_directives_preserved(
        _appearance(button_props(candidate, target_element_id)), _appearance(original), interpretation
    )
    return candidate


def _assert_directives_preserved(
    candidate: dict[str, object], original: dict[str, object], interpretation: Interpretation
) -> None:
    for directive in interpretation.directives:
        token = directive.path.removeprefix("/appearance/")
        if directive.kind == "keep" and candidate[token] != original[token]:
            raise _error(
                "lock_broken", "A generated candidate changed an explicitly kept visual attribute.", directive.path
            )
        if isinstance(directive, (SetDirective, PreferDirective)) and candidate[token] != directive.value:
            raise _error(
                "directive_broken",
                "A generated candidate did not use the visual value required by the directive.",
                directive.path,
            )
        if directive.kind == "avoid" and candidate[token] == original[token]:
            raise _error(
                "directive_broken",
                "A generated candidate did not move away from the avoided visual value.",
                directive.path,
            )
        if directive.kind == "decrease" and VISUAL_VALUES[token].index(cast(str, candidate[token])) >= VISUAL_VALUES[
            token
        ].index(cast(str, original[token])):
            raise _error("direction_broken", "A decrease directive moved in the opposite direction.", directive.path)
        if directive.kind == "increase" and VISUAL_VALUES[token].index(cast(str, candidate[token])) <= VISUAL_VALUES[
            token
        ].index(cast(str, original[token])):
            raise _error("direction_broken", "An increase directive moved in the opposite direction.", directive.path)

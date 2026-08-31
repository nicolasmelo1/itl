"""Deterministic catalog validation and candidate-patch materialization.

Every rule here is derived from the component registry, so adding an editable
subject is a registry change rather than a new branch in this module.
"""

from copy import deepcopy
from typing import cast

from pydantic import ValidationError

from itl_ai.refine.models import (
    COMPONENT_REGISTRY,
    EDITABLE_COMPONENTS,
    AtomicScope,
    AttributeDirective,
    CandidatePatch,
    ComponentEntry,
    Interpretation,
    ModelIssue,
    PreferDirective,
    SetDirective,
    level_for_component,
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


def editable_entry(component_type: str) -> ComponentEntry:
    entry = EDITABLE_COMPONENTS.get(component_type)
    if entry is None:
        raise _error("unsupported_subject", f"{component_type} is not an editable Taste Loop subject.")
    return entry


def visual_values(component_type: str) -> dict[str, tuple[str, ...]]:
    """The finite token vocabulary a model may choose from for this subject."""
    return dict(editable_entry(component_type).vocabulary)


def visual_paths(component_type: str) -> frozenset[str]:
    return frozenset(f"/appearance/{token}" for token in editable_entry(component_type).vocabulary)


def ordered_visual_paths(component_type: str) -> frozenset[str]:
    return frozenset(f"/appearance/{token}" for token in editable_entry(component_type).orderedTokens)


def _elements(spec: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], spec["elements"])


def _element_props(element: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], element["props"])


def _appearance(props: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], props["appearance"])


def _validate_elements(elements: dict[str, object]) -> None:
    for element_id, raw_element in elements.items():
        if not isinstance(raw_element, dict):
            raise _error("invalid_spec", "Element IDs and elements must be JSON objects.")
        element = cast(dict[str, object], raw_element)
        element_type = element.get("type")
        children = element.get("children")
        if (
            not isinstance(element_type, str)
            or element_type not in COMPONENT_REGISTRY
            or not isinstance(children, list)
        ):
            raise _error(
                "invalid_spec", "An element is not registered in the controlled catalog.", f"/elements/{element_id}"
            )
        entry = COMPONENT_REGISTRY[element_type]
        child_ids = cast(list[object], children)
        if not all(isinstance(child, str) for child in child_ids):
            raise _error(
                "invalid_spec", "Element children must be stable element IDs.", f"/elements/{element_id}/children"
            )
        for child in cast(list[str], child_ids):
            child_element = elements.get(child)
            if not isinstance(child_element, dict):
                raise _error(
                    "invalid_spec", "An element references a missing child.", f"/elements/{element_id}/children"
                )
            child_type = cast(dict[str, object], child_element).get("type")
            if child_type not in entry.allowedChildTypes:
                raise _error(
                    "invalid_spec",
                    f"{element_type} cannot host {child_type}.",
                    f"/elements/{element_id}/children",
                )
        try:
            element["props"] = entry.props.model_validate(element.get("props")).model_dump()
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


def element_component_type(spec: object, target_element_id: str) -> str:
    """Resolve which registered subject an element ID names, or fail closed."""
    element = _elements(validate_ui_spec(spec)).get(target_element_id)
    if not isinstance(element, dict):
        raise _error(
            "invalid_target",
            "Select a registered editable component before refining.",
            f"/elements/{target_element_id}",
        )
    component_type = cast(dict[str, object], element).get("type")
    if not isinstance(component_type, str) or component_type not in EDITABLE_COMPONENTS:
        raise _error(
            "invalid_target",
            "Select a registered editable component before refining.",
            f"/elements/{target_element_id}",
        )
    return component_type


def editable_props(spec: object, target_element_id: str) -> dict[str, object]:
    validated = validate_ui_spec(spec)
    element_component_type(validated, target_element_id)
    return _element_props(cast(dict[str, object], _elements(validated)[target_element_id]))


def assert_scope_matches_element(spec: object, target_element_id: str, scope: AtomicScope) -> str:
    """A request may narrow its subject, but never move it to another level.

    The scope ID stays free so that one Button role can be learned separately
    from another; the level is what keeps an atom decision out of a molecule's
    evidence.
    """
    component_type = element_component_type(spec, target_element_id)
    level = level_for_component(component_type)
    if scope.level != level:
        raise _error(
            "scope_mismatch",
            f"This request targets a {component_type}; its scope must be {level}-level.",
            f"/elements/{target_element_id}",
        )
    return component_type


def validate_interpretation(interpretation: Interpretation, target_element_id: str, component_type: str) -> None:
    if interpretation.targetElementId != target_element_id:
        raise _error("invalid_target", "The interpretation targets a different element.")
    supported = visual_paths(component_type)
    evidence_paths = [
        *interpretation.evidence.likedPaths,
        *interpretation.evidence.dislikedPaths,
        *interpretation.evidence.lockedPaths,
    ]
    if unknown := next((path for path in evidence_paths if path not in supported), None):
        raise _error("unsupported_path", f"Evidence is scoped only to {component_type} appearance paths.", unknown)
    keep_paths: set[str] = set()
    for directive in interpretation.directives:
        _validate_directive(directive, component_type)
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


def _validate_directive(directive: AttributeDirective, component_type: str) -> None:
    if directive.path not in visual_paths(component_type):
        raise _error(
            "unsupported_path", f"Directives may target only {component_type} appearance paths.", directive.path
        )
    if directive.kind in {"increase", "decrease"} and directive.path not in ordered_visual_paths(component_type):
        raise _error(
            "unsupported_direction", "Only ordered visual attributes can increase or decrease.", directive.path
        )
    if isinstance(directive, (PreferDirective, SetDirective)):
        token = directive.path.removeprefix("/appearance/")
        if directive.value not in visual_values(component_type)[token]:
            raise _error(
                "unsupported_value",
                f"A directive value is outside the {component_type} visual vocabulary.",
                directive.path,
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
    component_type = element_component_type(current, target_element_id)
    original = editable_props(current, target_element_id)
    validate_interpretation(interpretation, target_element_id, component_type)
    candidate = deepcopy(current)
    candidate_element = _elements(candidate).get(target_element_id)
    if not isinstance(candidate_element, dict):
        raise _error(
            "invalid_target",
            "Select a registered editable component before refining.",
            f"/elements/{target_element_id}",
        )
    candidate_appearance = _appearance(_element_props(cast(dict[str, object], candidate_element)))
    changed_paths: set[str] = set()
    for change in patch.changes:
        if change.path not in visual_paths(component_type):
            raise _error("unsupported_path", f"A patch may target only {component_type} appearance paths.", change.path)
        if change.path in changed_paths:
            raise _error(
                "duplicate_patch_path", "A candidate patch may change each visual path only once.", change.path
            )
        changed_paths.add(change.path)
        candidate_appearance[change.path.removeprefix("/appearance/")] = change.value
    candidate = validate_ui_spec(candidate)
    _assert_directives_preserved(
        _appearance(editable_props(candidate, target_element_id)),
        _appearance(original),
        interpretation,
        component_type,
    )
    return candidate


def _assert_directives_preserved(
    candidate: dict[str, object],
    original: dict[str, object],
    interpretation: Interpretation,
    component_type: str,
) -> None:
    values = visual_values(component_type)
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
        if directive.kind == "decrease" and values[token].index(cast(str, candidate[token])) >= values[token].index(
            cast(str, original[token])
        ):
            raise _error("direction_broken", "A decrease directive moved in the opposite direction.", directive.path)
        if directive.kind == "increase" and values[token].index(cast(str, candidate[token])) <= values[token].index(
            cast(str, original[token])
        ):
            raise _error("direction_broken", "An increase directive moved in the opposite direction.", directive.path)

"""The shared taste dimension space and each component's capability manifest.

Taste lives in one small, versioned space. A component is a *stimulus* that
exposes part of that space through its own finite tokens — never a private
vocabulary. `Button.radius=square` and `Card.radius=none` are different tokens
and the same point on `shape.radius`, which is what lets a judgment on one
component be read on another.

The normalized coordinate is an internal representation. A model still proposes
catalog values and the engine still validates them; nothing here widens what a
provider may emit.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal, get_args

from pydantic import Field

from itl_ai.config.paths import CONTRACTS_ROOT
from itl_ai.refine.base import StrictModel, TasteOutcome

DIMENSION_SPACE_VERSION = "itl.taste-dimensions/v1"
CONTRACT_PATH = CONTRACTS_ROOT / "catalog" / "taste-dimensions.v1.json"

TasteDimension = Literal[
    "shape.radius",
    "shape.borderWeight",
    "shape.geometry",
    "density.spacing",
    "density.padding",
    "density.controlHeight",
    "density.informationDensity",
    "emphasis.contrast",
    "emphasis.elevation",
    "emphasis.weight",
    "emphasis.saturation",
    "typography.scale",
    "typography.weight",
    "typography.tracking",
    "typography.hierarchy",
    "surface.fill",
    "surface.border",
    "surface.elevation",
    "surface.transparency",
    "motion.speed",
    "motion.amplitude",
    "motion.easing",
    "composition.alignment",
    "composition.whitespace",
    "composition.grouping",
    "composition.hierarchy",
]
ORDERED_TASTE_DIMENSIONS: tuple[TasteDimension, ...] = get_args(TasteDimension)
TASTE_DIMENSIONS: frozenset[str] = frozenset(ORDERED_TASTE_DIMENSIONS)

# How much one judgment moves the stimulus it was made about, and how much it
# moves the treatment it replaced. A manual edit is the strongest statement a
# person makes; an indifference is recorded as coverage with no direction.
OUTCOME_POLARITY: dict[TasteOutcome, tuple[float, float]] = {
    "accepted": (1.0, -0.25),
    "almost": (0.5, 0.0),
    "rejected": (-1.0, 0.0),
    "indifferent": (0.0, 0.0),
    "manual_edit": (1.0, -0.75),
}


class ManifestError(RuntimeError):
    """A capability manifest and the component registry disagree."""


class DimensionProjection(StrictModel):
    """How one component's finite token values land on a shared dimension."""

    token: str = Field(pattern=r"^[a-z][a-zA-Z0-9]*$")
    values: dict[str, float]


class DimensionSpaceContract(StrictModel):
    version: Literal["itl.taste-dimensions/v1"]
    description: str
    dimensions: dict[str, list[str]]
    components: dict[str, dict[TasteDimension, DimensionProjection]]


@dataclass(frozen=True)
class DimensionCapability:
    """One dimension a component exposes, and the token that exposes it."""

    dimension: TasteDimension
    token: str
    projection: Mapping[str, float]

    @property
    def path(self) -> str:
        return f"/appearance/{self.token}"

    def coordinate(self, value: str) -> float | None:
        return self.projection.get(value)

    def nearest_value(self, coordinate: float) -> str:
        """The catalog value this component would use for a shared coordinate."""
        return min(sorted(self.projection), key=lambda value: abs(self.projection[value] - coordinate))


@dataclass(frozen=True)
class StimulusCoordinate:
    """One dimension reading taken from a treatment a person actually saw."""

    dimension: TasteDimension
    token: str
    value: str
    coordinate: float
    polarity: float


def _load_contract() -> DimensionSpaceContract:
    try:
        raw = CONTRACT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"The taste dimension contract is missing at {CONTRACT_PATH}.") from exc
    return DimensionSpaceContract.model_validate_json(raw)


def _assert_contract_matches_the_typed_space(contract: DimensionSpaceContract) -> None:
    declared = frozenset(f"{group}.{name}" for group, names in contract.dimensions.items() for name in names)
    if declared != TASTE_DIMENSIONS:
        difference = sorted(declared.symmetric_difference(TASTE_DIMENSIONS))
        raise ManifestError(f"The dimension contract and the typed dimension space disagree on {difference}.")


CONTRACT = _load_contract()
_assert_contract_matches_the_typed_space(CONTRACT)
CAPABILITY_MANIFESTS: dict[str, tuple[DimensionCapability, ...]] = {
    component: tuple(
        DimensionCapability(dimension=dimension, token=projection.token, projection=dict(projection.values))
        for dimension, projection in sorted(projections.items())
    )
    for component, projections in CONTRACT.components.items()
}


def capabilities_for(component_type: str) -> tuple[DimensionCapability, ...]:
    """Which parts of the shared space this stimulus can express."""
    return CAPABILITY_MANIFESTS.get(component_type, ())


def dimensions_for(component_type: str) -> frozenset[str]:
    return frozenset(capability.dimension for capability in capabilities_for(component_type))


def capability_for(component_type: str, dimension: str) -> DimensionCapability | None:
    return next(
        (capability for capability in capabilities_for(component_type) if capability.dimension == dimension), None
    )


def capability_for_token(component_type: str, token: str) -> DimensionCapability | None:
    return next((capability for capability in capabilities_for(component_type) if capability.token == token), None)


def stimulus_coordinates(
    component_type: str,
    before: Mapping[str, str],
    after: Mapping[str, str] | None,
    outcome: TasteOutcome,
) -> list[StimulusCoordinate]:
    """Read one judgment at dimension altitude, in the shared space.

    Accepting a square, compact Button is evidence for `shape.radius → angular`
    and `density.padding → compact` at the same time; editing it away from
    `soft` is also evidence against the treatment it replaced.
    """
    readings: list[StimulusCoordinate] = []
    for token, value, polarity in _weighted_token_values(before, after, outcome):
        capability = capability_for_token(component_type, token)
        coordinate = capability.coordinate(value) if capability else None
        if capability is None or coordinate is None:
            continue
        readings.append(
            StimulusCoordinate(
                dimension=capability.dimension,
                token=token,
                value=value,
                coordinate=coordinate,
                polarity=polarity,
            )
        )
    return readings


def _weighted_token_values(
    before: Mapping[str, str], after: Mapping[str, str] | None, outcome: TasteOutcome
) -> Iterable[tuple[str, str, float]]:
    shown, replaced = OUTCOME_POLARITY[outcome]
    if after is None:
        return [(token, value, shown) for token, value in before.items()]
    return _changed_and_unchanged_values(before, after, outcome, shown, replaced)


def _changed_and_unchanged_values(
    before: Mapping[str, str], after: Mapping[str, str], outcome: TasteOutcome, shown: float, replaced: float
) -> list[tuple[str, str, float]]:
    rows: list[tuple[str, str, float]] = []
    for token, previous in before.items():
        current = after.get(token, previous)
        if current != previous:
            rows.append((token, current, shown))
            if replaced != 0.0:
                rows.append((token, previous, replaced))
        # A manual edit is a statement about the token the person moved. The
        # ones they left alone are not silently promoted to endorsements.
        elif outcome != "manual_edit":
            rows.append((token, current, shown))
    return rows


def _assert_component_is_registered(component: str, vocabularies: Mapping[str, Mapping[str, tuple[str, ...]]]) -> None:
    if component not in vocabularies:
        raise ManifestError(f"{component} declares taste capabilities but is not a registered editable subject.")


def _assert_tokens_are_covered_exactly_once(
    component: str, capabilities: tuple[DimensionCapability, ...], vocabulary: Mapping[str, tuple[str, ...]]
) -> None:
    claimed = [capability.token for capability in capabilities]
    if len(claimed) != len(set(claimed)):
        raise ManifestError(f"{component} maps one token onto more than one shared dimension.")
    if set(claimed) != set(vocabulary):
        difference = sorted(set(claimed).symmetric_difference(vocabulary))
        raise ManifestError(f"{component} does not declare a taste capability for {difference}.")


def _assert_projection_is_total(component: str, capability: DimensionCapability, values: tuple[str, ...]) -> None:
    if set(capability.projection) != set(values):
        difference = sorted(set(capability.projection).symmetric_difference(values))
        raise ManifestError(
            f"{component}.{capability.token} does not project {difference} onto {capability.dimension}."
        )
    outside = sorted(value for value, point in capability.projection.items() if not 0.0 <= point <= 1.0)
    if outside:
        raise ManifestError(f"{component}.{capability.token} projects {outside} outside the shared 0..1 scale.")


def _assert_ordered_token_is_monotonic(
    component: str, capability: DimensionCapability, values: tuple[str, ...]
) -> None:
    """An ordinal directive and the shared scale must agree on which way is up."""
    points = [capability.projection[value] for value in values]
    rising = all(earlier < later for earlier, later in zip(points, points[1:], strict=False))
    falling = all(earlier > later for earlier, later in zip(points, points[1:], strict=False))
    if not rising and not falling:
        raise ManifestError(
            f"{component}.{capability.token} is an ordered token, so its projection onto "
            f"{capability.dimension} must be monotonic."
        )


def validate_capability_manifests(
    vocabularies: Mapping[str, Mapping[str, tuple[str, ...]]],
    ordered_tokens: Mapping[str, frozenset[str]],
) -> None:
    """Fail closed when a manifest and the component registry disagree.

    A dimension a component cannot actually express, or a token no dimension
    reads, would both be invisible at runtime and wrong in the artifact.
    """
    for component in vocabularies:
        if component not in CAPABILITY_MANIFESTS:
            raise ManifestError(f"{component} is an editable subject without a taste capability manifest.")
    for component, capabilities in CAPABILITY_MANIFESTS.items():
        _assert_component_is_registered(component, vocabularies)
        vocabulary = vocabularies[component]
        _assert_tokens_are_covered_exactly_once(component, capabilities, vocabulary)
        for capability in capabilities:
            _assert_projection_is_total(component, capability, vocabulary[capability.token])
            if capability.token in ordered_tokens.get(component, frozenset()):
                _assert_ordered_token_is_monotonic(component, capability, vocabulary[capability.token])

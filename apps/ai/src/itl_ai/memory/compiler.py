"""Compile dimension observations into shared preferences and residuals.

Sanitized observations stay canonical; everything here is a derived cache that
must always be rebuildable. A compiled preference that cannot name the event
IDs behind it does not leave this module.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from itl_ai.refine.dimensions import DimensionCapability, capabilities_for
from itl_ai.refine.models import ComponentResidual, DimensionEvidence, DimensionSource

# Two positive readings this far apart on one dimension are not one preference.
CONTRADICTION_SPREAD = 0.5
# A rejection this close to the compiled preference contests it directly.
NEGATIVE_TOLERANCE = 0.1
# Past this, the component is not expressing the shared taste but an exception.
RESIDUAL_EXCEPTION_DELTA = 0.25

Agreement = Literal["consistent", "contradictory", "unknown"]


@dataclass(frozen=True)
class ObservationRow:
    """One dimension reading, already weighted by context, strength and outcome."""

    event_id: int
    dimension: str
    component_type: str
    value: str
    coordinate: float
    weight: float


def compile_dimension_evidence(component_type: str, rows: Sequence[ObservationRow]) -> list[DimensionEvidence]:
    """Read the shared space through one component's own tokens.

    Only the dimensions this component declares are returned, so evidence
    transfers along a shared dimension and nowhere else.
    """
    grouped: dict[str, list[ObservationRow]] = defaultdict(list)
    for row in rows:
        grouped[row.dimension].append(row)
    return [
        _dimension_evidence(capability, grouped.get(capability.dimension, []), component_type)
        for capability in capabilities_for(component_type)
    ]


def _dimension_evidence(
    capability: DimensionCapability, rows: Sequence[ObservationRow], component_type: str
) -> DimensionEvidence:
    coordinate = _weighted_mean(rows)
    return DimensionEvidence(
        dimension=capability.dimension,
        token=capability.token,
        coordinate=coordinate,
        nearestValue=capability.nearest_value(coordinate) if coordinate is not None else None,
        support=len(rows),
        agreement=_agreement(rows, coordinate),
        eventIds=sorted({row.event_id for row in rows}),
        sources=_sources(rows),
        residual=_residual(capability, rows, component_type, coordinate),
    )


def _weighted_mean(rows: Sequence[ObservationRow]) -> float | None:
    """Where the person sits on this dimension, or nothing when it is unknown."""
    endorsed = [row for row in rows if row.weight > 0]
    total = sum(row.weight for row in endorsed)
    if total <= 0:
        return None
    return round(sum(row.weight * row.coordinate for row in endorsed) / total, 4)


def _agreement(rows: Sequence[ObservationRow], coordinate: float | None) -> Agreement:
    """Contradiction is an output, not a failure, so it is reported as one."""
    endorsed = [row.coordinate for row in rows if row.weight > 0]
    if coordinate is None or not endorsed:
        return "unknown"
    contested = any(row.weight < 0 and abs(row.coordinate - coordinate) <= NEGATIVE_TOLERANCE for row in rows)
    return "contradictory" if max(endorsed) - min(endorsed) > CONTRADICTION_SPREAD or contested else "consistent"


def _sources(rows: Sequence[ObservationRow]) -> list[DimensionSource]:
    grouped: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        grouped[row.component_type].add(row.event_id)
    return [
        DimensionSource(componentType=component, eventIds=sorted(event_ids))
        for component, event_ids in sorted(grouped.items())
    ]


def _residual(
    capability: DimensionCapability, rows: Sequence[ObservationRow], component_type: str, shared: float | None
) -> ComponentResidual | None:
    """How far this component sits from the shared preference on this dimension."""
    own = [row for row in rows if row.component_type == component_type]
    own_coordinate = _weighted_mean(own)
    if own_coordinate is None or shared is None:
        return None
    delta = round(own_coordinate - shared, 4)
    return ComponentResidual(
        componentType=component_type,
        dimension=capability.dimension,
        componentCoordinate=own_coordinate,
        sharedCoordinate=shared,
        delta=delta,
        isException=abs(delta) >= RESIDUAL_EXCEPTION_DELTA,
        eventIds=sorted({row.event_id for row in own}),
    )

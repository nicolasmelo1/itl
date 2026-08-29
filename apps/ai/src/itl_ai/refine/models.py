"""Typed boundary models for the refinement API.

These models deliberately live in the Python service. The JSON fixtures under
``contracts/refine`` are the shared HTTP examples; neither application imports
the other application's runtime types.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

UI_SPEC_VERSION = "itl.ui/v1"
BUTTON_TOKEN_VALUES: dict[str, tuple[str, ...]] = {
    "variant": ("solid", "subtle", "outline"),
    "size": ("compact", "regular"),
    "radius": ("square", "soft", "pill"),
    "density": ("compact", "comfortable"),
    "background": ("accent", "surface", "transparent"),
    "foreground": ("light", "dark"),
    "border": ("none", "subtle", "strong"),
    "fontWeight": ("regular", "semibold"),
    "state": ("default", "disabled", "loading"),
}
BUTTON_TOKEN_PATHS = frozenset(f"/props/{name}" for name in BUTTON_TOKEN_VALUES)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ButtonProps(StrictModel):
    label: str = Field(min_length=1)
    variant: Literal["solid", "subtle", "outline"]
    size: Literal["compact", "regular"]
    radius: Literal["square", "soft", "pill"]
    density: Literal["compact", "comfortable"]
    background: Literal["accent", "surface", "transparent"]
    foreground: Literal["light", "dark"]
    border: Literal["none", "subtle", "strong"]
    fontWeight: Literal["regular", "semibold"]
    state: Literal["default", "disabled", "loading"]


class InputProps(StrictModel):
    label: str = Field(min_length=1)
    placeholder: str
    value: str
    tone: Literal["quiet", "strong"]
    state: Literal["default", "disabled"]


class BadgeProps(StrictModel):
    label: str = Field(min_length=1)
    tone: Literal["neutral", "accent", "success"]


class CardProps(StrictModel):
    title: str = Field(min_length=1)
    description: str
    emphasis: Literal["quiet", "raised"]


class ModelIssue(StrictModel):
    code: str
    message: str
    path: str | None = None


class ErrorResponse(StrictModel):
    code: str
    message: str
    issues: list[ModelIssue] = []
    recoverable: bool = True


class GenerateSpecRequest(StrictModel):
    target: Literal["Button"] = "Button"
    prompt: str = Field(default="A primary action", min_length=1, max_length=4_000)
    sessionId: str = Field(default="local", pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    context: str | None = Field(default=None, max_length=200)


class GenerateSpecResponse(StrictModel):
    spec: dict[str, object]
    evidenceIds: list[int] = []
    outputId: str


class ParseCritiqueRequest(StrictModel):
    specVersion: Literal["itl.ui/v1"]
    spec: dict[str, object]
    targetElementId: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    critique: str = Field(min_length=1, max_length=4_000)


class PatchIntent(StrictModel):
    targetElementId: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    likedPaths: list[str] = []
    dislikedPaths: list[str] = []
    lockedPaths: list[str] = []
    explorationPaths: list[str] = []
    ambiguity: list[str] = []
    rationale: str = Field(min_length=1)


class ParseCritiqueResponse(StrictModel):
    intent: PatchIntent


class GenerateVariantsRequest(StrictModel):
    specVersion: Literal["itl.ui/v1"]
    spec: dict[str, object]
    targetElementId: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    intent: PatchIntent
    includeWild: bool = False
    sessionId: str = Field(default="local", pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    context: str | None = Field(default=None, max_length=200)


class Variant(StrictModel):
    id: str
    kind: Literal["exploit", "adjacent_explore", "wild_explore"]
    direction: str
    spec: dict[str, object]


class GenerateVariantsResponse(StrictModel):
    variants: list[Variant]
    evidenceIds: list[int] = []
    outputId: str


class PreferenceEventRequest(StrictModel):
    """An explicit, append-only action from the refinement UI."""

    sessionId: str = Field(default="local", pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    componentType: Literal["Button"] = "Button"
    context: str | None = Field(default=None, max_length=200)
    targetElementId: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    action: Literal[
        "manual_edit",
        "confirmed_critique",
        "explicit_attribute_feedback",
        "absolute_feedback",
        "pairwise_choice",
        "candidate_acceptance",
        "rejection",
        "indifference",
        "explore_more",
    ]
    source: Literal[
        "manual_edit",
        "confirmed_critique",
        "explicit_attribute_feedback",
        "absolute_feedback",
        "pairwise_choice",
        "candidate_acceptance",
        "model_inference",
    ]
    beforeSpec: dict[str, object]
    afterSpec: dict[str, object] | None = None
    selectedElementId: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]*$")
    candidateId: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]*$")
    likedPaths: list[str] = []
    dislikedPaths: list[str] = []
    lockedPaths: list[str] = []
    critique: str | None = Field(default=None, max_length=4_000)
    parserInterpretation: PatchIntent | None = None


class PreferenceEventResponse(StrictModel):
    id: int
    createdAt: datetime


class RetrievedEvidence(StrictModel):
    id: int
    contextRelation: Literal["exact", "mismatch"]
    preferenceRelation: Literal["supporting", "conflicting", "unknown"]
    source: str
    context: str | None = None
    likedPaths: list[str]
    dislikedPaths: list[str]
    lockedPaths: list[str]
    critique: str | None = None


class MemoryResponse(StrictModel):
    evidence: list[RetrievedEvidence]

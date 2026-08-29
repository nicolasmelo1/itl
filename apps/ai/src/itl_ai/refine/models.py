"""Typed HTTP models for the contextual Button refinement boundary."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

UI_SPEC_VERSION = "itl.ui/v1"
VisualPath = Literal[
    "/appearance/recipe",
    "/appearance/size",
    "/appearance/radius",
    "/appearance/density",
    "/appearance/fontWeight",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ButtonContent(StrictModel):
    label: str = Field(min_length=1)


class ButtonSemantic(StrictModel):
    role: Literal["primary-action", "secondary-action"]
    state: Literal["default", "disabled", "loading"]


class ButtonAppearance(StrictModel):
    recipe: Literal["primary", "secondary", "outline", "ghost"]
    size: Literal["compact", "regular"]
    radius: Literal["square", "soft", "pill"]
    density: Literal["compact", "comfortable"]
    fontWeight: Literal["regular", "semibold"]


class ButtonProps(StrictModel):
    content: ButtonContent
    semantic: ButtonSemantic
    appearance: ButtonAppearance


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


class DesignContext(StrictModel):
    role: Literal["primary-action", "secondary-action"]
    surface: Literal["toolbar", "hero", "form", "dashboard"]
    density: Literal["compact", "comfortable"]


class PreferenceEvidence(StrictModel):
    likedPaths: list[VisualPath] = []
    dislikedPaths: list[VisualPath] = []
    lockedPaths: list[VisualPath] = []
    strength: Literal["weak", "moderate", "strong"] = "moderate"


class KeepDirective(StrictModel):
    kind: Literal["keep"]
    path: VisualPath


class AvoidDirective(StrictModel):
    kind: Literal["avoid"]
    path: VisualPath


class PreferDirective(StrictModel):
    kind: Literal["prefer"]
    path: VisualPath
    value: str


class SetDirective(StrictModel):
    kind: Literal["set"]
    path: VisualPath
    value: str


class IncreaseDirective(StrictModel):
    kind: Literal["increase"]
    path: VisualPath


class DecreaseDirective(StrictModel):
    kind: Literal["decrease"]
    path: VisualPath


class ExploreDirective(StrictModel):
    kind: Literal["explore"]
    path: VisualPath


AttributeDirective = Annotated[
    KeepDirective
    | AvoidDirective
    | PreferDirective
    | SetDirective
    | IncreaseDirective
    | DecreaseDirective
    | ExploreDirective,
    Field(discriminator="kind"),
]


class Interpretation(StrictModel):
    targetElementId: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    evidence: PreferenceEvidence
    directives: list[AttributeDirective]
    ambiguity: list[str] = []
    rationale: str = Field(min_length=1)


class GenerateSpecRequest(StrictModel):
    target: Literal["Button"] = "Button"
    prompt: str = Field(default="A primary action", min_length=1, max_length=4_000)
    sessionId: str = Field(default="local", pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    context: DesignContext


class GenerateSpecResponse(StrictModel):
    spec: dict[str, object]
    evidenceIds: list[int] = []
    outputId: str


class ParseCritiqueRequest(StrictModel):
    specVersion: Literal["itl.ui/v1"]
    spec: dict[str, object]
    targetElementId: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    critique: str = Field(min_length=1, max_length=4_000)


class ParseCritiqueResponse(StrictModel):
    interpretation: Interpretation


class GenerateVariantsRequest(StrictModel):
    specVersion: Literal["itl.ui/v1"]
    spec: dict[str, object]
    targetElementId: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    interpretation: Interpretation
    includeWild: bool = False
    sessionId: str = Field(default="local", pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    context: DesignContext


class Variant(StrictModel):
    id: str
    kind: Literal["exploit", "adjacent_explore", "wild_explore"]
    direction: str
    spec: dict[str, object]


class GenerateVariantsResponse(StrictModel):
    variants: list[Variant]
    evidenceIds: list[int] = []
    outputId: str


class SpecDiff(StrictModel):
    path: str
    before: object | None = None
    after: object | None = None


class PreferenceEventRequest(StrictModel):
    """An explicit, append-only action from the refinement UI."""

    sessionId: str = Field(default="local", pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    componentType: Literal["Button"] = "Button"
    context: DesignContext
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
    evidence: PreferenceEvidence = PreferenceEvidence()
    directives: list[AttributeDirective] = []
    critique: str | None = Field(default=None, max_length=4_000)
    parserInterpretation: Interpretation | None = None


class PreferenceEventResponse(StrictModel):
    id: int
    createdAt: datetime


class RetrievedEvidence(StrictModel):
    id: int
    contextRelation: Literal["exact", "compatible", "global", "mismatch"]
    preferenceRelation: Literal["supporting", "conflicting", "unknown"]
    source: str
    context: DesignContext | None = None
    evidence: PreferenceEvidence
    critique: str | None = None


class MemoryQuery(StrictModel):
    context: DesignContext
    evidence: PreferenceEvidence = PreferenceEvidence()


class MemoryResponse(StrictModel):
    evidence: list[RetrievedEvidence]

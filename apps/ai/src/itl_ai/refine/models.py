"""Typed HTTP models for the contextual Button refinement boundary."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


AtomicDesignLevel = Literal["foundation", "atom", "molecule", "organism", "template", "page"]


class AtomicScope(StrictModel):
    """The exact Atomic Design subject a session is allowed to learn from."""

    level: AtomicDesignLevel
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    semanticRole: str | None = Field(default=None, min_length=1, max_length=120)


DEFAULT_BUTTON_SCOPE = AtomicScope(level="atom", id="button", semanticRole="primary-action")


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


class CandidateChange(StrictModel):
    """One catalog-scoped visual mutation proposed by an untrusted model."""

    path: VisualPath
    value: str = Field(min_length=1)


class CandidatePatch(StrictModel):
    """A reviewable proposal; the engine, never the model, applies it to the current spec."""

    changes: list[CandidateChange] = Field(min_length=1, max_length=5)
    rationale: str = Field(min_length=1, max_length=1_000)


class Variant(StrictModel):
    id: str
    kind: Literal["exploit", "adjacent_explore", "wild_explore"]
    direction: str
    spec: dict[str, object]


class CandidateProposal(StrictModel):
    """A policy-labelled patch returned by GenerateCandidatePatches."""

    kind: Literal["exploit", "adjacent_explore", "wild_explore"]
    patch: CandidatePatch


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
    scope: AtomicScope = Field(default_factory=lambda: DEFAULT_BUTTON_SCOPE.model_copy(deep=True))
    context: DesignContext
    targetElementId: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    action: Literal[
        "manual_edit",
        "confirmed_critique",
        "explicit_attribute_feedback",
        "absolute_feedback",
        "pairwise_choice",
        "candidate_acceptance",
        "almost",
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

    @model_validator(mode="after")
    def scope_matches_the_current_component_catalog(self) -> "PreferenceEventRequest":
        if self.componentType == "Button" and self.scope.level != "atom":
            raise ValueError("Button preference events must use an atom-level scope.")
        return self


class PreferenceEventResponse(StrictModel):
    id: int
    createdAt: datetime


class RetrievedEvidence(StrictModel):
    id: int
    contextRelation: Literal["exact", "compatible", "global", "mismatch"]
    preferenceRelation: Literal["supporting", "conflicting", "unknown"]
    source: str
    scope: AtomicScope | None = None
    context: DesignContext | None = None
    evidence: PreferenceEvidence
    critique: str | None = None
    # This is a retrieval projection, not a second memory store.  It makes the
    # concrete design that received feedback available to the next generation.
    outcome: Literal["accepted", "almost", "rejected", "indifferent", "manual_edit"] | None = None
    observedAppearance: ButtonAppearance | None = None
    diff: list[SpecDiff] = []
    candidateId: str | None = None
    directives: list[AttributeDirective] = []
    parserInterpretation: Interpretation | None = None


class TasteBriefDecision(StrictModel):
    """The minimum auditable evidence slice that may enter a generation prompt."""

    eventId: int
    scope: AtomicScope | None = None
    contextRelation: Literal["exact", "compatible", "global", "mismatch"]
    preferenceRelation: Literal["supporting", "conflicting", "unknown"]
    source: str
    strength: Literal["weak", "moderate", "strong"]
    evidence: PreferenceEvidence
    directives: list[AttributeDirective] = []


class TasteBrief(StrictModel):
    version: Literal["itl.taste-brief/v1"] = "itl.taste-brief/v1"
    scope: AtomicScope
    context: DesignContext
    evidenceIds: list[int]
    decisions: list[TasteBriefDecision]


class MemoryQuery(StrictModel):
    context: DesignContext
    evidence: PreferenceEvidence = PreferenceEvidence()
    scope: AtomicScope = Field(default_factory=lambda: DEFAULT_BUTTON_SCOPE.model_copy(deep=True))


class MemoryResponse(StrictModel):
    evidence: list[RetrievedEvidence]

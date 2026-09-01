"""Typed HTTP models for the contextual refinement boundary and its subjects."""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, get_args

from pydantic import AfterValidator, BaseModel, Field, StringConstraints, model_validator

from itl_ai.refine.base import ContextRelation, EvidenceStrength, StrictModel, TasteOutcome
from itl_ai.refine.dimensions import (
    DIMENSION_SPACE_VERSION,
    DimensionCapability,
    TasteDimension,
    capabilities_for,
    validate_capability_manifests,
)

UI_SPEC_VERSION = "itl.ui/v1"
# A visual path is `/appearance/<token>`. Which tokens exist is a property of
# the selected component, not of this type: see COMPONENT_REGISTRY below.
VisualPath = Annotated[str, StringConstraints(pattern=r"^/appearance/[a-z][a-zA-Z0-9]*$")]
# `local` was the hardcoded client value for the first 95 judgments, which made
# session hold-out impossible. A placeholder is now refused at the boundary.
RESERVED_SESSION_IDS = frozenset({"local", "default", "session", "anonymous", "unknown"})


def _reject_reserved_session_id(value: str) -> str:
    if value.lower() in RESERVED_SESSION_IDS:
        raise ValueError("A judgment must carry a real session ID, not a placeholder.")
    return value


SessionId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{7,79}$"),
    AfterValidator(_reject_reserved_session_id),
]


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


class FormFieldAppearance(StrictModel):
    labelPlacement: Literal["above", "inline"]
    gap: Literal["tight", "regular", "loose"]
    hintTone: Literal["quiet", "strong"]


class FormFieldProps(StrictModel):
    label: str = Field(min_length=1)
    hint: str | None = None
    appearance: FormFieldAppearance


class SettingsFormProps(StrictModel):
    title: str = Field(min_length=1)
    description: str


class SettingsTemplateProps(StrictModel):
    title: str = Field(min_length=1)


class ProjectSettingsPageProps(StrictModel):
    title: str = Field(min_length=1)


class ModelIssue(StrictModel):
    code: str
    message: str
    path: str | None = None


class ErrorResponse(StrictModel):
    code: str
    message: str
    issues: list[ModelIssue] = []
    recoverable: bool = True


ProductKind = Literal["saas", "marketing", "commerce", "internal-tool", "editorial", "developer-tool"]
VisualTone = Literal["serious", "playful", "minimal", "expressive", "dense", "calm"]
Platform = Literal["web", "desktop", "mobile"]
Surface = Literal["toolbar", "hero", "form", "dashboard"]
SemanticRole = Literal["primary-action", "secondary-action"]
Density = Literal["compact", "comfortable"]
UsageState = Literal["default", "disabled", "loading"]
CorpusStratum = Literal["primary", "legacy"]


class ProjectContext(StrictModel):
    """A property of the project or session, never of the artifact.

    Round buttons in a playful product and square ones in a serious one are the
    same usage under two product tones. Without this axis they read as one
    context, and therefore as a contradiction the model cannot explain.
    """

    productKind: ProductKind
    visualTone: list[VisualTone] = Field(min_length=1, max_length=4)
    audience: str | None = Field(default=None, min_length=1, max_length=120)
    platform: Platform = "web"
    brandProfile: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]{0,60}$")


class UsageContext(StrictModel):
    """Where in a screen the stimulus sits. Independent of the product tone."""

    surface: Surface
    semanticRole: SemanticRole
    density: Density
    state: UsageState = "default"


class DesignContext(StrictModel):
    """The usage axis as the refinement clients still spell it on the wire."""

    role: SemanticRole
    surface: Surface
    density: Density
    state: UsageState = "default"

    def usage(self) -> UsageContext:
        return UsageContext(surface=self.surface, semanticRole=self.role, density=self.density, state=self.state)


AtomicDesignLevel = Literal["foundation", "atom", "molecule", "organism", "template", "page"]


class AtomicScope(StrictModel):
    """The exact Atomic Design subject a session is allowed to learn from."""

    level: AtomicDesignLevel
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    semanticRole: str | None = Field(default=None, min_length=1, max_length=120)


DEFAULT_BUTTON_SCOPE = AtomicScope(level="atom", id="button", semanticRole="primary-action")


def _appearance_vocabulary(model: type[BaseModel] | None) -> dict[str, tuple[str, ...]]:
    """Derive the finite token vocabulary from the props schema itself.

    A token therefore cannot exist for the model but not for the validator.
    """
    if model is None:
        return {}
    return {name: tuple(get_args(info.annotation)) for name, info in model.model_fields.items()}


@dataclass(frozen=True)
class ComponentEntry:
    """One registered component: what it is, what it may hold, what may change."""

    level: AtomicDesignLevel
    props: type[StrictModel]
    allowedChildTypes: tuple[str, ...] = ()
    # Only a subject with an appearance model is editable by the Taste Loop.
    appearance: type[StrictModel] | None = None
    scopeId: str | None = None
    orderedTokens: frozenset[str] = frozenset()

    @property
    def vocabulary(self) -> dict[str, tuple[str, ...]]:
        return _appearance_vocabulary(self.appearance)

    @property
    def isEditable(self) -> bool:
        """A subject is editable only if it has both a vocabulary and a scope."""
        return self.appearance is not None and self.scopeId is not None


COMPONENT_REGISTRY: dict[str, ComponentEntry] = {
    "Button": ComponentEntry(
        level="atom",
        props=ButtonProps,
        appearance=ButtonAppearance,
        scopeId="button",
        orderedTokens=frozenset({"size", "radius", "density", "fontWeight"}),
    ),
    "Input": ComponentEntry(level="atom", props=InputProps),
    "Badge": ComponentEntry(level="atom", props=BadgeProps),
    "Card": ComponentEntry(level="molecule", props=CardProps, allowedChildTypes=("Button", "Input", "Badge")),
    "FormField": ComponentEntry(
        level="molecule",
        props=FormFieldProps,
        allowedChildTypes=("Input",),
        appearance=FormFieldAppearance,
        scopeId="form-field",
        orderedTokens=frozenset({"gap", "hintTone"}),
    ),
    "SettingsForm": ComponentEntry(
        level="organism", props=SettingsFormProps, allowedChildTypes=("FormField", "Button", "Badge")
    ),
    "SettingsTemplate": ComponentEntry(
        level="template", props=SettingsTemplateProps, allowedChildTypes=("SettingsForm",)
    ),
    "ProjectSettingsPage": ComponentEntry(
        level="page", props=ProjectSettingsPageProps, allowedChildTypes=("SettingsTemplate",)
    ),
}
EditableComponentType = Literal["Button", "FormField"]
EDITABLE_COMPONENTS: dict[str, ComponentEntry] = {
    name: entry for name, entry in COMPONENT_REGISTRY.items() if entry.isEditable
}


def scope_for_component(component_type: str, semantic_role: str | None = None) -> AtomicScope:
    """The default learning subject for an editable component.

    A session may narrow the scope ID to one instance or role — a save button in
    settings is not the same subject as a hero call to action — but it may never
    move the subject to another Atomic level.
    """
    entry = EDITABLE_COMPONENTS[component_type]
    if entry.scopeId is None:
        raise KeyError(f"{component_type} is registered without a learning scope.")
    return AtomicScope(level=entry.level, id=entry.scopeId, semanticRole=semantic_role)


def level_for_component(component_type: str) -> AtomicDesignLevel:
    return EDITABLE_COMPONENTS[component_type].level


DEFAULT_EVENT_OUTCOMES: dict[str, TasteOutcome] = {
    "candidate_acceptance": "accepted",
    "almost": "almost",
    "rejection": "rejected",
    "indifference": "indifferent",
    "manual_edit": "manual_edit",
    "confirmed_critique": "manual_edit",
    "explicit_attribute_feedback": "manual_edit",
    "absolute_feedback": "manual_edit",
    "pairwise_choice": "accepted",
    "explore_more": "indifferent",
}


class PreferenceEvidence(StrictModel):
    likedPaths: list[VisualPath] = []
    dislikedPaths: list[VisualPath] = []
    lockedPaths: list[VisualPath] = []
    strength: EvidenceStrength = "moderate"


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
    target: EditableComponentType = "Button"
    prompt: str = Field(default="A primary action", min_length=1, max_length=4_000)
    sessionId: SessionId
    context: DesignContext
    projectContext: ProjectContext | None = None
    # Keep the Button default for the existing local laboratory, but never
    # replace an explicitly supplied atomic subject during retrieval.
    scope: AtomicScope = Field(default_factory=lambda: DEFAULT_BUTTON_SCOPE.model_copy(deep=True))


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
    sessionId: SessionId
    context: DesignContext
    projectContext: ProjectContext | None = None
    scope: AtomicScope = Field(default_factory=lambda: DEFAULT_BUTTON_SCOPE.model_copy(deep=True))


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

    sessionId: SessionId
    componentType: EditableComponentType = "Button"
    scope: AtomicScope = Field(default_factory=lambda: DEFAULT_BUTTON_SCOPE.model_copy(deep=True))
    context: DesignContext
    # The product tone belongs to the project or session, not to the artifact.
    # A judgment without one is read as `unspecified` and ranks below one with.
    projectContext: ProjectContext | None = None
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
    # New callers should send this explicit result. The compatibility mapping
    # below preserves historical local events while ensuring retrieval never
    # has an outcome-less decision.
    outcome: TasteOutcome | None = None
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
        """Keep one subject per scope so retrieval cannot silently merge them."""
        level = level_for_component(self.componentType)
        if self.scope.level != level:
            raise ValueError(f"{self.componentType} preference events must use a {level}-level scope.")
        if self.outcome is None:
            self.outcome = DEFAULT_EVENT_OUTCOMES[self.action]
        return self


class PreferenceEventResponse(StrictModel):
    id: int
    createdAt: datetime


class ObservedAppearance(StrictModel):
    """The catalog appearance of the component a person actually looked at."""

    componentType: EditableComponentType
    appearance: dict[str, str]


class ContextRelations(StrictModel):
    """Usage and product tone are compared independently, then summarized.

    Same usage under two product tones is `compatible`, not a contradiction:
    the system has an axis on which the two rows legitimately differ.
    """

    usage: ContextRelation
    project: ContextRelation
    overall: ContextRelation


class RetrievedEvidence(StrictModel):
    id: int
    contextRelation: ContextRelation
    relations: ContextRelations
    # Rows recorded before the acquisition contract required a real session ID,
    # a scope, an outcome and a project context are reported, never rewritten,
    # and never silently pooled with rows that carry all four.
    stratum: CorpusStratum
    preferenceRelation: Literal["supporting", "conflicting", "unknown"]
    source: str
    scope: AtomicScope | None = None
    context: DesignContext | None = None
    projectContext: ProjectContext | None = None
    evidence: PreferenceEvidence
    critique: str | None = None
    # This is a retrieval projection, not a second memory store.  It makes the
    # concrete design that received feedback available to the next generation.
    outcome: TasteOutcome
    observedAppearance: ObservedAppearance | None = None
    diff: list[SpecDiff] = []
    candidateId: str | None = None
    directives: list[AttributeDirective] = []
    parserInterpretation: Interpretation | None = None


class TasteStimulus(StrictModel):
    """The bounded visual treatment that was actually shown to the person."""

    componentType: EditableComponentType
    appearance: dict[str, str]
    candidateId: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]*$")


class TasteBriefDecision(StrictModel):
    """The minimum auditable evidence slice that may enter a generation prompt."""

    eventId: int
    scope: AtomicScope | None = None
    contextRelation: ContextRelation
    preferenceRelation: Literal["supporting", "conflicting", "unknown"]
    outcome: TasteOutcome
    # A row whose snapshot no longer holds a readable subject carries no
    # stimulus. An invented neutral appearance would be indistinguishable from
    # a real one in the prompt.
    stimulus: TasteStimulus | None = None
    source: str
    strength: EvidenceStrength
    directives: list[AttributeDirective] = []


class TasteBrief(StrictModel):
    version: Literal["itl.taste-brief/v3"] = "itl.taste-brief/v3"
    scope: AtomicScope
    context: DesignContext
    evidenceIds: list[int]
    decisions: list[TasteBriefDecision]


class DimensionSource(StrictModel):
    """Which components contributed to a shared reading, and through which events."""

    componentType: str
    eventIds: list[int]


class ComponentResidual(StrictModel):
    """An exception that does not generalize, kept as a statement of its own.

    "Angular everywhere, but pill is fine on chips" is a real taste statement.
    It is not an error term and must survive into the artifact.
    """

    componentType: str
    dimension: TasteDimension
    componentCoordinate: float
    sharedCoordinate: float
    delta: float
    isException: bool
    eventIds: list[int]


class DimensionEvidence(StrictModel):
    """One shared dimension, read through the queried component's own tokens."""

    dimension: TasteDimension
    token: str
    coordinate: float | None
    nearestValue: str | None
    support: int
    agreement: Literal["consistent", "contradictory", "unknown"]
    # A compiled preference that cannot name its evidence does not ship.
    eventIds: list[int]
    sources: list[DimensionSource]
    residual: ComponentResidual | None = None


class ComponentCapability(StrictModel):
    dimension: TasteDimension
    token: str
    path: str
    values: dict[str, float]


class ComponentManifest(StrictModel):
    """What part of the shared taste space this stimulus can express."""

    componentType: str
    level: AtomicDesignLevel
    dimensionSpaceVersion: Literal["itl.taste-dimensions/v1"] = DIMENSION_SPACE_VERSION
    capabilities: list[ComponentCapability]


class ManifestResponse(StrictModel):
    dimensionSpaceVersion: Literal["itl.taste-dimensions/v1"] = DIMENSION_SPACE_VERSION
    dimensions: list[TasteDimension]
    components: list[ComponentManifest]


class MemoryQuery(StrictModel):
    context: DesignContext
    projectContext: ProjectContext | None = None
    evidence: PreferenceEvidence = PreferenceEvidence()
    componentType: EditableComponentType = "Button"
    scope: AtomicScope = Field(default_factory=lambda: DEFAULT_BUTTON_SCOPE.model_copy(deep=True))


class MemoryResponse(StrictModel):
    evidence: list[RetrievedEvidence]
    dimensionSpaceVersion: Literal["itl.taste-dimensions/v1"] = DIMENSION_SPACE_VERSION
    # Evidence at the shared altitude. Event retrieval stays partitioned by
    # subject; this is the only channel on which a judgment about one component
    # is legible to another, and only where they declare the same dimension.
    dimensions: list[DimensionEvidence] = []


def _capability_model(capability: DimensionCapability) -> ComponentCapability:
    return ComponentCapability(
        dimension=capability.dimension,
        token=capability.token,
        path=capability.path,
        values=dict(capability.projection),
    )


def manifest_for_component(component_type: str) -> ComponentManifest:
    return ComponentManifest(
        componentType=component_type,
        level=EDITABLE_COMPONENTS[component_type].level,
        capabilities=[_capability_model(capability) for capability in capabilities_for(component_type)],
    )


validate_capability_manifests(
    {name: entry.vocabulary for name, entry in EDITABLE_COMPONENTS.items()},
    {name: entry.orderedTokens for name, entry in EDITABLE_COMPONENTS.items()},
)

"""Typed HTTP models for the contextual refinement boundary and its subjects."""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

UI_SPEC_VERSION = "itl.ui/v1"
# A visual path is `/appearance/<token>`. Which tokens exist is a property of
# the selected component, not of this type: see COMPONENT_REGISTRY below.
VisualPath = Annotated[str, StringConstraints(pattern=r"^/appearance/[a-z][a-zA-Z0-9]*$")]


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
        return self.appearance is not None


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
    assert entry.scopeId is not None
    return AtomicScope(level=entry.level, id=entry.scopeId, semanticRole=semantic_role)


def level_for_component(component_type: str) -> AtomicDesignLevel:
    return EDITABLE_COMPONENTS[component_type].level


TasteOutcome = Literal["accepted", "almost", "rejected", "indifferent", "manual_edit"]
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
    target: EditableComponentType = "Button"
    prompt: str = Field(default="A primary action", min_length=1, max_length=4_000)
    sessionId: str = Field(default="local", pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    context: DesignContext
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
    sessionId: str = Field(default="local", pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    context: DesignContext
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

    sessionId: str = Field(default="local", pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    componentType: EditableComponentType = "Button"
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
    contextRelation: Literal["exact", "compatible", "global", "mismatch"]
    preferenceRelation: Literal["supporting", "conflicting", "unknown"]
    outcome: TasteOutcome
    # A row whose snapshot no longer holds a readable subject carries no
    # stimulus. An invented neutral appearance would be indistinguishable from
    # a real one in the prompt.
    stimulus: TasteStimulus | None = None
    source: str
    strength: Literal["weak", "moderate", "strong"]
    directives: list[AttributeDirective] = []


class TasteBrief(StrictModel):
    version: Literal["itl.taste-brief/v3"] = "itl.taste-brief/v3"
    scope: AtomicScope
    context: DesignContext
    evidenceIds: list[int]
    decisions: list[TasteBriefDecision]


class MemoryQuery(StrictModel):
    context: DesignContext
    evidence: PreferenceEvidence = PreferenceEvidence()
    componentType: EditableComponentType = "Button"
    scope: AtomicScope = Field(default_factory=lambda: DEFAULT_BUTTON_SCOPE.model_copy(deep=True))


class MemoryResponse(StrictModel):
    evidence: list[RetrievedEvidence]

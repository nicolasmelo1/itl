"""Typed boundary models for the refinement API.

These models deliberately live in the Python service. The JSON fixtures under
``contracts/refine`` are the shared HTTP examples; neither application imports
the other application's runtime types.
"""

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


class GenerateSpecResponse(StrictModel):
    spec: dict[str, object]


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


class Variant(StrictModel):
    id: str
    kind: Literal["exploit", "adjacent_explore", "wild_explore"]
    spec: dict[str, object]


class GenerateVariantsResponse(StrictModel):
    variants: list[Variant]

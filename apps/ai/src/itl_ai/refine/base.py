"""Vocabulary shared by the wire models and the taste dimension space.

It lives apart from `models` so the dimension ontology can be typed without
importing the component registry that validates against it.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


TasteOutcome = Literal["accepted", "almost", "rejected", "indifferent", "manual_edit"]
EvidenceStrength = Literal["weak", "moderate", "strong"]
ContextRelation = Literal["exact", "compatible", "global", "mismatch"]

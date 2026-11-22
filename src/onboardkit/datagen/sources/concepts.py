"""Concept vocabulary: stable ids for the meaning of source columns."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

CONCEPTS_PATH = Path(__file__).with_name("concepts.yaml")

ValueType = Literal["string", "date", "money", "decimal", "enum"]


class Concept(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z_]+\.[a-z0-9_]+$")
    description: str = Field(min_length=1)
    value_type: ValueType


class ConceptCatalogue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    concepts: list[Concept]

    @model_validator(mode="after")
    def _ids_unique(self) -> ConceptCatalogue:
        ids = [c.id for c in self.concepts]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate concept ids: {duplicates}")
        return self

    def ids(self) -> set[str]:
        return {c.id for c in self.concepts}


def load_concepts(path: Path = CONCEPTS_PATH) -> ConceptCatalogue:
    with path.open(encoding="utf-8") as handle:
        return ConceptCatalogue.model_validate(yaml.safe_load(handle))

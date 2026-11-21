"""Shared row model, source profile, and exporter protocol.

Nothing here knows about a particular source: each source supplies a ``SourceProfile`` and a
projection from the truth, and the framework handles formatting, writing, and locating rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from onboardkit.datagen.sources.concepts import load_concepts
from onboardkit.datagen.sources.formatters import FORMATTERS
from onboardkit.datagen.truth.model import TruthFirm


@dataclass(frozen=True)
class TruthRefs:
    """Which truth entities a row stands for. Never written to an export."""

    person_ids: tuple[str, ...] = ()
    household_id: str | None = None
    account_id: str | None = None


@dataclass
class SourceRow:
    """One row of one table of one source, before formatting.

    ``values`` is keyed by concept id and holds typed values (``date``, ``Decimal``, ``str``,
    ``NameParts`` from the formatters module) so that mess can reason about real dates and amounts.
    """

    row_uid: str  # stable per dataset, for example "<source>:<table>:000123"
    source: str
    table: str
    values: dict[str, Any]
    refs: TruthRefs = field(default_factory=TruthRefs)


@dataclass(frozen=True)
class RowLocator:
    """Where a row landed, as a person opening the file would count it (1-based)."""

    file: str
    sheet: str | None
    row_number: int


@dataclass
class WriteResult:
    files: list[Path] = field(default_factory=list)
    locators: dict[str, RowLocator] = field(default_factory=dict)


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ColumnSpec(_Frozen):
    concept: str  # must exist in concepts.yaml
    header: str  # header text as the source writes it
    formatter: str = "passthrough"
    options: dict[str, Any] = Field(default_factory=dict)


class TableSpec(_Frozen):
    name: str
    file_name: str
    sheet_name: str | None = None  # spreadsheets only
    columns: list[ColumnSpec] = Field(min_length=1)
    preamble: list[str] = Field(default_factory=list)  # raw lines before the header
    trailer: list[str] = Field(default_factory=list)  # raw lines after the last row

    @model_validator(mode="after")
    def _unique_columns(self) -> TableSpec:
        concepts = [c.concept for c in self.columns]
        headers = [c.header for c in self.columns]
        if len(set(concepts)) != len(concepts):
            raise ValueError(f"table {self.name!r} repeats a concept")
        if len(set(headers)) != len(headers):
            raise ValueError(f"table {self.name!r} repeats a header")
        return self

    @property
    def header_line(self) -> int:
        """1-based line number of the header row."""
        return len(self.preamble) + 1


class SourceProfile(_Frozen):
    source: str
    file_type: Literal["csv", "xlsx"]
    encoding: str = "utf-8"
    delimiter: str = Field(default=",", min_length=1, max_length=1)
    line_ending: Literal["\n", "\r\n"] = "\n"
    tables: list[TableSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_references(self) -> SourceProfile:
        known = known_concepts()
        for table in self.tables:
            for column in table.columns:
                if column.concept not in known:
                    raise ValueError(
                        f"unknown concept {column.concept!r} in table {table.name!r}; "
                        "add it to concepts.yaml first"
                    )
                if column.formatter not in FORMATTERS:
                    raise ValueError(
                        f"unknown formatter {column.formatter!r}; available: {sorted(FORMATTERS)}"
                    )
        if len({t.name for t in self.tables}) != len(self.tables):
            raise ValueError("table names must be unique")
        return self

    def table(self, name: str) -> TableSpec:
        for table in self.tables:
            if table.name == name:
                return table
        raise KeyError(f"no table {name!r} in profile {self.source!r}")


@lru_cache(maxsize=1)
def known_concepts() -> frozenset[str]:
    return frozenset(load_concepts().ids())


class SourceExporter(Protocol):
    """What each concrete source implements."""

    profile: SourceProfile

    def project(self, firm: TruthFirm) -> list[SourceRow]: ...

    def write(self, rows: list[SourceRow], out_dir: Path) -> WriteResult: ...

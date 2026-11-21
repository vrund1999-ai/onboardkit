"""The mess contract: dataset container, events, context, and the interface every type follows."""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Protocol

from onboardkit.datagen.rng import derive_rng
from onboardkit.datagen.sources.base import SourceRow, TruthRefs
from onboardkit.datagen.truth.model import TruthFirm

SourceDataset = dict[str, dict[str, list[SourceRow]]]  # source -> table -> rows

Effect = Literal["entity_variant", "format_variant", "value_conflict", "structural"]
Severity = Literal["immaterial", "material"]
Ambiguity = Literal["low", "medium", "high"]


def group_by_table(rows_by_source: dict[str, list[SourceRow]]) -> SourceDataset:
    """Turn the flat per-source row lists of projection and coverage into a ``SourceDataset``."""
    data: SourceDataset = {}
    for source, rows in rows_by_source.items():
        tables: dict[str, list[SourceRow]] = defaultdict(list)
        for row in rows:
            tables[row.table].append(row)
        data[source] = dict(tables)
    return data


def flatten(data: SourceDataset) -> dict[str, list[SourceRow]]:
    """The inverse of ``group_by_table`` (tables in name order)."""
    return {
        source: [row for table in sorted(tables) for row in tables[table]]
        for source, tables in data.items()
    }


@dataclass(frozen=True)
class MessEvent:
    """One deliberate change (or one group of related changes) made by a mess type."""

    event_id: str  # "mess:<name>:<n>", sequential per type
    mess_type: str
    subtype: str  # for example "nickname" or "transposed_digits"
    source: str
    table: str
    row_uids: tuple[str, ...]  # rows affected
    concept: str | None  # concept changed, when the change is value-level
    before: str | None  # values rendered as text so events serialize cleanly
    after: str | None
    refs: TruthRefs
    effect: Effect
    severity: Severity | None = None
    ambiguity: Ambiguity | None = None


@dataclass
class MessContext:
    """What a mess type is given: its rate, seeded streams, and the truth to look things up in."""

    mess_name: str
    rate: float  # intensity * max_rate for this run
    root_seed: int
    firm: TruthFirm
    as_of_date: date
    _streams: dict[str, random.Random] = field(default_factory=dict, repr=False)
    _next_event: int = field(default=1, repr=False)

    def rng(self, source: str) -> random.Random:
        """This type's own stream for one source: ``derive_rng(seed, "mess", name, source)``."""
        if source not in self._streams:
            self._streams[source] = derive_rng(self.root_seed, "mess", self.mess_name, source)
        return self._streams[source]

    def event(
        self,
        *,
        subtype: str,
        source: str,
        table: str,
        row_uids: tuple[str, ...],
        effect: Effect,
        refs: TruthRefs,
        concept: str | None = None,
        before: str | None = None,
        after: str | None = None,
        severity: Severity | None = None,
        ambiguity: Ambiguity | None = None,
    ) -> MessEvent:
        """Create the next event with a sequential id for this type."""
        event = MessEvent(
            event_id=f"mess:{self.mess_name}:{self._next_event}",
            mess_type=self.mess_name,
            subtype=subtype,
            source=source,
            table=table,
            row_uids=row_uids,
            concept=concept,
            before=before,
            after=after,
            refs=refs,
            effect=effect,
            severity=severity,
            ambiguity=ambiguity,
        )
        self._next_event += 1
        return event


class MessType(Protocol):
    name: str  # registry key, for example "names"
    description: str
    touches: frozenset[str]  # concept ids this type may modify
    structural: bool  # True if it may add or remove rows
    max_rate: float  # share of eligible rows affected at intensity 1.0

    def apply(self, ctx: MessContext, data: SourceDataset) -> list[MessEvent]: ...

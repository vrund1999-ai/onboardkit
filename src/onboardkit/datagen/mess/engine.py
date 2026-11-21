"""Runs mess types in a fixed order and checks that each one did only what it declared."""

from __future__ import annotations

import copy
from collections.abc import Callable, Sequence
from typing import Any

from onboardkit.datagen.mess.base import MessContext, MessEvent, MessType, SourceDataset
from onboardkit.datagen.mess.registry import DEFAULT_REGISTRY, MessRegistry

RowKey = tuple[str, str, str]  # (source, table, row_uid)
Values = dict[RowKey, dict[str, Any]]


class MessContractError(RuntimeError):
    """A mess type changed something it did not declare, or did not explain a change."""


def _snapshot(data: SourceDataset) -> Values:
    return {
        (source, table, row.row_uid): copy.deepcopy(row.values)
        for source, tables in data.items()
        for table, rows in tables.items()
        for row in rows
    }


def _current(data: SourceDataset) -> Values:
    return {
        (source, table, row.row_uid): row.values
        for source, tables in data.items()
        for table, rows in tables.items()
        for row in rows
    }


def _check(mess: MessType, before: Values, data: SourceDataset, events: list[MessEvent]) -> None:
    after = _current(data)
    added = after.keys() - before.keys()
    removed = before.keys() - after.keys()
    if (added or removed) and not mess.structural:
        sample = sorted(added | removed)[0]
        verb = "added" if sample in added else "removed"
        raise MessContractError(
            f"mess type {mess.name!r} is not structural but {verb} row {sample[2]!r} "
            f"({len(added)} added, {len(removed)} removed)"
        )

    covered_rows = {(e.source, e.table, uid) for e in events for uid in e.row_uids}
    for key in sorted(added | removed):
        if key not in covered_rows:
            raise MessContractError(
                f"mess type {mess.name!r} changed the row set at {key[2]!r} without an event"
            )

    covered = {(e.source, e.table, uid, e.concept) for e in events for uid in e.row_uids}
    for key in sorted(after.keys() & before.keys()):
        old, new = before[key], after[key]
        for concept in sorted(old.keys() | new.keys()):
            if old.get(concept) == new.get(concept):
                continue
            if concept not in mess.touches:
                raise MessContractError(
                    f"mess type {mess.name!r} changed undeclared concept {concept!r} "
                    f"on row {key[2]!r}; declared: {sorted(mess.touches)}"
                )
            if (*key, concept) not in covered and (*key, None) not in covered:
                raise MessContractError(
                    f"mess type {mess.name!r} changed {concept!r} on row {key[2]!r} "
                    "without emitting an event for it"
                )


def _check_event_ids(mess: MessType, events: list[MessEvent]) -> None:
    expected = [f"mess:{mess.name}:{n}" for n in range(1, len(events) + 1)]
    if [e.event_id for e in events] != expected or any(e.mess_type != mess.name for e in events):
        raise MessContractError(
            f"mess type {mess.name!r} must emit sequential event ids "
            f"mess:{mess.name}:1..N (use ctx.event) with its own name as mess_type"
        )


def run_mess(
    data: SourceDataset,
    enabled: Sequence[str],
    ctx_factory: Callable[[MessType], MessContext],
    registry: MessRegistry = DEFAULT_REGISTRY,
) -> list[MessEvent]:
    """Apply the enabled types to ``data`` in place and return all events in execution order.

    The caller passes a copy of the projection when the original rows must stay untouched.
    """
    all_events: list[MessEvent] = []
    for mess in registry.ordered(list(enabled)):
        before = _snapshot(data)
        events = mess.apply(ctx_factory(mess), data)
        _check_event_ids(mess, events)
        _check(mess, before, data, events)
        all_events.extend(events)
    return all_events

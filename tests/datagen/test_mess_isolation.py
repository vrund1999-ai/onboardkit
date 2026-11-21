from typing import Any

import pytest

from onboardkit.datagen.config import MESS_TYPE_NAMES, resolve_config
from onboardkit.datagen.mess.base import MessEvent, SourceDataset
from onboardkit.datagen.mess.registry import DEFAULT_REGISTRY
from onboardkit.datagen.pipeline import build_rows

RowKey = tuple[str, str, str]
SIZE = 100
SEED = 42


def flat(data: SourceDataset) -> dict[RowKey, dict[str, Any]]:
    return {
        (source, table, row.row_uid): row.values
        for source, tables in data.items()
        for table, rows in tables.items()
        for row in rows
    }


def keys(event: MessEvent) -> list[RowKey]:
    return [(event.source, event.table, uid) for uid in event.row_uids]


def only(name: str) -> dict[str, Any]:
    return {"mess": {name: {"enabled": True, "intensity": 0.8}}}


@pytest.mark.parametrize("name", MESS_TYPE_NAMES)
def test_turning_one_type_on_changes_only_what_it_explains(name: str) -> None:
    mess = DEFAULT_REGISTRY.get(name)
    baseline = build_rows(resolve_config("clean", SIZE, SEED))
    run = build_rows(resolve_config("clean", SIZE, SEED, only(name)))
    assert baseline.firm == run.firm
    assert run.coverage_events == []
    assert run.mess_events
    assert {e.mess_type for e in run.mess_events} == {name}

    before, after = flat(baseline.data), flat(run.data)
    covered_rows = {key for e in run.mess_events for key in keys(e)}
    covered = {(*key, e.concept) for e in run.mess_events for key in keys(e)}
    differing = 0
    for key in sorted(before.keys() | after.keys()):
        if key not in before or key not in after:
            assert mess.structural, f"{name} changed the row set but is not structural"
            assert key in covered_rows
            differing += 1
            continue
        old, new = before[key], after[key]
        concepts = [c for c in old.keys() | new.keys() if old.get(c) != new.get(c)]
        differing += bool(concepts)
        for concept in concepts:
            assert concept in mess.touches, f"{name} changed {concept} on {key[2]}"
            assert (*key, concept) in covered or (*key, None) in covered
    assert differing > 0


def test_sources_a_type_does_not_report_on_are_identical_to_the_baseline() -> None:
    baseline = build_rows(resolve_config("clean", SIZE, SEED))
    for name in MESS_TYPE_NAMES:
        run = build_rows(resolve_config("clean", SIZE, SEED, only(name)))
        reported = {e.source for e in run.mess_events}
        for source in set(baseline.data) - reported:
            assert run.data[source] == baseline.data[source]

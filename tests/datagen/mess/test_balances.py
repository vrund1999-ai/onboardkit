import copy
import random
from collections import Counter
from datetime import date
from decimal import Decimal

import pytest
from mess_helpers import firm_of, projection

from onboardkit.datagen.mess.balances import (
    BOOK_WEIGHTS,
    IMMATERIAL,
    TOLERANCE_ABS,
    TOLERANCE_REL,
    VALUE_MAKERS,
    previous_quarter_end,
    tolerance,
    within_tolerance,
)
from onboardkit.datagen.mess.base import MessContext, MessEvent, SourceDataset, group_by_table
from onboardkit.datagen.mess.engine import run_mess
from onboardkit.datagen.mess.registry import DEFAULT_REGISTRY
from onboardkit.datagen.sources.base import SourceRow

AS_OF = date(2025, 12, 31)
ALL_SUBTYPES = {*BOOK_WEIGHTS, "stale_value"}


def run(
    size: int, rate: float, seed: int = 42
) -> tuple[SourceDataset, SourceDataset, list[MessEvent]]:
    firm = firm_of(size)
    original = group_by_table(copy.deepcopy(projection(firm)))
    data = group_by_table(copy.deepcopy(projection(firm)))
    events = run_mess(
        data, ["balances"], lambda mess: MessContext(mess.name, rate, seed, firm, AS_OF)
    )
    return original, data, events


def rows_by_uid(data: SourceDataset) -> dict[str, SourceRow]:
    return {r.row_uid: r for tables in data.values() for rows in tables.values() for r in rows}


def test_registered_with_story_settings() -> None:
    mess = DEFAULT_REGISTRY.get("balances")
    assert mess.max_rate == 0.25
    assert not mess.structural
    assert {
        "account.balance",
        "account.balance_as_of",
        "account.status",
        "account.type",
        "account.registration",
    } <= mess.touches
    assert sum(BOOK_WEIGHTS.values()) == pytest.approx(1.0)


def test_zero_intensity_changes_nothing() -> None:
    original, data, events = run(15, 0.0)
    assert events == []
    assert data == original


def test_every_subtype_appears_at_high_intensity_on_300_households() -> None:
    _, _, events = run(300, 0.25)
    assert {e.subtype for e in events} == ALL_SUBTYPES
    assert all(e.effect == "value_conflict" and e.mess_type == "balances" for e in events)


def test_every_event_has_a_severity_and_the_small_ones_are_immaterial() -> None:
    _, _, events = run(300, 0.25)
    assert all(e.severity in ("immaterial", "material") for e in events)
    for event in events:
        if event.subtype in IMMATERIAL:
            assert event.severity == "immaterial"
        elif event.subtype != "stale_value":
            assert event.severity == "material"
    immaterial = sum(e.severity == "immaterial" for e in events if e.source == "book_of_business")
    book = sum(e.source == "book_of_business" for e in events)
    assert 0.3 < immaterial / book < 0.6


def test_balances_stay_positive_with_two_places_across_seeds() -> None:
    for seed in (1, 2, 3):
        _, data, _ = run(60, 0.25, seed=seed)
        for tables in data.values():
            for rows in tables.values():
                for row in rows:
                    value = row.values.get("account.balance")
                    if value is None:
                        continue
                    assert isinstance(value, Decimal)
                    assert value > 0
                    assert value.is_finite()


def test_changed_book_balances_have_two_decimals() -> None:
    _, data, events = run(300, 0.25)
    now = rows_by_uid(data)
    value_events = [e for e in events if e.concept == "account.balance"]
    assert value_events
    for event in value_events:
        value = now[event.row_uids[0]].values["account.balance"]
        assert isinstance(value, Decimal)
        assert value > 0
        assert value == value.quantize(Decimal("0.01"))
        assert f"{value:f}" == event.after


def test_custodian_is_untouched_except_stale_values() -> None:
    original, data, events = run(300, 0.25)
    stale = {e.row_uids[0] for e in events if e.subtype == "stale_value"}
    assert stale
    before, now = rows_by_uid(original), rows_by_uid(data)
    for uid, row in now.items():
        if row.source != "custodian":
            continue
        if uid in stale:
            assert row.values["account.balance"] != before[uid].values["account.balance"]
            assert row.values["account.balance_as_of"] < before[uid].values["account.balance_as_of"]
            others = {k: v for k, v in row.values.items() if not k.startswith("account.balance")}
            assert others == {
                k: v for k, v in before[uid].values.items() if not k.startswith("account.balance")
            }
        else:
            assert row.values == before[uid].values


def test_stale_value_uses_the_previous_quarter_end_and_labels_by_two_percent() -> None:
    assert previous_quarter_end(date(2025, 12, 31)) == date(2025, 9, 30)
    assert previous_quarter_end(date(2025, 3, 31)) == date(2024, 12, 31)
    assert previous_quarter_end(date(2025, 5, 15)) == date(2025, 3, 31)
    _, data, events = run(300, 0.25)
    now = rows_by_uid(data)
    stale = [e for e in events if e.subtype == "stale_value"]
    assert {e.severity for e in stale} == {"material", "immaterial"}
    for event in stale:
        row = now[event.row_uids[0]]
        assert row.values["account.balance_as_of"] == date(2025, 9, 30)
        assert f"prior_as_of={date(2025, 9, 30)}" in (event.detail or "")
        before, after = Decimal(event.before or ""), Decimal(event.after or "")
        assert (event.severity == "material") == (abs(after - before) / before > Decimal("0.02"))


def test_at_most_one_event_per_account_and_source() -> None:
    _, _, events = run(300, 0.25)
    counts = Counter((e.source, e.refs.account_id) for e in events)
    assert counts
    assert max(counts.values()) == 1
    assert all(e.refs.account_id for e in events)


def test_value_events_record_the_tolerance_and_whether_it_is_met() -> None:
    assert Decimal("1.00") == TOLERANCE_ABS
    assert Decimal("0.001") == TOLERANCE_REL
    _, _, events = run(300, 0.25)
    value_events = [
        e for e in events if e.concept == "account.balance" or e.subtype == "stale_value"
    ]
    assert value_events
    for event in value_events:
        before, after = Decimal(event.before or ""), Decimal(event.after or "")
        assert "tolerance=max(1.00, 0.1%)" in (event.detail or "")
        assert f"within_tolerance={within_tolerance(before, after)}" in (event.detail or "")


@pytest.mark.parametrize(
    ("authoritative", "other", "expected"),
    [
        (Decimal("1000.00"), Decimal("1001.00"), True),
        (Decimal("1000.00"), Decimal("1001.01"), False),
        (Decimal("500000.00"), Decimal("500500.00"), True),  # 0.1 percent of 500,000 is 500
        (Decimal("500000.00"), Decimal("500500.01"), False),
        (Decimal("999.99"), Decimal("999.98"), True),
    ],
)
def test_tolerance_boundaries(authoritative: Decimal, other: Decimal, expected: bool) -> None:
    assert within_tolerance(authoritative, other) is expected
    assert tolerance(Decimal("50")) == Decimal("1.00")
    assert tolerance(Decimal("500000.00")) == Decimal("500.00")


def test_rounding_diff_is_within_one_dollar_and_small_drift_within_half_a_percent() -> None:
    original, _, events = run(300, 0.25)
    custodian = {
        r.refs.account_id: r.values["account.balance"] for r in original["custodian"]["accounts"]
    }
    for event in events:
        if event.subtype not in ("rounding_diff", "small_drift"):
            continue
        base = custodian[event.refs.account_id]
        assert Decimal(event.before or "") == base
        delta = abs(Decimal(event.after or "") - base)
        assert delta > 0
        if event.subtype == "rounding_diff":
            assert delta <= Decimal("1.00")
        else:
            assert delta <= base * Decimal("0.005") + Decimal("0.01")


def test_transposed_digits_swap_two_adjacent_digits() -> None:
    rng = random.Random(3)
    base = Decimal("18497.87")
    for _ in range(50):
        value = VALUE_MAKERS["transposed_digits"](base, rng)
        assert value is not None
        a, b = f"{base:f}", f"{value:f}"
        diffs = [i for i in range(len(a)) if a[i] != b[i]]
        assert len(diffs) == 2
        assert diffs[1] == diffs[0] + 1
        assert abs(value - base) > Decimal("1.00")
    assert VALUE_MAKERS["transposed_digits"](Decimal("1111.11"), rng) is None


def test_magnitude_error_is_limited_to_balances_under_200000() -> None:
    rng = random.Random(5)
    for _ in range(40):
        value = VALUE_MAKERS["magnitude_error"](Decimal("42000.50"), rng)
        assert value in (Decimal("420005.00"), Decimal("4200.05"))
    assert VALUE_MAKERS["magnitude_error"](Decimal("200000.00"), rng) is None
    _, _, events = run(300, 0.25)
    for event in events:
        if event.subtype == "magnitude_error":
            assert Decimal(event.before or "") < 200000


def test_type_mismatch_changes_the_type_in_book_and_crm_only() -> None:
    original, data, events = run(300, 0.25)
    before, now = rows_by_uid(original), rows_by_uid(data)
    type_events = [e for e in events if e.subtype == "type_mismatch"]
    assert {e.source for e in type_events} == {"book_of_business", "crm"}
    for event in type_events:
        old, new = before[event.row_uids[0]], now[event.row_uids[0]]
        assert old.values["account.type"].value == event.before
        assert new.values["account.type"].value == event.after
        assert event.before != event.after


def test_status_and_registration_mismatch_are_written_as_notes() -> None:
    original, data, events = run(300, 0.25)
    before, now = rows_by_uid(original), rows_by_uid(data)
    notes = [e for e in events if e.subtype in ("status_mismatch", "registration_mismatch")]
    assert {e.subtype for e in notes} == {"status_mismatch", "registration_mismatch"}
    for event in notes:
        old, new = before[event.row_uids[0]], now[event.row_uids[0]]
        assert event.source == "book_of_business"
        assert not old.values["meta.notes"]
        assert new.values["meta.notes"]
        if event.subtype == "status_mismatch":
            assert new.values["meta.notes"] in ("Closed per client", "Active, reopened")
        else:
            assert new.values["meta.notes"].startswith("Sole owner: ")


def test_no_other_values_change_and_row_sets_are_equal() -> None:
    original, data, events = run(300, 0.25)
    before, now = rows_by_uid(original), rows_by_uid(data)
    assert before.keys() == now.keys()
    changed = sum(before[uid].values != now[uid].values for uid in before)
    assert changed == len({(e.source, e.row_uids[0]) for e in events})


def test_same_seed_same_events_and_other_seed_differs() -> None:
    assert run(60, 0.25)[2] == run(60, 0.25)[2]
    assert run(60, 0.25, seed=1)[2] != run(60, 0.25, seed=2)[2]

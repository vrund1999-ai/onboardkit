import copy
import random
from datetime import date

import pytest
from mess_helpers import firm_of, projection

import onboardkit.datagen.mess.names as names_module
from onboardkit.datagen.mess.base import MessContext, MessEvent, SourceDataset, group_by_table
from onboardkit.datagen.mess.engine import run_mess
from onboardkit.datagen.mess.names import (
    AMBIGUITY,
    OWNERS,
    WEIGHTS,
    NamesMess,
    _initial_only,
    _nickname,
    _RowContext,
    _suffix_change,
    _typo_word,
    nicknames,
)
from onboardkit.datagen.mess.registry import DEFAULT_REGISTRY
from onboardkit.datagen.sources.base import SourceRow, TruthRefs
from onboardkit.datagen.sources.formatters import NameParts, apply_formatter
from onboardkit.datagen.truth.model import TruthFirm

AS_OF = date(2025, 12, 31)


def run(firm: TruthFirm, rate: float, seed: int = 42) -> tuple[SourceDataset, list[MessEvent]]:
    data = group_by_table(copy.deepcopy(projection(firm)))
    events = run_mess(
        data,
        ["names"],
        lambda mess: MessContext(mess.name, rate, seed, firm, AS_OF),
    )
    return data, events


def eligible_rows(data: SourceDataset) -> int:
    return sum(
        1
        for tables in data.values()
        for rows in tables.values()
        for row in rows
        if any(row.values.get(c) not in (None, "", []) for c in NamesMess.touches)
    )


def test_registered_under_its_name_with_story_settings() -> None:
    mess = DEFAULT_REGISTRY.get("names")
    assert mess.max_rate == 0.35
    assert not mess.structural
    assert mess.touches == {
        "person.first_name",
        "person.last_name",
        "person.suffix",
        "account.owner_names",
        "account.registration",
        "household.name",
    }


def test_weights_sum_to_one_and_every_subtype_has_an_ambiguity() -> None:
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)
    assert set(WEIGHTS) == set(AMBIGUITY) == set(names_module.HANDLERS)


def test_zero_rate_changes_nothing() -> None:
    firm = firm_of(15)
    before = group_by_table(copy.deepcopy(projection(firm)))
    data, events = run(firm, 0.0)
    assert events == []
    assert data == before


def test_affected_share_matches_rate_on_300_households() -> None:
    firm = firm_of(300)
    for rate in (0.35, 0.175):
        data, events = run(firm, rate)
        affected = {(e.source, e.row_uids[0]) for e in events}
        share = len(affected) / eligible_rows(data)
        assert share == pytest.approx(rate, abs=0.05)


def test_every_subtype_appears_at_high_intensity() -> None:
    _, events = run(firm_of(300), 1.0)
    assert {e.subtype for e in events} == set(WEIGHTS)


def test_events_are_complete_and_no_variant_equals_the_original() -> None:
    _, events = run(firm_of(300), 0.5)
    assert events
    for event in events:
        assert event.mess_type == "names"
        assert event.effect == "entity_variant"
        assert event.concept in NamesMess.touches
        assert event.before != event.after
        assert event.after is not None or event.before is not None
        assert event.ambiguity in ("low", "medium", "high")
        assert event.row_uids and event.refs.person_ids


def test_values_in_the_dataset_match_the_events() -> None:
    firm = firm_of(60)
    original = group_by_table(copy.deepcopy(projection(firm)))
    data, events = run(firm, 0.5)
    changed = 0
    for source, tables in data.items():
        for table, rows in tables.items():
            for row, old in zip(rows, original[source][table], strict=True):
                changed += row.values != old.values
    assert changed == len({(e.source, e.row_uids[0]) for e in events})


def test_custodian_owner_names_change_one_element_and_never_by_case() -> None:
    data, events = run(firm_of(300), 1.0)
    owner_events = [e for e in events if e.concept == OWNERS]
    assert owner_events
    assert all(e.subtype != "case_change" for e in owner_events)
    assert all(e.source == "custodian" for e in owner_events)
    for tables in data.values():
        for row in tables.get("accounts", []):
            owners = row.values.get(OWNERS)
            if owners:
                assert all(isinstance(o, NameParts) for o in owners)


def test_order_swap_swaps_both_parts_of_a_contact() -> None:
    firm = firm_of(300)
    original = {r.row_uid: r for r in projection(firm)["crm"]}
    data, events = run(firm, 1.0)
    swapped = [e for e in events if e.subtype == "order_swap" and e.concept == "person.first_name"]
    assert swapped
    for event in swapped:
        row = next(r for r in data["crm"]["contacts"] if r.row_uid == event.row_uids[0])
        old = original[row.row_uid]
        assert row.values["person.first_name"] == old.values["person.last_name"]
        assert row.values["person.last_name"] == old.values["person.first_name"]
        partner = [
            e for e in events if e.row_uids == event.row_uids and e.concept == "person.last_name"
        ]
        assert len(partner) == 1


def test_typos_keep_the_first_letter_and_change_one_character() -> None:
    rng = random.Random(1)
    for word in ["Smith", "Arnold", "Wesley", "Kim", "McDonald", "NORRIS", "O'Brien"]:
        for _ in range(300):
            variant = _typo_word(word, rng)
            assert variant is not None
            assert variant != word
            assert variant[0] == word[0]
            assert abs(len(variant) - len(word)) <= 1
    assert _typo_word("Al", rng) is None


def test_typo_events_never_alter_the_first_letter_of_a_surname() -> None:
    _, events = run(firm_of(300), 1.0)
    surname_events = [e for e in events if e.subtype == "typo" and e.concept == "person.last_name"]
    assert surname_events
    assert all(e.before and e.after and e.before[0] == e.after[0] for e in surname_events)


def person_row(first: str, last: str, suffix: str | None = None) -> SourceRow:
    return SourceRow(
        row_uid="crm:contacts:x",
        source="crm",
        table="contacts",
        values={"person.first_name": first, "person.last_name": last, "person.suffix": suffix},
        refs=TruthRefs(person_ids=("P-00001",), household_id="HH-0001"),
    )


def context_for(row: SourceRow, firm: TruthFirm | None = None) -> _RowContext:
    firm = firm or firm_of(15)
    people = firm.people_by_id()
    members = [people[m] for m in firm.households_by_id()["HH-0001"].member_ids]
    return _RowContext(row, members, members)


def test_readme_example_pair_can_be_produced() -> None:
    initial_row = person_row("John", "Smith")
    (initial,) = _initial_only(context_for(initial_row), random.Random(1))
    initial.apply()
    first = apply_formatter(
        "name_first_last",
        NameParts(
            str(initial_row.values["person.first_name"]),
            str(initial_row.values["person.last_name"]),
        ),
        {},
    )
    assert first == "J. Smith"

    suffix_row = person_row("John", "Smith")
    (suffix,) = _suffix_change(context_for(suffix_row), random.Random(1))
    suffix.apply()
    second = apply_formatter(
        "name_first_last",
        NameParts("John", "Smith", suffix=str(suffix_row.values["person.suffix"])),
        {},
    )
    assert second == "John Smith Jr."


def test_nickname_uses_the_table_and_falls_back_to_initial_only() -> None:
    assert len(nicknames()) >= 60
    row = person_row("Robert", "Smith")
    (change,) = _nickname(context_for(row), random.Random(3))
    assert change.after in {"Bob", "Rob", "Bobby"}
    assert change.subtype == ""

    (fallback,) = _nickname(context_for(person_row("Zephyr", "Smith")), random.Random(3))
    assert fallback.after == "Z."
    assert fallback.subtype == "initial_only"


def test_high_ambiguity_when_a_household_has_two_members_with_the_same_initial() -> None:
    firm = firm_of(15)
    household = firm.households_by_id()["HH-0001"]
    first_two = list(household.member_ids[:2])
    people = [
        p.model_copy(update={"first_name": "Jordan", "last_name": "Rivera"})
        if p.person_id in first_two
        else p
        for p in firm.people
    ]
    clashing = firm.model_copy(update={"people": tuple(people)})
    row = person_row("Jordan", "Rivera")
    row.refs = TruthRefs(person_ids=(first_two[0],), household_id="HH-0001")
    row_context = context_for(row, clashing)
    (change,) = _initial_only(row_context, random.Random(1))
    assert change.ambiguity == "high"

    # A different household member with another initial is not a clash.
    other = person_row("Quinn", "Rivera")
    other.refs = TruthRefs(person_ids=(first_two[0],), household_id="HH-0001")
    (alone,) = _initial_only(context_for(other, clashing), random.Random(1))
    assert alone.ambiguity is None


def test_hyphen_events_are_high_and_clash_events_are_labelled() -> None:
    _, events = run(firm_of(300), 1.0)
    assert {e.ambiguity for e in events if e.subtype == "hyphen_or_maiden"} == {"high"}
    assert any(e.subtype == "initial_only" and e.ambiguity == "high" for e in events)


def test_same_seed_same_events_and_other_seed_differs() -> None:
    firm = firm_of(60)
    assert run(firm, 0.35)[1] == run(firm, 0.35)[1]
    assert run(firm, 0.35, seed=1)[1] != run(firm, 0.35, seed=2)[1]


def test_original_projection_and_truth_are_not_touched() -> None:
    firm = firm_of(15)
    before = firm.model_dump_json()
    rows = projection(firm)
    snapshot = copy.deepcopy(rows)
    run(firm, 1.0)
    assert firm.model_dump_json() == before
    assert rows == snapshot


def test_nickname_data_is_generic() -> None:
    table = nicknames()
    assert all(
        options and formal not in {o.lower() for o in options} for formal, options in table.items()
    )

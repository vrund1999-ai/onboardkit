from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from onboardkit.datagen.answer_keys import entity_matches as em
from onboardkit.datagen.answer_keys.entity_matches import (
    ENTITY_GROUPS_FILE,
    ENTITY_MATCHES_FILE,
    GROUP_HEADER,
    MATCH_HEADER,
    UNSEEN_FILE,
    Membership,
    derive_groups,
    derive_memberships,
    event_difficulty,
    expected_pairs,
    write_entity_matches,
)
from onboardkit.datagen.answer_keys.provenance import (
    PROVENANCE_FILE,
    PROVENANCE_HEADER,
    write_provenance,
)
from onboardkit.datagen.answer_keys.writer import read_table
from onboardkit.datagen.config import resolve_config
from onboardkit.datagen.mess.base import MessEvent
from onboardkit.datagen.pipeline import DatasetResult, build_rows, generate_dataset
from onboardkit.datagen.sources.base import TruthRefs

WRITERS = [write_provenance, write_entity_matches]


def make(tmp_path: Path, preset: str, size: str | int = "sample", seed: int = 42) -> DatasetResult:
    return generate_dataset(
        resolve_config(preset, size, seed), tmp_path, answer_key_writers=WRITERS
    )


def event(
    event_id: str,
    row_uids: tuple[str, ...],
    *,
    mess_type: str = "names",
    subtype: str = "nickname",
    effect: Any = "entity_variant",
    concept: str | None = "person.first_name",
    ambiguity: Any = "low",
) -> MessEvent:
    return MessEvent(
        event_id=event_id,
        mess_type=mess_type,
        subtype=subtype,
        source="crm",
        table="contacts",
        row_uids=row_uids,
        concept=concept,
        before=None,
        after=None,
        refs=TruthRefs(),
        effect=effect,
        ambiguity=ambiguity,
    )


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"ambiguity": "low"}, "moderate"),
        ({"ambiguity": "medium"}, "moderate"),
        ({"ambiguity": "high"}, "hard"),
        (
            {"effect": "format_variant", "concept": "account.number", "ambiguity": "low"},
            "moderate",
        ),
        (
            {"effect": "format_variant", "concept": "person.date_of_birth", "ambiguity": "high"},
            "hard",
        ),
        ({"effect": "format_variant", "concept": "person.phone", "ambiguity": "low"}, None),
        ({"effect": "format_variant", "concept": "person.client_since", "ambiguity": "high"}, None),
        ({"effect": "value_conflict", "concept": "account.balance", "ambiguity": None}, None),
        ({"mess_type": "households", "subtype": "split", "effect": "structural"}, "hard"),
        ({"mess_type": "households", "subtype": "duplicate", "effect": "structural"}, "hard"),
        ({"mess_type": "households", "subtype": "missing", "effect": "structural"}, "moderate"),
    ],
)
def test_each_event_category_maps_to_one_difficulty(
    kwargs: dict[str, Any], expected: str | None
) -> None:
    assert event_difficulty(event("mess:x:1", ("r",), **kwargs)) == expected


def person(pid: str, household: str, first: str, last: str) -> SimpleNamespace:
    return SimpleNamespace(person_id=pid, household_id=household, first_name=first, last_name=last)


def record(uid: str, source: str, row: int, people: str, household: str, account: str) -> list[str]:
    cells = {
        "row_uid": uid,
        "source": source,
        "table": "t",
        "file": f"{source}/f.csv",
        "sheet": "",
        "row_number": str(row),
        "person_ids": people,
        "household_id": household,
        "account_id": account,
        "source_keys": "",
        "origin": "projected",
    }
    return [cells[name] for name in PROVENANCE_HEADER]


@pytest.fixture
def mini(monkeypatch: pytest.MonkeyPatch) -> list[Membership]:
    """A hand-built dataset: a joint account, a duplicate household, a split, a nickname."""
    people = (
        person("P-1", "HH-1", "Robert", "Lane"),  # joint account owners
        person("P-2", "HH-1", "Linda", "Lane"),
        person("P-3", "HH-2", "John", "Moss"),  # confusable pair: same initial and surname
        person("P-4", "HH-2", "Jane", "Moss"),
        person("P-5", "HH-3", "Ana", "Vega"),  # split off from HH-3
    )
    records = [
        record("custodian:1", "custodian", 4, "P-1|P-2", "HH-1", "ACCT-1"),
        record("crm:1", "crm", 2, "P-1", "HH-1", ""),
        record("crm:1-dup", "crm", 9, "P-1", "HH-1", ""),  # duplicate household row
        record("crm:2", "crm", 3, "P-2", "HH-1", ""),
        record("crm:3", "crm", 4, "P-3", "HH-2", ""),
        record("crm:4", "crm", 5, "P-4", "HH-2", ""),
        record("crm:5", "crm", 6, "P-5", "HH-3", ""),  # moved by a split
        record("book:stale", "book_of_business", 7, "P-9", "HH-9", ""),  # stale extra
    ]
    events = [
        event("mess:households:1", ("crm:1-dup",), mess_type="households", subtype="duplicate",
              effect="structural", concept=None, ambiguity=None),
        event("mess:households:2", ("crm:5",), mess_type="households", subtype="split",
              effect="structural", concept=None, ambiguity=None),
        event("mess:names:1", ("crm:2",)),  # nickname on Linda's row
        event("mess:names:2", ("crm:3",), ambiguity="medium"),  # name variant, confusable person
        event("mess:balances:1", ("custodian:1",), mess_type="balances", effect="value_conflict",
              concept="account.balance", ambiguity=None),
    ]  # fmt: skip
    context = SimpleNamespace(firm=SimpleNamespace(people=people), mess_events=events)
    monkeypatch.setattr(em, "build_provenance", lambda _: (records, []))
    return derive_memberships(context)  # type: ignore[arg-type]


def of(memberships: list[Membership], entity_type: str, truth_id: str) -> list[Membership]:
    return [m for m in memberships if (m.entity_type, m.truth_id) == (entity_type, truth_id)]


def test_a_joint_account_row_joins_each_owner_and_one_account_group(mini: list[Membership]) -> None:
    assert {m.row_uid for m in of(mini, "account", "ACCT-1")} == {"custodian:1"}
    for owner in ("P-1", "P-2"):
        assert "custodian:1" in {m.row_uid for m in of(mini, "person", owner)}
    assert "custodian:1" in {m.row_uid for m in of(mini, "household", "HH-1")}


def test_stale_rows_have_no_account_membership(mini: list[Membership]) -> None:
    stale = [m for m in mini if m.row_uid == "book:stale"]
    assert {m.entity_type for m in stale} == {"person", "household"}


def test_duplicate_household_is_one_group_spanning_both_rows(mini: list[Membership]) -> None:
    group = of(mini, "household", "HH-1")
    assert {"crm:1", "crm:1-dup", "crm:2", "custodian:1"} <= {m.row_uid for m in group}
    dup = next(m for m in group if m.row_uid == "crm:1-dup")
    assert (dup.difficulty, dup.variant_events) == ("hard", ("mess:households:1",))
    assert next(m for m in group if m.row_uid == "crm:1").difficulty == "easy"
    (row,) = (r for r in derive_groups(mini) if r[:2] == ["household", "HH-1"])
    assert row[3] == "crm|custodian"
    assert row[4] == "hard"  # the hardest member decides


def test_split_household_member_is_hard(mini: list[Membership]) -> None:
    (member,) = of(mini, "person", "P-5")
    assert (member.difficulty, member.variant_events) == ("hard", ("mess:households:2",))


def test_nickname_variant_is_moderate_and_recorded(mini: list[Membership]) -> None:
    (member,) = (m for m in of(mini, "person", "P-2") if m.row_uid == "crm:2")
    assert (member.difficulty, member.variant_events) == ("moderate", ("mess:names:1",))
    assert [m.difficulty for m in of(mini, "person", "P-2") if m.row_uid == "custodian:1"] == [
        "easy"
    ]


def test_confusable_people_are_hard_only_when_a_name_was_varied(mini: list[Membership]) -> None:
    varied = next(m for m in of(mini, "person", "P-3"))
    untouched = next(m for m in of(mini, "person", "P-4"))
    assert varied.difficulty == "hard"  # name variant on a confusable person
    assert untouched.difficulty == "easy"  # same collision, nothing varied


def test_balance_conflicts_do_not_change_identity_difficulty(mini: list[Membership]) -> None:
    row = next(m for m in of(mini, "account", "ACCT-1"))
    assert (row.difficulty, row.variant_events) == ("easy", ())


def test_expected_pairs_are_unordered_distinct_rows(mini: list[Membership]) -> None:
    pairs = list(expected_pairs(mini, "person"))
    assert ("crm:1", "crm:1-dup") in pairs
    assert ("crm:1", "custodian:1") in pairs
    assert all(a < b for a, b in pairs)
    assert len(pairs) == len(set(pairs))
    assert ("crm:3", "crm:4") not in pairs  # different people
    household_pairs = set(expected_pairs(mini, "household"))
    assert ("crm:1", "crm:1-dup") in household_pairs
    assert list(expected_pairs(mini, "account")) == []  # one row only: no pairs


def test_groups_count_rows_and_sources(mini: list[Membership]) -> None:
    groups = {tuple(r[:2]): r for r in derive_groups(mini)}
    assert groups[("account", "ACCT-1")] == ["account", "ACCT-1", "1", "custodian", "easy"]
    assert groups[("person", "P-1")][2] == "3"


# ---- generated datasets ----


@pytest.fixture(scope="module")
def nightmare(tmp_path_factory: pytest.TempPathFactory) -> DatasetResult:
    return make(tmp_path_factory.mktemp("em"), "nightmare", 150, 3)


def truth_file(result: DatasetResult, name: str) -> list[dict[str, str]]:
    return read_table(result.path / "truth" / name)


def test_files_have_the_documented_columns(nightmare: DatasetResult) -> None:
    matches = truth_file(nightmare, ENTITY_MATCHES_FILE)
    groups = truth_file(nightmare, ENTITY_GROUPS_FILE)
    assert tuple(matches[0]) == MATCH_HEADER
    assert tuple(groups[0]) == GROUP_HEADER
    assert {m["difficulty"] for m in matches} == {"easy", "moderate", "hard"}
    assert {g["entity_type"] for g in groups} == {"person", "household", "account"}
    assert (nightmare.path / "truth" / UNSEEN_FILE).is_file()


def test_every_referenced_row_appears_for_each_entity_type(nightmare: DatasetResult) -> None:
    provenance = truth_file(nightmare, PROVENANCE_FILE)
    matches = truth_file(nightmare, ENTITY_MATCHES_FILE)
    member_rows = {(m["entity_type"], m["row_uid"]) for m in matches}
    for record_ in provenance:
        if record_["person_ids"]:
            assert ("person", record_["row_uid"]) in member_rows
        if record_["household_id"]:
            assert ("household", record_["row_uid"]) in member_rows
        assert (("account", record_["row_uid"]) in member_rows) == bool(record_["account_id"])
    expected = sum(
        len([p for p in r["person_ids"].split("|") if p])
        + bool(r["household_id"])
        + bool(r["account_id"])
        for r in provenance
    )
    assert len(matches) == expected  # no extra and no missing memberships


def test_stale_extras_are_not_in_account_groups(nightmare: DatasetResult) -> None:
    stale = {
        r["row_uid"] for r in truth_file(nightmare, PROVENANCE_FILE) if r["origin"] == "stale_extra"
    }
    assert stale
    for m in truth_file(nightmare, ENTITY_MATCHES_FILE):
        if m["row_uid"] in stale:
            assert m["entity_type"] != "account"


def test_duplicate_and_split_households_stay_one_group_across_crm_ids(
    nightmare: DatasetResult,
) -> None:
    provenance = {r["row_uid"]: r for r in truth_file(nightmare, PROVENANCE_FILE)}
    matches = [
        m for m in truth_file(nightmare, ENTITY_MATCHES_FILE) if m["entity_type"] == "household"
    ]
    for origin in ("duplicate", "split"):
        rows = [r for r in provenance.values() if r["origin"] == origin]
        assert rows, origin
        for row in rows:
            group = [m for m in matches if m["truth_id"] == row["household_id"]]
            crm_ids = {
                provenance[m["row_uid"]]["source_keys"].split("household_id=")[1]
                for m in group
                if m["source"] == "crm"
                and "household_id=" in provenance[m["row_uid"]]["source_keys"]
            }
            assert len(crm_ids) >= 2, (origin, row["row_uid"])
            assert row["row_uid"] in {m["row_uid"] for m in group}


def test_rows_without_variant_events_are_easy_and_others_are_not(nightmare: DatasetResult) -> None:
    for m in truth_file(nightmare, ENTITY_MATCHES_FILE):
        assert (m["difficulty"] == "easy") == (m["variant_events"] == "")


def test_variant_events_exist_in_the_mess_log(nightmare: DatasetResult) -> None:
    built = build_rows(nightmare.config)
    known = {e.event_id for e in built.mess_events}
    for m in truth_file(nightmare, ENTITY_MATCHES_FILE):
        for event_id in filter(None, m["variant_events"].split("|")):
            assert event_id in known


def test_seen_plus_not_exported_equals_truth(nightmare: DatasetResult) -> None:
    built = build_rows(nightmare.config)
    truth = {
        "person": {p.person_id for p in built.firm.people},
        "household": {h.household_id for h in built.firm.households},
        "account": {a.account_id for a in built.firm.accounts},
    }
    groups = truth_file(nightmare, ENTITY_GROUPS_FILE)
    unseen = truth_file(nightmare, UNSEEN_FILE)
    assert unseen
    for entity_type, ids in truth.items():
        seen = {g["truth_id"] for g in groups if g["entity_type"] == entity_type}
        missing = {u["truth_id"] for u in unseen if u["entity_type"] == entity_type}
        assert seen | missing == ids
        assert not seen & missing
    referenced = {
        p
        for rows in built.data.values()
        for rs in rows.values()
        for r in rs
        for p in r.refs.person_ids
    }
    assert {u["truth_id"] for u in unseen if u["entity_type"] == "person"}.isdisjoint(referenced)


@pytest.mark.parametrize("seed", [1, 2, 42])
def test_clean_datasets_are_all_easy_and_fully_seen(tmp_path: Path, seed: int) -> None:
    result = make(tmp_path, "clean", 200, seed)
    groups = truth_file(result, ENTITY_GROUPS_FILE)
    assert {g["max_difficulty"] for g in groups} == {"easy"}
    assert {m["difficulty"] for m in truth_file(result, ENTITY_MATCHES_FILE)} == {"easy"}
    assert truth_file(result, UNSEEN_FILE) == []
    built = build_rows(result.config)
    counts = {
        t: sum(g["entity_type"] == t for g in groups) for t in ("person", "household", "account")
    }
    assert counts == {
        "person": len(built.firm.people),
        "household": len(built.firm.households),
        "account": len(built.firm.accounts),
    }


def test_files_are_byte_identical_across_runs(tmp_path: Path) -> None:
    first = make(tmp_path / "a", "nightmare", 60, 9)
    second = make(tmp_path / "b", "nightmare", 60, 9)
    for name in (ENTITY_MATCHES_FILE, ENTITY_GROUPS_FILE, UNSEEN_FILE):
        data = (first.path / "truth" / name).read_bytes()
        assert data == (second.path / "truth" / name).read_bytes()
        assert b"\r" not in data


def test_answer_key_exists_only_under_truth(tmp_path: Path) -> None:
    result = make(tmp_path, "typical")
    for path in (result.path / "exports").rglob("*"):
        if path.is_file():
            text = path.read_bytes()
            assert b"entity_matches" not in text
            assert b"ACCT-" not in text
    assert (result.path / "truth" / ENTITY_MATCHES_FILE).is_file()

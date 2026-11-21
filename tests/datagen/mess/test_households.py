import copy
import csv
from collections import Counter
from datetime import date
from pathlib import Path

import pytest
from mess_helpers import firm_of, projection

from onboardkit.datagen.mess.base import MessContext, MessEvent, SourceDataset, group_by_table
from onboardkit.datagen.mess.engine import run_mess
from onboardkit.datagen.mess.households import DUPLICATE_SUFFIX, WEIGHTS
from onboardkit.datagen.mess.registry import DEFAULT_REGISTRY
from onboardkit.datagen.sources.base import SourceRow
from onboardkit.datagen.sources.book_of_business import BookOfBusinessExporter
from onboardkit.datagen.sources.crm import CrmExporter
from onboardkit.datagen.truth.builder import build_firm
from onboardkit.datagen.truth.model import HouseholdRole, TruthFirm
from onboardkit.datagen.truth.profile import load_profile

AS_OF = date(2025, 12, 31)
Run = tuple[TruthFirm, SourceDataset, SourceDataset, list[MessEvent]]


def run(firm: TruthFirm, rate: float, seed: int = 42) -> Run:
    original = group_by_table(copy.deepcopy(projection(firm)))
    data = group_by_table(copy.deepcopy(projection(firm)))
    events = run_mess(
        data, ["households"], lambda mess: MessContext(mess.name, rate, seed, firm, AS_OF)
    )
    return firm, original, data, events


@pytest.fixture(scope="module")
def full() -> Run:
    return run(firm_of(60), 1.0)


def contacts(data: SourceDataset) -> dict[str, SourceRow]:
    return {r.row_uid: r for r in data["crm"]["contacts"]}


def of_subtype(events: list[MessEvent], subtype: str) -> list[MessEvent]:
    return [e for e in events if e.subtype == subtype]


def test_registered_with_story_settings() -> None:
    mess = DEFAULT_REGISTRY.get("households")
    assert mess.structural
    assert mess.max_rate == 0.15
    assert mess.touches == {
        "household.source_id",
        "household.name",
        "person.source_id",
        "person.household_role",
        "household.advisor",
    }
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_zero_intensity_adds_changes_and_removes_nothing() -> None:
    _, original, data, events = run(firm_of(15), 0.0)
    assert events == []
    assert data == original


def test_all_subtypes_occur_at_full_rate(full: Run) -> None:
    events = full[3]
    assert {e.subtype for e in events} == {"duplicate", "split", "missing"}
    assert all(e.effect == "structural" and e.mess_type == "households" for e in events)


def test_no_household_gets_more_than_one_event(full: Run) -> None:
    counts = Counter(e.refs.household_id for e in full[3])
    assert counts and max(counts.values()) == 1


def test_duplicate_copies_members_with_new_ids_and_same_truth_refs(full: Run) -> None:
    _, original, data, events = full
    duplicates = of_subtype(events, "duplicate")
    assert duplicates
    now = contacts(data)
    before = contacts(original)
    for event in duplicates:
        copies = [now[uid] for uid in event.row_uids]
        sources = [now[uid.removesuffix(DUPLICATE_SUFFIX)] for uid in event.row_uids]
        assert all(uid.endswith(DUPLICATE_SUFFIX) for uid in event.row_uids)
        assert all(uid.removesuffix(DUPLICATE_SUFFIX) in before for uid in event.row_uids)
        assert {c.refs for c in copies} == {s.refs for s in sources}
        assert len(copies) == len(
            [r for r in before.values() if r.refs.household_id == event.refs.household_id]
        )
        new_households = {str(c.values["household.source_id"]) for c in copies}
        assert len(new_households) == 1
        assert new_households != {str(s.values["household.source_id"]) for s in sources}
        for copy_row, source in zip(copies, sources, strict=True):
            assert copy_row.values["person.source_id"] != source.values["person.source_id"]
            assert copy_row.values["person.first_name"] == source.values["person.first_name"]
            assert copy_row.values["person.date_of_birth"] == source.values["person.date_of_birth"]
        assert event.before != event.after


def test_duplicate_name_is_a_variation() -> None:
    _, original, data, events = run(firm_of(60), 1.0)
    names = {
        str(contacts(data)[uid].values["household.name"])
        for e in of_subtype(events, "duplicate")
        for uid in e.row_uids
    }
    originals = {str(r.values["household.name"]) for r in contacts(original).values()}
    assert names
    assert all(("," in n or n.startswith("The ")) and n not in originals for n in names)


def test_split_moves_one_non_primary_member_to_a_new_household(full: Run) -> None:
    _, original, data, events = full
    splits = of_subtype(events, "split")
    assert splits
    now = contacts(data)
    before = contacts(original)
    for event in splits:
        (uid,) = event.row_uids
        moved, old = now[uid], before[uid]
        assert old.values["person.household_role"] is not HouseholdRole.PRIMARY
        assert moved.values["person.household_role"] is HouseholdRole.PRIMARY
        assert moved.values["household.source_id"] != old.values["household.source_id"]
        assert moved.values["household.name"].endswith(" Household")
        assert moved.values["person.source_id"] == old.values["person.source_id"]
        assert moved.refs == old.refs  # truth refs: still the same truth household
        old_household = str(old.values["household.source_id"])
        stayers = [
            r
            for r in now.values()
            if r.values["household.source_id"] == old_household and r.row_uid != uid
        ]
        assert stayers  # the original household keeps at least one member
        assert any(s.refs.household_id == moved.refs.household_id for s in stayers)


def test_missing_blanks_household_fields_but_keeps_person_data(full: Run) -> None:
    _, original, data, events = full
    crm_missing = [e for e in of_subtype(events, "missing") if e.source == "crm"]
    assert crm_missing
    now, before = contacts(data), contacts(original)
    for event in crm_missing:
        for uid in event.row_uids:
            row, old = now[uid], before[uid]
            assert row.values["household.source_id"] is None
            assert row.values["household.name"] is None
            assert row.values["person.household_role"] is None
            for concept, value in old.values.items():
                if not concept.startswith("household.") and concept != "person.household_role":
                    assert row.values[concept] == value


def test_missing_in_the_spreadsheet_blanks_the_first_row_of_a_block(full: Run) -> None:
    _, _, data, events = full
    book_missing = [e for e in of_subtype(events, "missing") if e.source == "book_of_business"]
    assert book_missing
    for event in book_missing:
        (uid,) = event.row_uids
        rows = data["book_of_business"][event.table]
        row = next(r for r in rows if r.row_uid == uid)
        block = sorted(
            (r for r in rows if r.refs.household_id == row.refs.household_id),
            key=lambda r: r.row_uid,
        )
        assert block[0] is row
        assert row.values["household.name"] == ""
        assert event.before


def test_workbook_shows_a_blank_household_cell_after_missing(tmp_path: Path) -> None:
    firm, _, data, events = run(firm_of(60), 1.0)
    event = next(e for e in of_subtype(events, "missing") if e.source == "book_of_business")
    exporter = BookOfBusinessExporter()
    exporter.project(firm)
    rows = [r for tables in data["book_of_business"].values() for r in tables]
    result = exporter.write(rows, tmp_path)
    import openpyxl

    locator = result.locators[event.row_uids[0]]
    sheet = openpyxl.load_workbook(result.files[0])[str(locator.sheet)]
    assert sheet.cell(row=locator.row_number, column=1).value is None
    assert sheet.cell(row=locator.row_number, column=3).value is not None


def test_ids_stay_unique_and_links_have_no_orphans(full: Run) -> None:
    _, original, data, _ = full
    rows = data["crm"]["contacts"]
    contact_ids = [str(r.values["person.source_id"]) for r in rows]
    assert len(set(contact_ids)) == len(contact_ids)
    assert all(len(i) == 7 and i[0] == "C" for i in contact_ids)
    household_ids = {str(r.values["household.source_id"]) for r in rows} - {"None"}
    assert all(len(h) == 5 and h[0] == "H" for h in household_ids)
    # one source household id never mixes people from different truth households
    groups: dict[str, set[str | None]] = {}
    for r in rows:
        if r.values["household.source_id"] is not None:
            groups.setdefault(str(r.values["household.source_id"]), set()).add(r.refs.household_id)
    assert all(len(g) == 1 for g in groups.values())
    links = {str(r.values["person.source_id"]) for r in data["crm"]["linked_accounts"]}
    assert links <= set(contact_ids)
    assert data["crm"]["linked_accounts"] == original["crm"]["linked_accounts"]


def test_nothing_outside_crm_contacts_and_the_book_changes(full: Run) -> None:
    _, original, data, _ = full
    assert data["custodian"] == original["custodian"]
    assert data["crm"]["linked_accounts"] == original["crm"]["linked_accounts"]


def test_affected_share_matches_rate_on_300_households() -> None:
    firm, _, _, events = run(firm_of(300), 0.5 * 0.15)
    share = len(events) / len(firm.households)
    assert share == pytest.approx(0.075, abs=0.05)


def test_crm_export_writes_blank_household_fields(tmp_path: Path) -> None:
    firm, _, data, events = run(firm_of(60), 1.0)
    exporter = CrmExporter()
    exporter.project(firm)
    rows = [r for tables in data["crm"].values() for r in tables]
    exporter.write(rows, tmp_path)
    with (tmp_path / "crm_contacts.csv").open(encoding="utf-8", newline="") as handle:
        records = list(csv.DictReader(handle))
    assert len(records) == len(data["crm"]["contacts"])
    blank = [r for r in records if r["household_id"] == ""]
    missing = sum(len(e.row_uids) for e in events if e.subtype == "missing" and e.source == "crm")
    assert len(blank) == missing > 0
    assert all(r["household_name"] == "" and r["household_role"] == "" for r in blank)
    assert all(r["first_name"] for r in blank)


def test_same_seed_same_events_and_other_seed_differs() -> None:
    firm = firm_of(60)
    assert run(firm, 0.5)[3] == run(firm, 0.5)[3]
    assert run(firm, 0.5, seed=1)[3] != run(firm, 0.5, seed=2)[3]


def test_truth_is_untouched() -> None:
    firm = build_firm(load_profile(), 15, 42)
    before = firm.model_dump_json()
    run(firm, 1.0)
    assert firm.model_dump_json() == before

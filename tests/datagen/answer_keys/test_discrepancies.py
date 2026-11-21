from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from onboardkit.datagen.answer_keys.discrepancies import (
    DISCREPANCIES_FILE,
    HEADER,
    INHERENT,
    authority,
    build_discrepancies,
    check_consistency,
    inherent_count,
    write_discrepancies,
)
from onboardkit.datagen.answer_keys.writer import read_table
from onboardkit.datagen.config import resolve_config
from onboardkit.datagen.pipeline import AnswerKeyContext, generate_dataset
from onboardkit.datagen.sources.base import RawText, SourceRow
from onboardkit.datagen.sources.coverage import CoverageEvent

CUSTODIAN, CRM, BOOK = "custodian", "crm", "book_of_business"


def capture(
    tmp_path: Path, preset: str, size: str | int = "sample", seed: int = 42
) -> tuple[AnswerKeyContext, Path]:
    held: list[AnswerKeyContext] = []

    def writer(context: AnswerKeyContext) -> None:
        held.append(context)
        write_discrepancies(context)

    result = generate_dataset(
        resolve_config(preset, size, seed), tmp_path, answer_key_writers=[writer]
    )
    return held[0], result.path / "truth" / DISCREPANCIES_FILE


@pytest.fixture(scope="module")
def typical(tmp_path_factory: pytest.TempPathFactory) -> tuple[AnswerKeyContext, Path]:
    return capture(tmp_path_factory.mktemp("d"), "typical")


@pytest.fixture(scope="module")
def clean_base(tmp_path_factory: pytest.TempPathFactory) -> AnswerKeyContext:
    return capture(tmp_path_factory.mktemp("c"), "clean", 20, 3)[0]


@pytest.fixture
def clean(clean_base: AnswerKeyContext) -> AnswerKeyContext:
    """A fresh copy of the clean context that a test may damage."""
    copy = deepcopy(clean_base)
    assert build_discrepancies(copy) == []
    return copy


def only(context: AnswerKeyContext) -> dict[str, str]:
    found = build_discrepancies(context)
    assert len(found) == 1, found
    d = found[0]
    return {
        "kind": d.kind,
        "entity_type": d.entity_type,
        "truth_id": d.truth_id,
        "concept": d.concept,
        "sources": "|".join(d.sources),
        "auth": d.authoritative_source,
        "auth_value": d.authoritative_value,
        "other": "|".join(d.other_values),
        "severity": d.severity,
        "origin": "|".join(d.origin_events),
    }


def row_of(context: AnswerKeyContext, source: str, table: str, index: int = 0) -> SourceRow:
    return [r for r in context.rows[source] if r.table == table][index]


def test_clean_dataset_has_no_discrepancies_and_the_file_is_header_only(tmp_path: Path) -> None:
    context, path = capture(tmp_path, "clean", "sample", 1)
    assert build_discrepancies(context) == []
    assert path.read_text(encoding="utf-8").strip().split(",") == list(HEADER)
    assert check_consistency(context) == []


def test_custodian_account_missing(clean: AnswerKeyContext) -> None:
    gone = row_of(clean, CUSTODIAN, "accounts")
    clean.rows[CUSTODIAN].remove(gone)
    assert only(clean) == {
        "kind": "missing_in_source",
        "entity_type": "account",
        "truth_id": gone.refs.account_id,
        "concept": "",
        "sources": CUSTODIAN,
        "auth": CUSTODIAN,
        "auth_value": "",
        "other": "",
        "severity": "material",
        "origin": "",
    }


def test_crm_link_person_and_household_missing(clean: AnswerKeyContext) -> None:
    link = row_of(clean, CRM, "linked_accounts")
    clean.rows[CRM].remove(link)
    found = only(clean)
    assert found["kind"] == "missing_in_source" and found["sources"] == CRM
    assert found["truth_id"] == link.refs.account_id
    assert found["other"] == f"crm=no link for {link.refs.person_ids[0]}"

    context = deepcopy(clean)
    household = row_of(context, CRM, "contacts").refs.household_id
    gone = [
        r for r in context.rows[CRM] if r.table == "contacts" and r.refs.household_id == household
    ]
    context.rows[CRM] = [r for r in context.rows[CRM] if r not in gone]
    kinds = {(d.entity_type, d.truth_id) for d in build_discrepancies(context)}
    assert ("household", household) in kinds
    assert {("person", pid) for r in gone for pid in r.refs.person_ids} <= kinds


def test_book_account_and_household_missing(clean: AnswerKeyContext) -> None:
    household = row_of(clean, BOOK, "accounts").refs.household_id
    gone = [r for r in clean.rows[BOOK] if r.refs.household_id == household]
    clean.rows[BOOK] = [r for r in clean.rows[BOOK] if r not in gone]
    found = {(d.entity_type, d.truth_id) for d in build_discrepancies(clean)}
    assert ("household", household) in found
    assert {("account", r.refs.account_id) for r in gone} <= found


def test_stale_extra_row(clean: AnswerKeyContext) -> None:
    row = deepcopy(row_of(clean, BOOK, "accounts"))
    row.row_uid = "book_of_business:archive:stale-000001"
    row.table = "archive"
    row.refs = replace(row.refs, account_id=None)
    row.values["account.number"] = "ZZ999999"
    clean.rows[BOOK].append(row)
    found = only(clean)
    assert found["kind"] == "stale_extra" and found["truth_id"] == ""
    assert found["other"] == "book_of_business=ZZ999999"
    assert found["auth"] == CUSTODIAN


def test_balance_conflicts_use_the_tolerance(clean: AnswerKeyContext) -> None:
    row = row_of(clean, BOOK, "accounts")
    base = Decimal(str(row.values["account.balance"]))
    row.values["account.balance"] = base + Decimal("0.50")
    small = only(clean)
    assert (small["kind"], small["concept"], small["severity"]) == (
        "value_conflict",
        "account.balance",
        "immaterial",
    )
    assert small["origin"] == INHERENT
    assert small["auth_value"] == f"{base:.2f}"
    assert small["other"] == f"book_of_business={base + Decimal('0.50'):.2f}"
    row.values["account.balance"] = base + Decimal("5000")
    assert only(clean)["severity"] == "material"


def test_type_status_and_registration_conflicts_are_material(clean: AnswerKeyContext) -> None:
    link = row_of(clean, CRM, "linked_accounts")
    original = link.values["account.type"]
    link.values["account.type"] = "other-type"
    typed = only(clean)
    assert (typed["concept"], typed["sources"], typed["severity"]) == (
        "account.type",
        "crm|custodian",
        "material",
    )
    link.values["account.type"] = original

    book = row_of(clean, BOOK, "accounts")
    book.values["meta.notes"] = "Closed per client"
    status = only(clean)
    assert status["concept"] == "account.status" and status["other"] == "book_of_business=closed"
    book.values["meta.notes"] = "Sole owner: Pat Lee"
    assert only(clean)["concept"] == "account.registration"


def test_format_only_variants_are_not_discrepancies(clean: AnswerKeyContext) -> None:
    book = row_of(clean, BOOK, "accounts")
    value = book.values["account.balance"]
    book.values["account.balance"] = RawText(text=f"${value:,.2f}", original=value)
    book.values["account.number"] = RawText(
        text="x-" + str(book.values["account.number"]), original=book.values["account.number"]
    )
    assert build_discrepancies(clean) == []


def test_note_phrases_are_not_conflicts(clean: AnswerKeyContext) -> None:
    row_of(clean, BOOK, "accounts").values["meta.notes"] = "needs W-9"
    assert build_discrepancies(clean) == []


def test_authority_follows_the_roadmap_defaults() -> None:
    for concept in ("account.balance", "account.status", "account.registration", "account.type"):
        assert authority(concept) == CUSTODIAN
    for concept in ("person.email", "person.phone", "household.name", "household.advisor"):
        assert authority(concept) == CRM
    assert authority("meta.notes") == BOOK


@pytest.mark.parametrize(
    ("preset", "size", "seed"),
    [
        ("typical", "sample", 42),
        ("typical", "default", 7),
        ("clean", "sample", 3),
        ("nightmare", 60, 5),
    ],
)
def test_events_are_a_subset_of_the_state_based_list(
    tmp_path: Path, preset: str, size: str | int, seed: int
) -> None:
    context, _ = capture(tmp_path, preset, size, seed)
    assert check_consistency(context) == []


def test_every_coverage_event_and_value_conflict_is_listed(
    typical: tuple[AnswerKeyContext, Path],
) -> None:
    context, _ = typical
    cited = {i for d in build_discrepancies(context) for i in d.origin_events}
    assert context.coverage_events
    for coverage in context.coverage_events:
        assert coverage.event_id in cited
    in_book = {r.refs.account_id for r in context.rows[BOOK]}
    for event in context.mess_events:
        if event.effect == "value_conflict" and event.concept != "account.balance":
            if event.subtype == "stale_value" and event.refs.account_id not in in_book:
                continue
            assert event.event_id in cited, event


def test_severity_matches_the_event_label(typical: tuple[AnswerKeyContext, Path]) -> None:
    context, _ = typical
    labels = {e.event_id: e.severity for e in context.mess_events}
    checked = 0
    for d in build_discrepancies(context):
        events = [labels[i] for i in d.origin_events if i in labels]
        if events:
            expected = "material" if "material" in events else "immaterial"
            assert d.severity == expected
            checked += 1
    assert checked > 0


def test_format_events_never_cause_a_discrepancy(typical: tuple[AnswerKeyContext, Path]) -> None:
    context, _ = typical
    format_ids = {e.event_id for e in context.mess_events if e.effect == "format_variant"}
    assert format_ids
    cited = {i for d in build_discrepancies(context) for i in d.origin_events}
    assert not format_ids & cited


def test_inherent_drift_is_counted_and_only_the_book_is_involved(
    typical: tuple[AnswerKeyContext, Path],
) -> None:
    context, _ = typical
    inherent = [d for d in build_discrepancies(context) if d.origin_events == (INHERENT,)]
    assert inherent and inherent_count(context) == len(inherent)
    assert all(d.sources == (BOOK, CUSTODIAN) or d.sources == (CUSTODIAN, BOOK) for d in inherent)


def test_ids_are_sequential_and_rows_sorted(typical: tuple[AnswerKeyContext, Path]) -> None:
    context, path = typical
    rows = read_table(path)
    assert [r["discrepancy_id"] for r in rows] == [f"D-{n:06d}" for n in range(1, len(rows) + 1)]
    assert len(rows) == len(build_discrepancies(context))
    assert {r["kind"] for r in rows} <= {"missing_in_source", "value_conflict", "stale_extra"}
    assert {r["severity"] for r in rows} <= {"immaterial", "material"}


def test_output_is_byte_identical_across_runs(tmp_path: Path) -> None:
    _, one = capture(tmp_path / "a", "nightmare", 40, 9)
    _, two = capture(tmp_path / "b", "nightmare", 40, 9)
    assert one.read_bytes() == two.read_bytes()


def test_coverage_event_ids_are_stable() -> None:
    event = CoverageEvent("omitted", CRM, "contacts", "crm:contacts:000012", refs=None)  # type: ignore[arg-type]
    assert event.event_id == "cov:omitted:crm:contacts:000012"

from functools import cache
from pathlib import Path

import pytest

from onboardkit.datagen.config import (
    BookCoverage,
    CoverageConfig,
    CrmCoverage,
    CustodianCoverage,
)
from onboardkit.datagen.sources.base import SourceRow
from onboardkit.datagen.sources.book_of_business import BookOfBusinessExporter
from onboardkit.datagen.sources.coverage import CoverageEvent, apply_coverage
from onboardkit.datagen.sources.crm import CrmExporter
from onboardkit.datagen.sources.custodian import CustodianExporter
from onboardkit.datagen.truth.builder import build_firm
from onboardkit.datagen.truth.model import TruthFirm
from onboardkit.datagen.truth.profile import load_profile

TYPICAL = CoverageConfig(
    custodian=CustodianCoverage(accounts=1.0),
    crm=CrmCoverage(persons=0.97, account_links=0.90),
    book_of_business=BookCoverage(households=0.85, accounts=0.80, stale_extra_rate=0.03),
)
Rows = dict[str, list[SourceRow]]


@cache
def _firm(households: int, seed: int) -> TruthFirm:
    return build_firm(load_profile(), households, seed)


def project_all(firm: TruthFirm) -> Rows:
    return {
        "custodian": CustodianExporter.for_firm(firm).project(firm),
        "crm": CrmExporter().project(firm),
        "book_of_business": BookOfBusinessExporter().project(firm),
    }


def _uids(rows: Rows) -> dict[str, set[str]]:
    return {source: {r.row_uid for r in items} for source, items in rows.items()}


def test_full_rates_change_nothing_and_log_nothing() -> None:
    firm = _firm(15, 42)
    rows = project_all(firm)
    kept, events = apply_coverage(rows, firm, CoverageConfig(), 42)
    assert kept == rows
    assert events == []


def test_omitted_share_is_close_to_configured_rate() -> None:
    firm = _firm(300, 42)
    rows = project_all(firm)
    kept, events = apply_coverage(rows, firm, TYPICAL, 42)

    def share(source: str, table: str) -> float:
        before = [r for r in rows[source] if r.table == table]
        after = [r for r in kept[source] if r.table == table]
        return len(after) / len(before)

    assert share("custodian", "accounts") == pytest.approx(1.0, abs=0.03)
    assert share("crm", "contacts") == pytest.approx(0.97, abs=0.03)
    assert share("crm", "linked_accounts") == pytest.approx(0.90, abs=0.03)
    assert events


def test_spreadsheet_household_and_account_rates_are_each_close_to_target() -> None:
    firm = _firm(300, 42)
    rows = project_all(firm)
    book = rows["book_of_business"]
    only_households = CoverageConfig(book_of_business=BookCoverage(households=0.85))
    kept, _ = apply_coverage(rows, firm, only_households, 42)
    before = {r.refs.household_id for r in book}
    after = {r.refs.household_id for r in kept["book_of_business"]}
    assert len(after) / len(before) == pytest.approx(0.85, abs=0.03)

    only_accounts = CoverageConfig(book_of_business=BookCoverage(accounts=0.80))
    kept, _ = apply_coverage(rows, firm, only_accounts, 42)
    assert len(kept["book_of_business"]) / len(book) == pytest.approx(0.80, abs=0.03)


@pytest.mark.parametrize("seed", range(12))
def test_every_account_and_household_survives_somewhere(seed: int) -> None:
    firm = _firm(15, seed)
    harsh = CoverageConfig(
        custodian=CustodianCoverage(accounts=0.5),
        crm=CrmCoverage(persons=0.4, account_links=0.3),
        book_of_business=BookCoverage(households=0.4, accounts=0.3, stale_extra_rate=0.1),
    )
    kept, _ = apply_coverage(project_all(firm), firm, harsh, seed)
    refs = [r.refs for rows in kept.values() for r in rows]
    assert {a.account_id for a in firm.accounts} <= {x.account_id for x in refs}
    assert {h.household_id for h in firm.households} <= {x.household_id for x in refs}


def test_one_event_per_omission_and_per_extra() -> None:
    firm = _firm(60, 7)
    rows = project_all(firm)
    kept, events = apply_coverage(rows, firm, TYPICAL, 7)
    before = sum(len(v) for v in rows.values())
    after = sum(len(v) for v in kept.values())
    omitted = [e for e in events if e.kind == "omitted"]
    extras = [e for e in events if e.kind == "stale_extra"]
    assert before - len(omitted) + len(extras) == after
    assert len({e.row_uid for e in events}) == len(events)
    original = {r.row_uid for items in rows.values() for r in items}
    survivors = {r.row_uid for items in kept.values() for r in items}
    assert {e.row_uid for e in omitted} == original - survivors
    assert {e.row_uid for e in extras} == survivors - original
    assert all(isinstance(e, CoverageEvent) for e in events)


def test_stale_extras_have_no_truth_account_and_unique_new_numbers() -> None:
    firm = _firm(60, 7)
    kept, events = apply_coverage(project_all(firm), firm, TYPICAL, 7)
    extras = [r for r in kept["book_of_business"] if "stale-" in r.row_uid]
    assert extras
    assert len(extras) == len([e for e in events if e.kind == "stale_extra"])
    truth_numbers = {a.account_number for a in firm.accounts}
    numbers = [str(r.values["account.number"]) for r in extras]
    assert all(r.refs.account_id is None for r in extras)
    assert not set(numbers) & truth_numbers
    assert len(set(numbers)) == len(numbers)
    assert all(r.table == "archive" for r in extras)
    assert all(n.startswith("MC") and len(n) == 8 for n in numbers)


def test_extras_can_be_written_into_the_workbook(tmp_path: Path) -> None:
    firm = _firm(15, 42)
    kept, _ = apply_coverage(
        project_all(firm),
        firm,
        CoverageConfig(book_of_business=BookCoverage(stale_extra_rate=0.2)),
        42,
    )
    exporter = BookOfBusinessExporter()
    exporter.project(firm)
    result = exporter.write(kept["book_of_business"], tmp_path)
    assert len(result.locators) == len(kept["book_of_business"])


def test_same_seed_and_config_give_identical_omissions() -> None:
    firm = _firm(60, 7)
    one = apply_coverage(project_all(firm), firm, TYPICAL, 7)
    two = apply_coverage(project_all(firm), firm, TYPICAL, 7)
    assert one[1] == two[1]
    assert _uids(one[0]) == _uids(two[0])


def test_different_seed_changes_omissions() -> None:
    firm = _firm(60, 7)
    one = apply_coverage(project_all(firm), firm, TYPICAL, 7)
    two = apply_coverage(project_all(firm), firm, TYPICAL, 8)
    assert one[1] != two[1]


def test_changing_crm_rate_does_not_change_custodian_omissions() -> None:
    firm = _firm(60, 7)
    custodian_only = CoverageConfig(custodian=CustodianCoverage(accounts=0.8))
    with_crm = CoverageConfig(
        custodian=CustodianCoverage(accounts=0.8), crm=CrmCoverage(persons=0.5, account_links=0.5)
    )
    first = apply_coverage(project_all(firm), firm, custodian_only, 7)
    second = apply_coverage(project_all(firm), firm, with_crm, 7)

    def custodian_omissions(events: list[CoverageEvent]) -> set[str | None]:
        return {e.row_uid for e in events if e.source == "custodian"}

    # The guarantee rule may restore a few custodian rows when the CRM drops more, so compare the
    # initial selection through rows the CRM change cannot have needed.
    assert custodian_omissions(second[1]) <= custodian_omissions(first[1])
    assert len(custodian_omissions(first[1])) > 0


def test_some_households_appear_in_all_three_sources() -> None:
    firm = _firm(300, 42)
    kept, _ = apply_coverage(project_all(firm), firm, TYPICAL, 42)
    sets = [
        {r.refs.household_id for r in kept[s] if "stale-" not in r.row_uid}
        for s in ("custodian", "crm", "book_of_business")
    ]
    assert len(sets[0] & sets[1] & sets[2]) >= 100

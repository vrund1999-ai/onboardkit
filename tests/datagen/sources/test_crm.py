import csv
import re
from collections import Counter
from pathlib import Path

import pytest

from onboardkit.datagen.sources.base import SourceRow, WriteResult, known_concepts
from onboardkit.datagen.sources.crm import ACCOUNT_TYPE_LABELS, ROLE_LABELS, CrmExporter
from onboardkit.datagen.truth.builder import build_firm
from onboardkit.datagen.truth.profile import AccountType, load_profile

FIRM = build_firm(load_profile(), 15, 42)
EMAIL = re.compile(r"^[a-z0-9._-]+@example\.(com|test)$")
PHONE = re.compile(r"^\(\d{3}\) 555-01\d{2}$")


@pytest.fixture(scope="module")
def exported(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[CrmExporter, list[SourceRow], WriteResult, Path]:
    out = tmp_path_factory.mktemp("crm")
    exporter = CrmExporter()
    rows = exporter.project(FIRM)
    return exporter, rows, exporter.write(rows, out), out


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_two_files_with_expected_headers(
    exported: tuple[CrmExporter, list[SourceRow], WriteResult, Path],
) -> None:
    _, _, _, out = exported
    contacts = (out / "crm_contacts.csv").read_text(encoding="utf-8").splitlines()[0]
    assert contacts == (
        "contact_id,first_name,last_name,suffix,date_of_birth,email,phone,street,city,state,zip,"
        "household_id,household_name,household_role,advisor,client_since"
    )
    linked = (out / "crm_linked_accounts.csv").read_text(encoding="utf-8").splitlines()[0]
    assert linked == "contact_id,account_number,account_type"  # README's account_number example


def test_bytes_no_bom_lf_only(
    exported: tuple[CrmExporter, list[SourceRow], WriteResult, Path],
) -> None:
    for name in ("crm_contacts.csv", "crm_linked_accounts.csv"):
        data = (exported[3] / name).read_bytes()
        assert not data.startswith(b"\xef\xbb\xbf")
        assert b"\r" not in data
        assert data.endswith(b"\n")


def test_every_person_appears_exactly_once(
    exported: tuple[CrmExporter, list[SourceRow], WriteResult, Path],
) -> None:
    _, rows, _, out = exported
    contact_rows = [r for r in rows if r.table == "contacts"]
    assert Counter(r.refs.person_ids for r in contact_rows) == Counter(
        (p.person_id,) for p in FIRM.people
    )
    assert len(_read(out / "crm_contacts.csv")) == len(FIRM.people)


def test_every_owner_gets_a_link_for_each_account(
    exported: tuple[CrmExporter, list[SourceRow], WriteResult, Path],
) -> None:
    exporter, _, _, out = exported
    links = _read(out / "crm_linked_accounts.csv")
    expected = Counter(
        (exporter.id_maps.person[owner], a.account_number)
        for a in FIRM.accounts
        for owner in a.owner_ids
    )
    assert Counter((r["contact_id"], r["account_number"]) for r in links) == expected
    joint = next(a for a in FIRM.accounts if a.account_type is AccountType.JOINT)
    assert sum(r["account_number"] == joint.account_number for r in links) == 2


def test_contract_links_join_to_contacts_without_orphans(
    exported: tuple[CrmExporter, list[SourceRow], WriteResult, Path],
) -> None:
    out = exported[3]
    contact_ids = {r["contact_id"] for r in _read(out / "crm_contacts.csv")}
    assert {r["contact_id"] for r in _read(out / "crm_linked_accounts.csv")} <= contact_ids


def test_emails_and_phones_are_fictional(
    exported: tuple[CrmExporter, list[SourceRow], WriteResult, Path],
) -> None:
    contacts = _read(exported[3] / "crm_contacts.csv")
    adults = [r for r in contacts if r["household_role"] != "Dependent"]
    assert adults
    for record in adults:
        assert EMAIL.match(record["email"]), record["email"]
        assert PHONE.match(record["phone"]), record["phone"]
    for record in contacts:
        if record["household_role"] == "Dependent":
            assert record["email"] == ""
            assert record["phone"] == ""


def test_email_and_phone_validators_reject_real_looking_values() -> None:
    assert not EMAIL.match("jane@gmail.com")
    assert not PHONE.match("(212) 555-1234")


def test_source_ids_are_unrelated_and_unique(
    exported: tuple[CrmExporter, list[SourceRow], WriteResult, Path],
) -> None:
    exporter = exported[0]
    people = exporter.id_maps.person
    households = exporter.id_maps.household
    assert len(set(people.values())) == len(people) == len(FIRM.people)
    assert len(set(households.values())) == len(households) == len(FIRM.households)
    assert all(re.fullmatch(r"C\d{6}", v) for v in people.values())
    assert all(re.fullmatch(r"H\d{4}", v) for v in households.values())
    for truth_id, source_id in {**people, **households}.items():
        assert truth_id not in source_id
        assert truth_id.split("-")[1] != source_id[1:]
    ordered = [people[p.person_id] for p in FIRM.people]
    assert ordered != sorted(ordered)  # not simply numbered in truth order


def test_formats(exported: tuple[CrmExporter, list[SourceRow], WriteResult, Path]) -> None:
    exporter, _, _, out = exported
    by_source_id = {v: k for k, v in exporter.id_maps.person.items()}
    people = FIRM.people_by_id()
    households = FIRM.households_by_id()
    for record in _read(out / "crm_contacts.csv"):
        person = people[by_source_id[record["contact_id"]]]
        household = households[person.household_id]
        assert record["date_of_birth"] == person.date_of_birth.isoformat()
        assert record["client_since"] == household.client_since.isoformat()
        assert record["household_role"] == ROLE_LABELS[person.household_role.value]
        assert record["household_name"] == household.display_name
        assert record["household_id"] == exporter.id_maps.household[household.household_id]
        assert record["advisor"] == household.advisor
        assert re.fullmatch(r"[A-Z]{2}", record["state"])
        assert record["suffix"] == (person.suffix or "")


def test_account_type_labels(
    exported: tuple[CrmExporter, list[SourceRow], WriteResult, Path],
) -> None:
    assert set(ACCOUNT_TYPE_LABELS) == {t.value for t in AccountType}
    links = _read(exported[3] / "crm_linked_accounts.csv")
    assert {r["account_type"] for r in links} <= set(ACCOUNT_TYPE_LABELS.values())
    assert "Joint Brokerage" in {r["account_type"] for r in links}


def test_locators_resolve_for_both_files(
    exported: tuple[CrmExporter, list[SourceRow], WriteResult, Path],
) -> None:
    exporter, rows, result, out = exported
    assert len(result.locators) == len(rows)
    lines = {
        name: (out / name).read_text(encoding="utf-8").splitlines()
        for name in ("crm_contacts.csv", "crm_linked_accounts.csv")
    }
    for row in rows:
        locator = result.locators[row.row_uid]
        line = lines[locator.file][locator.row_number - 1]
        key = (
            exporter.id_maps.person[row.refs.person_ids[0]]
            if row.table == "contacts"
            else row.values["account.number"]
        )
        assert key in line


def test_every_column_concept_exists_in_catalogue() -> None:
    columns = [c for t in CrmExporter().profile.tables for c in t.columns]
    assert {c.concept for c in columns} <= known_concepts()


def test_output_is_byte_identical_across_runs(tmp_path: Path) -> None:
    def run(folder: Path) -> tuple[bytes, bytes]:
        exporter = CrmExporter()
        exporter.write(exporter.project(FIRM), folder)
        return (
            (folder / "crm_contacts.csv").read_bytes(),
            (folder / "crm_linked_accounts.csv").read_bytes(),
        )

    assert run(tmp_path / "a") == run(tmp_path / "b")


def test_different_seed_gives_different_source_ids() -> None:
    other = build_firm(load_profile(), 15, 43)
    first, second = CrmExporter(), CrmExporter()
    first.project(FIRM)
    second.project(other)
    assert list(first.id_maps.person.values()) != list(second.id_maps.person.values())

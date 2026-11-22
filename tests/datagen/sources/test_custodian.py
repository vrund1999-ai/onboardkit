import csv
import io
from collections import Counter
from pathlib import Path

import pytest

from onboardkit.datagen.sources.base import known_concepts
from onboardkit.datagen.sources.custodian import ACCOUNT_TYPE_CODES, CustodianExporter
from onboardkit.datagen.truth.builder import build_firm
from onboardkit.datagen.truth.model import TruthFirm
from onboardkit.datagen.truth.profile import AccountType, load_profile

FIRM = build_firm(load_profile(), 15, 42)


@pytest.fixture(scope="module")
def written(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, CustodianExporter, int]:
    out = tmp_path_factory.mktemp("custodian")
    exporter = CustodianExporter.for_firm(FIRM)
    rows = exporter.project(FIRM)
    result = exporter.write(rows, out)
    assert len(result.locators) == len(rows)
    accounts = sum(r.table == "accounts" for r in rows)
    return result.files[0], exporter, accounts


def _lines(path: Path) -> list[str]:
    return path.read_bytes().decode("utf-8-sig").split("\r\n")


def test_first_lines_snapshot(written: tuple[Path, CustodianExporter, int]) -> None:
    lines = _lines(written[0])
    assert lines[:5] == [
        '"MERIDIAN CUSTODY SERVICES - ACCOUNT MASTER"',
        '"Report date: 12/31/2025"',
        '"Acct #","Account Title","Acct Type","Status","Open Date","Market Value",'
        '"Value As Of","Owner 1","Owner 2","Mail Addr","TIN Last4"',
        '"MC143753","BRUCE ARNOLD INDIVIDUAL","IND","OPEN","12/12/2023","18,497.87",'
        '"20251231","ARNOLD, BRUCE","","92017 Daniel Road Suite 681, Stewartfurt, WA 95727","3576"',
        '"MC151672","WESLEY V ARNOLD ROTH IRA","ROTH","OPEN","10/30/2022","121,930.20",'
        '"20251231","ARNOLD, WESLEY V","","92017 Daniel Road Suite 681, Stewartfurt, WA 95727",'
        '"5768"',
    ]


def test_bytes_bom_and_crlf(written: tuple[Path, CustodianExporter, int]) -> None:
    data = written[0].read_bytes()
    assert data.startswith(b"\xef\xbb\xbf")
    assert data.endswith(b"\r\n")
    assert data.replace(b"\r\n", b"").count(b"\n") == 0
    assert data.replace(b"\r\n", b"").count(b"\r") == 0


def test_preamble_header_and_trailer(written: tuple[Path, CustodianExporter, int]) -> None:
    path, _, count = written
    lines = _lines(path)
    assert lines[2].startswith('"Acct #"')
    assert lines[-2] == f'"Total records: {count}"'
    assert lines[-1] == ""
    assert len(lines) == 3 + count + 1 + 1  # preamble+header, rows, trailer, final break


def test_every_account_appears_exactly_once() -> None:
    projected = CustodianExporter.for_firm(FIRM).project(FIRM)
    rows = [r for r in projected if r.table == "accounts"]
    assert Counter(r.refs.account_id for r in rows) == Counter(a.account_id for a in FIRM.accounts)
    assert len({r.row_uid for r in rows}) == len(rows)


def test_values_use_documented_formats(written: tuple[Path, CustodianExporter, int]) -> None:
    text = written[0].read_bytes().decode("utf-8-sig")
    records = list(csv.reader(io.StringIO(text)))
    header = records[2]
    data = records[3:-1]
    assert header[0] == "Acct #"  # the README header example
    by_number = {a.account_number: a for a in FIRM.accounts}
    people = FIRM.people_by_id()
    for record in data:
        row = dict(zip(header, record, strict=True))
        account = by_number[row["Acct #"]]
        assert row["Acct Type"] == ACCOUNT_TYPE_CODES[account.account_type.value]
        assert row["Status"] == account.status.value.upper()
        assert row["Open Date"] == account.open_date.strftime("%m/%d/%Y")
        assert row["Value As Of"] == "20251231"
        assert row["Market Value"] == f"{account.balance:,.2f}"
        assert row["Account Title"] == account.registration_title.upper()
        owner = people[account.owner_ids[0]]
        assert row["Owner 1"].startswith(f"{owner.last_name.upper()}, {owner.first_name.upper()}")
        assert row["TIN Last4"] == owner.tax_id_last4
        assert (row["Owner 2"] != "") == (len(account.owner_ids) == 2)
        assert row["Owner 1"] == row["Owner 1"].upper()


def test_account_type_codes_cover_every_type() -> None:
    assert set(ACCOUNT_TYPE_CODES) == {t.value for t in AccountType}
    assert ACCOUNT_TYPE_CODES["joint"] == "JNT"
    assert ACCOUNT_TYPE_CODES["education_529"] == "529"


def test_every_column_concept_exists_in_catalogue() -> None:
    exporter = CustodianExporter.for_firm(FIRM)
    assert {c.concept for c in exporter.profile.tables[0].columns} <= known_concepts()


def test_owner_columns_are_distinguished_by_index() -> None:
    columns = CustodianExporter.for_firm(FIRM).profile.tables[0].columns
    owners = [c for c in columns if c.concept == "account.owner_names"]
    assert [c.options["index"] for c in owners] == [0, 1]


def test_locators_point_to_the_right_lines(written: tuple[Path, CustodianExporter, int]) -> None:
    path, exporter, _ = written
    rows = exporter.project(FIRM)
    result = exporter.write(rows, path.parent / "again")
    lines = _lines(result.files[0])
    for row in (r for r in rows if r.table == "accounts"):
        locator = result.locators[row.row_uid]
        assert locator.file == "custodian_accounts.csv"
        assert locator.sheet is None
        assert f'"{row.values["account.number"]}"' in lines[locator.row_number - 1]
    assert min(loc.row_number for loc in result.locators.values()) == 4  # after 2 notes + header


def test_output_is_byte_identical_across_runs(tmp_path: Path) -> None:
    def run(folder: Path) -> bytes:
        firm: TruthFirm = build_firm(load_profile(), 15, 42)
        exporter = CustodianExporter.for_firm(firm)
        return exporter.write(exporter.project(firm), folder).files[0].read_bytes()

    assert run(tmp_path / "a") == run(tmp_path / "b")


def test_no_household_or_email_columns() -> None:
    headers = [c.header for c in CustodianExporter.for_firm(FIRM).profile.tables[0].columns]
    assert not any("household" in h.lower() or "email" in h.lower() for h in headers)

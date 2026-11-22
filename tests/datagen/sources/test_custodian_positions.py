import csv
import io
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pytest

from onboardkit.datagen.config import resolve_config
from onboardkit.datagen.pipeline import build_rows, generate_dataset
from onboardkit.datagen.sources.base import known_concepts
from onboardkit.datagen.sources.custodian import CustodianExporter
from onboardkit.datagen.sources.custodian_positions import ASSET_CLASS_CODES
from onboardkit.datagen.sources.formatters import apply_formatter
from onboardkit.datagen.truth.builder import build_firm
from onboardkit.datagen.truth.profile import AssetClass, load_profile

FIRM = build_firm(load_profile(), 15, 42)


@pytest.fixture(scope="module")
def positions_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("positions")
    exporter = CustodianExporter.for_firm(FIRM)
    result = exporter.write(exporter.project(FIRM), out)
    return next(f for f in result.files if f.name == "custodian_positions.csv")


def _records(path: Path) -> list[list[str]]:
    return list(csv.reader(io.StringIO(path.read_bytes().decode("utf-8-sig"))))


def test_first_lines_snapshot(positions_file: Path) -> None:
    lines = positions_file.read_bytes().decode("utf-8-sig").split("\r\n")
    assert lines[:5] == [
        '"MERIDIAN CUSTODY SERVICES - POSITION REPORT"',
        '"Report date: 12/31/2025"',
        '"Acct #","Symbol","Security Description","Asset Class","Quantity","Price",'
        '"Market Value","Price Date"',
        '"MC143753","CASH","CASH AND MONEY MARKET","CASH","1,077.8500","1.0000","1,077.85",'
        '"20251231"',
        '"MC143753","SJKG","DRIFTWOOD NETWORKS INC","EQ","25.1339","98.0495","2,464.37","20251231"',
    ]


def test_bytes_bom_and_crlf(positions_file: Path) -> None:
    data = positions_file.read_bytes()
    assert data.startswith(b"\xef\xbb\xbf")
    assert data.endswith(b"\r\n")
    assert data.replace(b"\r\n", b"").count(b"\n") == 0


def test_trailer_counts_the_data_rows(positions_file: Path) -> None:
    records = _records(positions_file)
    data = records[3:-1]
    assert records[-1] == [f"Total positions: {len(data)}"]
    assert len(data) == len(FIRM.holdings)


def test_values_use_the_documented_formats(positions_file: Path) -> None:
    records = _records(positions_file)
    header, data = records[2], records[3:-1]
    securities = {s.security_id: s for s in FIRM.securities}
    holdings = iter(FIRM.holdings)
    for record in data:
        row = dict(zip(header, record, strict=True))
        holding = next(holdings)
        security = securities[holding.security_id]
        assert row["Symbol"] == security.symbol.upper()
        assert row["Security Description"] == security.name.upper()
        assert row["Asset Class"] == ASSET_CLASS_CODES[security.asset_class.value]
        assert row["Quantity"] == f"{holding.quantity:,.4f}"
        assert row["Price"] == f"{security.price:.4f}"
        assert row["Market Value"] == f"{holding.value:,.2f}"
        assert row["Price Date"] == "20251231"


def test_positions_of_an_account_add_up_to_its_market_value(positions_file: Path) -> None:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for record in _records(positions_file)[3:-1]:
        totals[record[0]] += Decimal(record[6].replace(",", ""))
    assert {a.account_number: a.balance for a in FIRM.accounts} == dict(totals)


def test_asset_class_codes_cover_every_class() -> None:
    assert set(ASSET_CLASS_CODES) == {c.value for c in AssetClass}


def test_every_column_concept_exists_in_the_catalogue() -> None:
    table = CustodianExporter.for_firm(FIRM).profile.table("positions")
    assert {c.concept for c in table.columns} <= known_concepts()
    assert {c.header for c in table.columns} >= {"Acct #", "Quantity", "Price", "Market Value"}


def test_position_rows_carry_only_a_holding_reference() -> None:
    rows = [r for r in CustodianExporter.for_firm(FIRM).project(FIRM) if r.table == "positions"]
    assert len(rows) == len(FIRM.holdings)
    assert all(r.refs.holding_id and not r.refs.account_id for r in rows)
    assert len({r.row_uid for r in rows}) == len(rows)


@pytest.mark.parametrize("seed", [3, 8, 13])
def test_positions_follow_their_account_through_coverage(seed: int) -> None:
    built = build_rows(resolve_config("nightmare", 40, seed))
    custodian = built.data["custodian"]
    account_of = {h.holding_id: h.account_id for h in built.firm.holdings}
    exported = {row.refs.account_id for row in custodian["accounts"]}
    positioned = {account_of[str(row.refs.holding_id)] for row in custodian["positions"]}
    assert positioned == exported  # every holding is held in an account, so none is lost or alone
    omitted = [
        e for e in built.coverage_events if e.source == "custodian" and e.table == "accounts"
    ]
    assert omitted or seed != 3  # the seeds used do leave some custodian accounts out
    assert not {e.refs.account_id for e in omitted} & positioned


def test_a_clean_dataset_has_positions_for_every_account(tmp_path: Path) -> None:
    result = generate_dataset(resolve_config("clean", "sample", 42), tmp_path)
    assert result.counts["rows.custodian"] == result.counts["accounts"] + len(FIRM.holdings)


def test_decimal_formatter_places_commas_and_rejects_floats() -> None:
    assert (
        apply_formatter("decimal", Decimal("1234.5"), {"places": 4, "commas": True}) == "1,234.5000"
    )
    assert apply_formatter("decimal", Decimal("98.04954"), {"places": 4}) == "98.0495"
    assert apply_formatter("decimal", None, {}) == ""
    with pytest.raises(TypeError, match="never a float"):
        apply_formatter("decimal", 1.5, {})
    with pytest.raises(TypeError, match="needs a Decimal"):
        apply_formatter("decimal", "1.5", {})

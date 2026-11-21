from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from onboardkit.datagen.sources import base as base_module
from onboardkit.datagen.sources import formatters as formatters_module
from onboardkit.datagen.sources import writers as writers_module
from onboardkit.datagen.sources.base import (
    ColumnSpec,
    SourceProfile,
    SourceRow,
    TableSpec,
    TruthRefs,
)
from onboardkit.datagen.sources.writers import write_csv, write_csv_tables

COLUMNS = [
    ColumnSpec(concept="account.number", header="Acct #"),
    ColumnSpec(concept="account.balance", header="Market Value", formatter="money"),
    ColumnSpec(
        concept="account.open_date",
        header="Open Date",
        formatter="date",
        options={"pattern": "%m/%d/%Y"},
    ),
]


def _profile(**kwargs: Any) -> SourceProfile:
    table = kwargs.pop("table", None) or TableSpec(
        name="accounts", file_name="accounts.csv", columns=COLUMNS
    )
    return SourceProfile(source="demo", file_type="csv", tables=[table], **kwargs)


def _rows() -> list[SourceRow]:
    return [
        SourceRow(
            row_uid=f"demo:accounts:{i:06d}",
            source="demo",
            table="accounts",
            values={
                "account.number": f"MC00000{i}",
                "account.balance": Decimal(i) * Decimal("1000.5"),
                "account.open_date": date(2020, 1, i),
            },
            refs=TruthRefs(account_id=f"ACCT-{i:06d}"),
        )
        for i in (3, 1, 2)  # deliberately out of order
    ]


def test_unknown_concept_fails_with_clear_message() -> None:
    bad = TableSpec(
        name="t", file_name="t.csv", columns=[ColumnSpec(concept="account.numbr", header="x")]
    )
    with pytest.raises(ValidationError, match=r"unknown concept 'account.numbr'"):
        _profile(table=bad)


def test_unknown_formatter_fails() -> None:
    bad = TableSpec(
        name="t",
        file_name="t.csv",
        columns=[ColumnSpec(concept="account.number", header="x", formatter="shout")],
    )
    with pytest.raises(ValidationError, match="unknown formatter"):
        _profile(table=bad)


def test_duplicate_headers_and_concepts_rejected() -> None:
    with pytest.raises(ValidationError, match="repeats a header"):
        TableSpec(
            name="t",
            file_name="t.csv",
            columns=[
                ColumnSpec(concept="account.number", header="x"),
                ColumnSpec(concept="account.type", header="x"),
            ],
        )
    with pytest.raises(ValidationError, match="repeats a concept with the same options"):
        TableSpec(
            name="t",
            file_name="t.csv",
            columns=[
                ColumnSpec(concept="account.number", header="a"),
                ColumnSpec(concept="account.number", header="b"),
            ],
        )


def test_csv_content_order_and_locators(tmp_path: Path) -> None:
    profile = _profile()
    path = tmp_path / "accounts.csv"
    locators = write_csv(profile, profile.tables[0], _rows(), path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "Acct #,Market Value,Open Date"
    assert [line.split(",")[0] for line in lines[1:]] == ["MC000001", "MC000002", "MC000003"]
    assert lines[1] == "MC000001,1000.50,01/01/2020"
    assert locators["demo:accounts:000001"].row_number == 2
    assert locators["demo:accounts:000003"].row_number == 4
    assert locators["demo:accounts:000002"].file == "accounts.csv"


def test_preamble_and_trailer_shift_locators(tmp_path: Path) -> None:
    table = TableSpec(
        name="accounts",
        file_name="accounts.csv",
        columns=COLUMNS,
        preamble=["Account Master Report", "Run date: 12/31/2025", ""],
        trailer=["", "Total accounts: 3"],
    )
    profile = _profile(table=table)
    path = tmp_path / "accounts.csv"
    locators = write_csv(profile, table, _rows(), path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert table.header_line == 4
    assert lines[table.header_line - 1] == "Acct #,Market Value,Open Date"
    for row in _rows():
        locator = locators[row.row_uid]
        assert lines[locator.row_number - 1].startswith(row.values["account.number"])
    assert lines[-1] == "Total accounts: 3"
    assert len(lines) == 3 + 1 + 3 + 2


def test_encoding_delimiter_and_line_ending_from_bytes(tmp_path: Path) -> None:
    profile = _profile(encoding="utf-8-sig", delimiter=";", line_ending="\r\n")
    path = tmp_path / "accounts.csv"
    write_csv(profile, profile.tables[0], _rows(), path)
    data = path.read_bytes()
    assert data.startswith(b"\xef\xbb\xbf")
    assert b"Acct #;Market Value;Open Date\r\n" in data
    assert data.count(b"\r\n") == 4
    assert b"\r\r" not in data
    assert data.replace(b"\r\n", b"").count(b"\n") == 0


def test_non_utf8_encoding(tmp_path: Path) -> None:
    table = TableSpec(
        name="t",
        file_name="t.csv",
        columns=[ColumnSpec(concept="account.registration", header="Title")],
    )
    profile = _profile(table=table, encoding="cp1252")
    row = SourceRow(
        row_uid="demo:t:1", source="demo", table="t", values={"account.registration": "JOSÉ"}
    )
    path = tmp_path / "t.csv"
    write_csv(profile, table, [row], path)
    assert path.read_bytes().endswith(b"JOS\xc9\n")


def test_unencodable_character_raises(tmp_path: Path) -> None:
    table = TableSpec(
        name="t",
        file_name="t.csv",
        columns=[ColumnSpec(concept="account.registration", header="Title")],
    )
    profile = _profile(table=table, encoding="ascii")
    row = SourceRow(
        row_uid="demo:t:1", source="demo", table="t", values={"account.registration": "JOSÉ"}
    )
    with pytest.raises(UnicodeEncodeError):
        write_csv(profile, table, [row], tmp_path / "t.csv")


def test_line_break_in_a_cell_is_rejected(tmp_path: Path) -> None:
    table = TableSpec(
        name="t",
        file_name="t.csv",
        columns=[ColumnSpec(concept="meta.notes", header="Notes")],
    )
    profile = _profile(table=table)
    row = SourceRow(
        row_uid="demo:t:1", source="demo", table="t", values={"meta.notes": "line1\nline2"}
    )
    with pytest.raises(ValueError, match="line break"):
        write_csv(profile, table, [row], tmp_path / "t.csv")


def test_missing_values_become_empty_cells(tmp_path: Path) -> None:
    profile = _profile()
    row = SourceRow(
        row_uid="demo:accounts:1",
        source="demo",
        table="accounts",
        values={"account.number": "MC000009"},
    )
    path = tmp_path / "a.csv"
    write_csv(profile, profile.tables[0], [row], path)
    assert path.read_text(encoding="utf-8").splitlines()[1] == "MC000009,,"


def test_commas_and_quotes_are_escaped(tmp_path: Path) -> None:
    table = TableSpec(
        name="t",
        file_name="t.csv",
        columns=[ColumnSpec(concept="meta.notes", header="Notes")],
    )
    profile = _profile(table=table)
    row = SourceRow(
        row_uid="demo:t:1", source="demo", table="t", values={"meta.notes": 'said "hi", left'}
    )
    path = tmp_path / "t.csv"
    write_csv(profile, table, [row], path)
    assert path.read_text(encoding="utf-8").splitlines()[1] == '"said ""hi"", left"'


def test_output_is_stable_across_runs_and_input_order(tmp_path: Path) -> None:
    profile = _profile()
    table = profile.tables[0]
    write_csv(profile, table, _rows(), tmp_path / "one.csv")
    write_csv(profile, table, list(reversed(_rows())), tmp_path / "two.csv")
    assert (tmp_path / "one.csv").read_bytes() == (tmp_path / "two.csv").read_bytes()


def test_write_csv_tables_writes_each_table(tmp_path: Path) -> None:
    profile = _profile()
    result = write_csv_tables(profile, _rows(), tmp_path / "out")
    assert [p.name for p in result.files] == ["accounts.csv"]
    assert len(result.locators) == 3
    assert (tmp_path / "out" / "accounts.csv").is_file()


def test_xlsx_profile_not_supported_yet(tmp_path: Path) -> None:
    profile = SourceProfile(
        source="demo",
        file_type="xlsx",
        tables=[TableSpec(name="t", file_name="t.xlsx", sheet_name="S", columns=COLUMNS)],
    )
    with pytest.raises(NotImplementedError):
        write_csv_tables(profile, [], tmp_path)


def test_framework_modules_contain_no_source_specific_logic() -> None:
    for module in (base_module, formatters_module, writers_module):
        text = Path(module.__file__ or "").read_text(encoding="utf-8").lower()
        for word in ("meridian", "cedarline", "custodian", "crm", "book_of_business"):
            assert word not in text, (module.__name__, word)

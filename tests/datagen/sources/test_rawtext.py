import csv
from datetime import date
from pathlib import Path

import openpyxl

from onboardkit.datagen.sources.base import ColumnSpec, RawText, SourceRow, TableSpec, TruthRefs
from onboardkit.datagen.sources.book_of_business import BookOfBusinessExporter
from onboardkit.datagen.sources.crm import CrmExporter
from onboardkit.datagen.sources.writers import format_cell, format_row
from onboardkit.datagen.truth.builder import build_firm
from onboardkit.datagen.truth.profile import load_profile

TABLE = TableSpec(
    name="t",
    file_name="t.csv",
    columns=[
        ColumnSpec(concept="account.open_date", header="Opened", formatter="date"),
        ColumnSpec(concept="account.number", header="Acct #"),
    ],
)


def row(opened: object, number: object) -> SourceRow:
    return SourceRow(
        row_uid="x:t:1",
        source="x",
        table="t",
        values={"account.open_date": opened, "account.number": number},
        refs=TruthRefs(person_ids=(), household_id=None),
    )


def test_raw_text_is_written_verbatim_and_typed_values_still_format() -> None:
    typed = row(date(1980, 3, 4), "AB123456")
    raw = row(RawText("4 Mar 1980", date(1980, 3, 4)), RawText(" ab-123456 ", "AB123456"))
    assert format_row(TABLE, typed) == ["1980-03-04", "AB123456"]
    assert format_row(TABLE, raw) == ["4 Mar 1980", " ab-123456 "]
    assert format_cell(TABLE.columns[0], raw) == "4 Mar 1980"


def test_raw_text_keeps_the_original_value() -> None:
    value = RawText("03/04/80", date(1980, 3, 4))
    assert value.original == date(1980, 3, 4)
    assert value == RawText("03/04/80", date(1980, 3, 4))


def test_csv_file_contains_the_raw_text(tmp_path: Path) -> None:
    firm = build_firm(load_profile(), 15, 42)
    exporter = CrmExporter()
    rows = exporter.project(firm)
    target = next(r for r in rows if r.table == "contacts")
    target.values["person.date_of_birth"] = RawText("March 4, 1980", date(1980, 3, 4))
    target.values["person.address_state"] = RawText("New York", "NY")
    exporter.write(rows, tmp_path)
    with (tmp_path / "crm_contacts.csv").open(encoding="utf-8", newline="") as handle:
        records = list(csv.DictReader(handle))
    assert records[0]["date_of_birth"] == "March 4, 1980"
    assert records[0]["state"] == "New York"


def test_workbook_cell_holds_raw_text(tmp_path: Path) -> None:
    firm = build_firm(load_profile(), 15, 42)
    exporter = BookOfBusinessExporter()
    rows = exporter.project(firm)
    target = next(r for r in rows if r.table == "accounts")
    original = target.values["meta.review_date"]
    target.values["meta.review_date"] = RawText("5th Jan 2025", original)
    result = exporter.write(rows, tmp_path)
    locator = result.locators[target.row_uid]
    sheet = openpyxl.load_workbook(result.files[0])[str(locator.sheet)]
    values = [c.value for c in sheet[locator.row_number]]
    assert "5th Jan 2025" in values

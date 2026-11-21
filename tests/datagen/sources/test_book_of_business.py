import zipfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest
from openpyxl.worksheet.worksheet import Worksheet

from onboardkit.datagen.config import BookOfBusinessConfig
from onboardkit.datagen.sources.base import SourceRow, WriteResult, known_concepts
from onboardkit.datagen.sources.book_of_business import (
    ARCHIVE_SHEET,
    FIRST_DATA_ROW,
    HEADER_ROW,
    TYPE_LABELS,
    BookOfBusinessExporter,
    advisor_sheet_name,
    stale_balance,
)
from onboardkit.datagen.sources.xlsx_utils import ZIP_TIME
from onboardkit.datagen.truth.builder import build_firm
from onboardkit.datagen.truth.profile import AccountStatus, AccountType, load_profile

FIRM = build_firm(load_profile(), 15, 42)
Built = tuple[BookOfBusinessExporter, list[SourceRow], WriteResult]


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Built:
    exporter = BookOfBusinessExporter()
    rows = exporter.project(FIRM)
    return exporter, rows, exporter.write(rows, tmp_path_factory.mktemp("bob"))


def _sheet(result: WriteResult, name: str) -> Worksheet:
    sheet = openpyxl.load_workbook(result.files[0])[name]
    assert isinstance(sheet, Worksheet)
    return sheet


def test_sheet_names(built: Built) -> None:
    names = openpyxl.load_workbook(built[2].files[0]).sheetnames
    advisors = [advisor_sheet_name(a.name) for a in FIRM.profile.advisors]
    assert names == ["Summary", *advisors, ARCHIVE_SHEET]


def test_advisor_sheet_layout(built: Built) -> None:
    sheet = _sheet(built[2], advisor_sheet_name(FIRM.profile.advisors[0].name))
    assert sheet["A1"].value == "Lantern Ridge Wealth Partners - Book of Business"
    assert sheet["A2"].value == f"Advisor: {FIRM.profile.advisors[0].name}"
    assert sheet["A3"].value == "Updated: 31-Dec-2025"
    assert all(cell.value is None for cell in sheet[4])
    headers = [c.value for c in sheet[HEADER_ROW]][:7]
    assert headers == ["Household", "Advisor", "AcctNo", "Type", "Balance", "Notes", "Last Review"]


def test_spacer_row_after_each_household_and_name_only_on_first_row(built: Built) -> None:
    sheet = _sheet(built[2], advisor_sheet_name(FIRM.profile.advisors[0].name))
    blocks: list[list[tuple[object, ...]]] = [[]]
    for values in sheet.iter_rows(min_row=FIRST_DATA_ROW, values_only=True):
        if all(v is None for v in values):
            if blocks[-1]:
                blocks.append([])
        else:
            blocks[-1].append(values)
    blocks = [b for b in blocks if b]
    assert len(blocks) >= 2
    for block in blocks:
        assert block[0][0] is not None
        assert all(row[0] is None for row in block[1:])
        assert all(row[2] is not None for row in block)


def test_couple_label_style(built: Built) -> None:
    labels = {str(r.values["household.name"]) for r in built[1]}
    assert any(" & " in label and ", " in label for label in labels)
    assert all(", " in label for label in labels)


def test_closed_accounts_only_on_archive(built: Built) -> None:
    _, rows, result = built
    closed = {a.account_number for a in FIRM.accounts if a.status is AccountStatus.CLOSED}
    assert closed, "sample should contain a closed account"
    archive = {r[2] for r in _sheet(result, ARCHIVE_SHEET).iter_rows(min_row=6, values_only=True)}
    assert closed <= archive
    for advisor in FIRM.profile.advisors:
        sheet = _sheet(result, advisor_sheet_name(advisor.name))
        numbers = {r[2] for r in sheet.iter_rows(min_row=6, values_only=True)}
        assert not numbers & closed
    assert len(rows) == len(FIRM.accounts)


def test_balances_rounded_drifted_and_positive(built: Built) -> None:
    _, rows, _ = built
    truth = {a.account_id: a.balance for a in FIRM.accounts}
    differing = 0
    for row in rows:
        balance = row.values["account.balance"]
        assert isinstance(balance, Decimal)
        assert balance > 0
        assert balance % 100 == 0
        original = truth[str(row.refs.account_id)]
        if balance != original:
            differing += 1
        assert abs(balance - original) <= original * Decimal("0.12") + 50
    assert differing > 0


def test_clean_settings_give_zero_drift() -> None:
    exact = BookOfBusinessExporter(BookOfBusinessConfig(inherent_drift=0.0, round_to=0.01))
    truth = {a.account_id: a.balance for a in FIRM.accounts}
    for row in exact.project(FIRM):
        assert row.values["account.balance"] == truth[str(row.refs.account_id)]


def test_stale_balance_never_zero_or_negative() -> None:
    class Rng:
        def gauss(self, mu: float, sigma: float) -> float:
            return -1.0

    assert stale_balance(Decimal("10.00"), 0.12, Decimal("100"), Rng()) == Decimal("100")


def test_account_numbers_are_text_and_dates_are_dates(built: Built) -> None:
    sheet = _sheet(built[2], advisor_sheet_name(FIRM.profile.advisors[0].name))
    data = [row for row in sheet.iter_rows(min_row=6) if row[2].value is not None]
    assert data
    for row in data:
        assert row[2].data_type == "s"
        assert row[2].number_format == "@"
        assert isinstance(row[6].value, datetime)
        assert row[6].number_format == "d-mmm-yy"
        assert row[4].number_format == '"$"#,##0.00'


def test_acctno_header_present(built: Built) -> None:
    sheet = _sheet(built[2], ARCHIVE_SHEET)
    assert "AcctNo" in [c.value for c in sheet[HEADER_ROW]]


def test_summary_values_are_plain_numbers(built: Built) -> None:
    _, rows, result = built
    sheet = _sheet(result, "Summary")
    table = {
        r[0]: (r[1], r[2])
        for r in sheet.iter_rows(min_row=FIRST_DATA_ROW, values_only=True)
        if r[0]
    }
    assert set(table) == {a.name for a in FIRM.profile.advisors}
    open_rows = [r for r in rows if r.table == "accounts"]
    assert sum(count for count, _ in table.values()) == len(
        {(r.values["household.advisor"], r.refs.household_id) for r in open_rows}
    )
    expected = sum((r.values["account.balance"] for r in open_rows), Decimal(0))
    assert sum(Decimal(str(total)) for _, total in table.values()) == expected
    assert not any(
        isinstance(c.value, str) and c.value.startswith("=") for r in sheet.iter_rows() for c in r
    )


def test_locators_point_at_the_right_sheet_and_row(built: Built) -> None:
    _, rows, result = built
    assert len(result.locators) == len(rows)
    workbook = openpyxl.load_workbook(result.files[0])
    for row in rows:
        locator = result.locators[row.row_uid]
        assert locator.file == "book_of_business.xlsx"
        assert locator.sheet is not None
        sheet = workbook[locator.sheet]
        assert sheet.cell(row=locator.row_number, column=3).value == row.values["account.number"]
        if row.table == "archive":
            assert locator.sheet == ARCHIVE_SHEET
        else:
            assert locator.sheet == advisor_sheet_name(str(row.values["household.advisor"]))


def test_every_column_concept_exists_in_catalogue() -> None:
    columns = [c for t in BookOfBusinessExporter().profile.tables for c in t.columns]
    assert {c.concept for c in columns} <= known_concepts()


def test_type_labels_cover_every_type() -> None:
    assert set(TYPE_LABELS) == {t.value for t in AccountType}
    assert {"Joint", "Roth", "IRA", "529", "Indiv"} == set(TYPE_LABELS.values())


def test_no_merged_cells(built: Built) -> None:
    workbook = openpyxl.load_workbook(built[2].files[0])
    assert all(not ws.merged_cells.ranges for ws in workbook.worksheets)


def test_output_is_byte_identical_across_runs(tmp_path: Path) -> None:
    def run(folder: Path) -> bytes:
        exporter = BookOfBusinessExporter()
        return exporter.write(exporter.project(FIRM), folder).files[0].read_bytes()

    assert run(tmp_path / "a") == run(tmp_path / "b")


def test_zip_entries_are_normalised(built: Built) -> None:
    with zipfile.ZipFile(built[2].files[0]) as archive:
        infos = archive.infolist()
        assert [i.filename for i in infos] == sorted(i.filename for i in infos)
        assert all(i.date_time == ZIP_TIME for i in infos)
        core = archive.read("docProps/core.xml").decode("utf-8")
    assert "onboardkit" in core
    assert "2025-12-31T12:00:00" in core

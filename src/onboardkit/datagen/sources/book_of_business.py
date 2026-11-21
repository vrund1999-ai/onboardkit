"""The Book of Business source: the spreadsheet operations staff keep on the side.

Hand-maintained in style: title rows, a sheet per advisor, a blank row after each household,
household names on the first row of a block only, and balances that are rounded and a little
stale. The lowest-priority source.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from onboardkit.datagen.config import BookOfBusinessConfig
from onboardkit.datagen.rng import derive_rng
from onboardkit.datagen.sources.base import (
    ColumnSpec,
    RawText,
    RowLocator,
    SourceProfile,
    SourceRow,
    TableSpec,
    TruthRefs,
    WriteResult,
)
from onboardkit.datagen.sources.writers import format_cell
from onboardkit.datagen.sources.xlsx_utils import save_deterministic, stamp_for
from onboardkit.datagen.truth.model import HouseholdRole, TruthFirm, TruthHousehold, TruthPerson
from onboardkit.datagen.truth.profile import AccountStatus, AccountType

SOURCE = "book_of_business"
ACCOUNTS = "accounts"
ARCHIVE = "archive"
FILE_NAME = "book_of_business.xlsx"
SUMMARY_SHEET = "Summary"
ARCHIVE_SHEET = "Archive"
HEADER_ROW = 5
FIRST_DATA_ROW = 6

TYPE_LABELS = {
    AccountType.INDIVIDUAL.value: "Indiv",
    AccountType.JOINT.value: "Joint",
    AccountType.TRADITIONAL_IRA.value: "IRA",
    AccountType.ROTH_IRA.value: "Roth",
    AccountType.ROLLOVER_IRA.value: "IRA",
    AccountType.EDUCATION_529.value: "529",
}
NOTE_PHRASES = (
    "needs W-9",
    "moving to new address",
    "call re: beneficiary",
    "check RMD",
    "statement returned",
    "waiting on transfer paperwork",
)
NOTE_PROBABILITY = 0.08
REVIEW_WINDOW_DAYS = 540
CURRENCY_FORMAT = '"$"#,##0.00'
DATE_FORMAT = "d-mmm-yy"
COLUMN_WIDTHS = (30, 18, 12, 8, 16, 30, 12)


def advisor_sheet_name(advisor: str) -> str:
    return f"Advisor - {advisor}"


def _columns() -> list[ColumnSpec]:
    return [
        ColumnSpec(concept="household.name", header="Household"),
        ColumnSpec(concept="household.advisor", header="Advisor"),
        ColumnSpec(concept="account.number", header="AcctNo"),
        ColumnSpec(
            concept="account.type", header="Type", formatter="map", options={"mapping": TYPE_LABELS}
        ),
        ColumnSpec(
            concept="account.balance",
            header="Balance",
            formatter="money",
            options={"style": "number"},
        ),
        ColumnSpec(concept="meta.notes", header="Notes"),
        ColumnSpec(concept="meta.review_date", header="Last Review", formatter="excel_date"),
    ]


def build_profile() -> SourceProfile:
    return SourceProfile(
        source=SOURCE,
        file_type="xlsx",
        tables=[
            TableSpec(name=ACCOUNTS, file_name=FILE_NAME, columns=_columns()),
            TableSpec(
                name=ARCHIVE, file_name=FILE_NAME, sheet_name=ARCHIVE_SHEET, columns=_columns()
            ),
        ],
    )


def household_label(household: TruthHousehold, members: list[TruthPerson]) -> str:
    """``Smith, John & Jane`` for a couple, ``Smith, John`` for one adult."""
    adults = [m for m in members if m.household_role is not HouseholdRole.DEPENDENT]
    primary = adults[0]
    label = f"{primary.last_name}, {primary.first_name}"
    if len(adults) > 1:
        spouse = adults[1]
        same = spouse.last_name == primary.last_name
        label += f" & {spouse.first_name}" + ("" if same else f" {spouse.last_name}")
    return label


def stale_balance(truth: Decimal, drift: float, step: Decimal, rng: Any) -> Decimal:
    """Truth balance times a small drift factor, rounded to ``step``; never zero or negative."""
    if drift > 0:
        factor = max(-drift, min(drift, rng.gauss(0.0, drift / 2)))
        truth = truth * (Decimal(1) + Decimal(str(round(factor, 6))))
    units = (truth / step).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
    amount = units * step
    return amount if amount > 0 else step


class BookOfBusinessExporter:
    """Projects the truth into the workbook and writes it."""

    def __init__(self, config: BookOfBusinessConfig | None = None) -> None:
        self.config = config or BookOfBusinessConfig()
        self.profile = build_profile()
        self.firm_name = ""
        self.advisors: tuple[str, ...] = ()
        self.as_of_date = date(1970, 1, 1)

    def project(self, firm: TruthFirm) -> list[SourceRow]:
        """One row per truth account: open and restricted ones on their advisor's sheet."""
        self.firm_name = firm.profile.firm.name
        self.advisors = tuple(a.name for a in firm.profile.advisors)
        self.as_of_date = firm.as_of_date
        people = firm.people_by_id()
        households = firm.households_by_id()
        step = Decimal(str(self.config.round_to))
        labels = {
            h.household_id: household_label(h, [people[m] for m in h.member_ids])
            for h in firm.households
        }
        rows: list[SourceRow] = []
        for account in firm.accounts:
            household = households[account.household_id]
            rng = derive_rng(firm.root_seed, SOURCE, account.account_id)
            balance = stale_balance(account.balance, self.config.inherent_drift, step, rng)
            note = rng.choice(NOTE_PHRASES) if rng.random() < NOTE_PROBABILITY else None
            reviewed = firm.as_of_date - timedelta(days=rng.randrange(REVIEW_WINDOW_DAYS))
            closed = account.status is AccountStatus.CLOSED
            rows.append(
                SourceRow(
                    row_uid=f"{SOURCE}:{ARCHIVE if closed else ACCOUNTS}:"
                    f"{account.account_id.removeprefix('ACCT-')}",
                    source=SOURCE,
                    table=ARCHIVE if closed else ACCOUNTS,
                    values={
                        "household.name": labels[household.household_id],
                        "household.advisor": household.advisor,
                        "account.number": account.account_number,
                        "account.type": account.account_type,
                        "account.balance": balance,
                        "meta.notes": note,
                        "meta.review_date": reviewed,
                    },
                    refs=TruthRefs(
                        person_ids=account.owner_ids,
                        household_id=household.household_id,
                        account_id=account.account_id,
                    ),
                )
            )
        return rows

    def write(self, rows: list[SourceRow], out_dir: Path) -> WriteResult:
        workbook = Workbook()
        summary = workbook.active
        assert isinstance(summary, Worksheet)
        summary.title = SUMMARY_SHEET
        locators: dict[str, RowLocator] = {}

        by_advisor: dict[str, list[SourceRow]] = defaultdict(list)
        archived: list[SourceRow] = []
        for row in rows:
            if row.table == ARCHIVE:
                archived.append(row)
            else:
                by_advisor[str(row.values["household.advisor"])].append(row)
        extra = sorted(set(by_advisor) - set(self.advisors))
        advisors = [*self.advisors, *extra]

        totals: list[tuple[str, int, Decimal]] = []
        for advisor in advisors:
            members = by_advisor.get(advisor, [])
            sheet = workbook.create_sheet(advisor_sheet_name(advisor))
            self._write_sheet(sheet, self.profile.table(ACCOUNTS), members, f"Advisor: {advisor}")
            locators.update(self._locators(sheet.title, members))
            households = {r.refs.household_id for r in members}
            totals.append(
                (advisor, len(households), sum((_balance(r) for r in members), Decimal(0)))
            )

        archive = workbook.create_sheet(ARCHIVE_SHEET)
        self._write_sheet(
            archive,
            self.profile.table(ARCHIVE),
            archived,
            "Closed accounts and departed households",
        )
        locators.update(self._locators(ARCHIVE_SHEET, archived))
        self._write_summary(summary, totals)

        path = out_dir / FILE_NAME
        save_deterministic(workbook, path, stamp_for(self.as_of_date))
        return WriteResult(files=[path], locators=locators)

    def _title_rows(self, sheet: Worksheet, second_line: str) -> None:
        sheet["A1"] = f"{self.firm_name} - Book of Business"
        sheet["A1"].font = Font(bold=True, size=14)
        sheet["A2"] = second_line
        sheet["A3"] = f"Updated: {self.as_of_date.strftime('%d-%b-%Y')}"

    def _write_summary(self, sheet: Worksheet, totals: list[tuple[str, int, Decimal]]) -> None:
        self._title_rows(sheet, "Summary by advisor")
        for index, header in enumerate(("Advisor", "Households", "Total Balance"), start=1):
            cell = sheet.cell(row=HEADER_ROW, column=index, value=header)
            cell.font = Font(bold=True)
        for offset, (advisor, count, total) in enumerate(totals):
            row = FIRST_DATA_ROW + offset
            sheet.cell(row=row, column=1, value=advisor)
            sheet.cell(row=row, column=2, value=count)
            cell = sheet.cell(row=row, column=3, value=total)
            cell.number_format = CURRENCY_FORMAT
        for letter, width in zip("ABC", (24, 12, 18), strict=True):
            sheet.column_dimensions[letter].width = width

    def _layout(self, rows: list[SourceRow]) -> list[tuple[int, SourceRow, bool]]:
        """Excel row for each source row, and whether it opens its household's block."""
        blocks: dict[str, list[SourceRow]] = defaultdict(list)
        for row in rows:
            blocks[str(row.refs.household_id)].append(row)
        placed: list[tuple[int, SourceRow, bool]] = []
        excel_row = FIRST_DATA_ROW
        for household_id in sorted(blocks):
            for position, row in enumerate(sorted(blocks[household_id], key=lambda r: r.row_uid)):
                placed.append((excel_row, row, position == 0))
                excel_row += 1
            excel_row += 1  # blank spacer row after every household
        return placed

    def _locators(self, sheet_name: str, rows: list[SourceRow]) -> dict[str, RowLocator]:
        return {
            row.row_uid: RowLocator(file=FILE_NAME, sheet=sheet_name, row_number=excel_row)
            for excel_row, row, _ in self._layout(rows)
        }

    def _write_sheet(
        self, sheet: Worksheet, table: TableSpec, rows: list[SourceRow], second_line: str
    ) -> None:
        self._title_rows(sheet, second_line)
        for index, column in enumerate(table.columns, start=1):
            sheet.cell(row=HEADER_ROW, column=index, value=column.header).font = Font(bold=True)
        for letter, width in zip("ABCDEFG", COLUMN_WIDTHS, strict=True):
            sheet.column_dimensions[letter].width = width
        for excel_row, row, first_in_block in self._layout(rows):
            for index, column in enumerate(table.columns, start=1):
                value = format_cell(column, row)
                if column.concept == "household.name" and not first_in_block:
                    value = ""
                if value == "":
                    continue
                cell = sheet.cell(row=excel_row, column=index, value=value)
                if isinstance(row.values.get(column.concept), RawText):
                    continue  # pre-formatted text keeps the cell's default format
                if column.concept == "account.number":
                    cell.number_format = "@"
                elif column.concept == "account.balance":
                    cell.number_format = CURRENCY_FORMAT
                elif column.concept == "meta.review_date":
                    cell.number_format = DATE_FORMAT


def _balance(row: SourceRow) -> Decimal:
    value = row.values["account.balance"]
    if isinstance(value, RawText):
        value = value.original
    assert isinstance(value, Decimal)
    return value

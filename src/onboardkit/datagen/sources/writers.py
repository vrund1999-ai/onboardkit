"""File writers shared by every source. Spreadsheet writing arrives with E2-S4."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path

from onboardkit.datagen.sources.base import (
    RowLocator,
    SourceProfile,
    SourceRow,
    TableSpec,
    WriteResult,
)
from onboardkit.datagen.sources.formatters import apply_formatter


def format_row(table: TableSpec, row: SourceRow) -> list[str]:
    """Format one row's values in the table's column order. Missing concepts become empty."""
    cells: list[str] = []
    for column in table.columns:
        formatted = apply_formatter(
            column.formatter, row.values.get(column.concept), column.options
        )
        text = f"{formatted:f}" if isinstance(formatted, Decimal) else formatted
        if "\n" in text or "\r" in text:
            raise ValueError(f"{row.row_uid}: {column.header!r} contains a line break")
        cells.append(text)
    return cells


def write_csv(
    profile: SourceProfile,
    table: TableSpec,
    rows: Iterable[SourceRow],
    path: Path,
) -> dict[str, RowLocator]:
    """Write one table as CSV and return where each row landed.

    Lines are, in order: the preamble (raw), the header, the rows (sorted by ``row_uid`` so output
    is stable), and the trailer (raw). Row numbers count lines as an editor would show them.
    """
    ordered = sorted(rows, key=lambda r: r.row_uid)
    path.parent.mkdir(parents=True, exist_ok=True)
    locators: dict[str, RowLocator] = {}
    ending = profile.line_ending
    # newline="" stops the text layer translating line endings (double CRs on Windows).
    with path.open("w", encoding=profile.encoding, newline="") as handle:
        for line in table.preamble:
            handle.write(line + ending)
        writer = csv.writer(handle, delimiter=profile.delimiter, lineterminator=ending)
        writer.writerow([c.header for c in table.columns])
        line_number = table.header_line
        for row in ordered:
            line_number += 1
            writer.writerow(format_row(table, row))
            locators[row.row_uid] = RowLocator(
                file=table.file_name, sheet=None, row_number=line_number
            )
        for line in table.trailer:
            handle.write(line + ending)
    return locators


def write_csv_tables(profile: SourceProfile, rows: list[SourceRow], out_dir: Path) -> WriteResult:
    """Write every table of a CSV profile into ``out_dir``."""
    if profile.file_type != "csv":
        raise NotImplementedError("only CSV profiles are supported until E2-S4")
    result = WriteResult()
    for table in profile.tables:
        table_rows = [r for r in rows if r.table == table.name]
        path = out_dir / table.file_name
        result.locators.update(write_csv(profile, table, table_rows, path))
        result.files.append(path)
    return result

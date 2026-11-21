"""File writers shared by every source. Spreadsheet writing arrives with E2-S4."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, TextIO

from onboardkit.datagen.sources.base import (
    RowLocator,
    SourceProfile,
    SourceRow,
    TableSpec,
    WriteResult,
)
from onboardkit.datagen.sources.formatters import Formatted, apply_formatter


def format_row_native(table: TableSpec, row: SourceRow) -> list[Formatted]:
    """Format one row's values in column order, keeping dates and decimals as real values."""
    return [
        apply_formatter(column.formatter, row.values.get(column.concept), column.options)
        for column in table.columns
    ]


def to_text(value: Formatted) -> str:
    if isinstance(value, Decimal):
        return f"{value:f}"
    if isinstance(value, date):
        return value.isoformat()
    return value


def format_row(table: TableSpec, row: SourceRow) -> list[str]:
    """Format one row as text for a CSV. Missing concepts become empty cells."""
    cells = [to_text(value) for value in format_row_native(table, row)]
    for column, text in zip(table.columns, cells, strict=True):
        if "\n" in text or "\r" in text:
            raise ValueError(f"{row.row_uid}: {column.header!r} contains a line break")
    return cells


def _write_note(handle: TextIO, writer: Any, line: str, ending: str) -> None:
    """Write a preamble or trailer line: blank stays blank, text goes through the CSV writer so
    commas cannot be mistaken for column breaks."""
    if line:
        writer.writerow([line])
    else:
        handle.write(ending)


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
    quoting: Literal[0, 1] = csv.QUOTE_ALL if profile.quoting == "all" else csv.QUOTE_MINIMAL
    with path.open("w", encoding=profile.encoding, newline="") as handle:
        writer = csv.writer(
            handle, delimiter=profile.delimiter, lineterminator=ending, quoting=quoting
        )
        for line in table.preamble:
            _write_note(handle, writer, line, ending)
        writer.writerow([c.header for c in table.columns])
        line_number = table.header_line
        for row in ordered:
            line_number += 1
            writer.writerow(format_row(table, row))
            locators[row.row_uid] = RowLocator(
                file=table.file_name, sheet=None, row_number=line_number
            )
        for line in table.trailer:
            _write_note(handle, writer, line, ending)
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

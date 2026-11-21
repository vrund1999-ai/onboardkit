"""Column mapping answer key: the true meaning of every column of every exported file and sheet.

The truth is declared by the source profiles (each column carries a concept id), so this key is a
mechanical export of them. It does not depend on the seed: layouts are static. Header text is
never altered by the M0 mess types; a later mess type that changes headers must generate this key
from the headers as written.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook

from onboardkit.datagen.answer_keys.writer import read_table, write_table
from onboardkit.datagen.manifest import Problem
from onboardkit.datagen.pipeline import AnswerKeyContext
from onboardkit.datagen.sources.base import (
    ColumnSpec,
    HasSheets,
    SourceProfile,
    TableSpec,
    known_concepts,
)

COLUMN_MAPPINGS_FILE = "column_mappings.csv"
HEADER = (
    "source",
    "file",
    "sheet",
    "column_position",
    "header",
    "concept",
    "slice",
    "value_format",
    "notes",
)
NO_CONCEPT = "none"
SUMMARY_NOTE = "summary sheet: advisor totals, no concept"
CONTINUATION_NOTE = "blank on continuation rows of a household block"
CONTINUATION_CONCEPTS = {"household.name"}


def describe_format(column: ColumnSpec) -> str:
    """The formatter applied, with its option values (for example ``date:%m/%d/%Y``)."""
    options = {k: v for k, v in column.options.items() if k != "mapping"}
    if "mapping" in column.options:
        options["codes"] = len(column.options["mapping"])
    if not options:
        return column.formatter
    if set(options) == {"pattern"}:
        return f"{column.formatter}:{options['pattern']}"
    if set(options) == {"style"}:
        return f"{column.formatter}:{options['style']}"
    pairs = ",".join(f"{key}={options[key]}" for key in sorted(options))
    return f"{column.formatter}:{pairs}"


def _slices(table: TableSpec) -> dict[int, str]:
    """Slice index for columns that share a concept (owner 1 and owner 2), else nothing."""
    counts = Counter(c.concept for c in table.columns)
    seen: Counter[str] = Counter()
    result: dict[int, str] = {}
    for position, column in enumerate(table.columns):
        if counts[column.concept] > 1:
            index = column.options.get("index", seen[column.concept])
            result[position] = str(index)
        seen[column.concept] += 1
    return result


def _table_rows(
    source: str, file: str, sheet: str, table: TableSpec, header_row: int, xlsx: bool
) -> list[list[str]]:
    slices = _slices(table)
    rows = []
    for position, column in enumerate(table.columns):
        notes = []
        if header_row != 1:
            notes.append(f"header on row {header_row}")
        if xlsx and column.concept in CONTINUATION_CONCEPTS:
            notes.append(CONTINUATION_NOTE)
        rows.append(
            [
                source,
                file,
                sheet,
                str(position + 1),
                column.header,
                column.concept,
                slices.get(position, ""),
                describe_format(column),
                "; ".join(notes),
            ]
        )
    return rows


def build_column_mappings(context: AnswerKeyContext) -> list[list[str]]:
    """One row per column of every file and sheet, derived from the profiles."""
    rows: list[list[str]] = []
    for source, profile in context.profiles.items():
        rows += _source_rows(source, profile, context)
    return rows


def _source_rows(source: str, profile: SourceProfile, context: AnswerKeyContext) -> list[list[str]]:
    if profile.file_type == "csv":
        return [
            row
            for table in profile.tables
            for row in _table_rows(
                source, f"{source}/{table.file_name}", "", table, table.header_line, xlsx=False
            )
        ]
    exporter = context.exporters[source]
    if not isinstance(exporter, HasSheets):
        raise TypeError(f"{source} exporter cannot describe its sheets")
    rows: list[list[str]] = []
    file = f"{source}/{profile.tables[0].file_name}"
    for info in exporter.sheets(context.rows[source]):
        if info.table is None:
            for position, header in enumerate(info.headers):
                rows.append(
                    [source, file, info.sheet, str(position + 1), header, NO_CONCEPT, "", "",
                     "; ".join([f"header on row {info.header_row}", SUMMARY_NOTE])]
                )  # fmt: skip
        else:
            table = profile.table(info.table)
            rows += _table_rows(source, file, info.sheet, table, info.header_row, xlsx=True)
    return rows


def write_column_mappings(context: AnswerKeyContext) -> None:
    """Answer key writer: ``column_mappings.csv`` under ``truth/``."""
    write_table(
        context.truth_dir / COLUMN_MAPPINGS_FILE,
        HEADER,
        build_column_mappings(context),
        key=lambda row: (row[0], row[1], row[2], int(row[3])),
    )


def _file_header_rows(path: Path, sheet: str) -> list[list[str]]:
    if sheet:
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            rows = [
                ["" if v is None else str(v) for v in cells]
                for cells in workbook[sheet].iter_rows(values_only=True)
            ]
        finally:
            workbook.close()
    else:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = [list(cells) for cells in csv.reader(handle)]
    return [_trim(cells) for cells in rows]


def _trim(cells: list[str]) -> list[str]:
    while cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


def verify_column_mappings(dataset_dir: Path) -> list[Problem]:
    """Re-read the exports and confirm the key's headers and positions match the files exactly."""
    path = dataset_dir / "truth" / COLUMN_MAPPINGS_FILE
    if not path.is_file():
        return [Problem("missing", f"truth/{COLUMN_MAPPINGS_FILE}", "column mapping key not found")]
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for entry in read_table(path):
        groups[(entry["file"], entry["sheet"])].append(entry)
    problems: list[Problem] = []
    known = known_concepts()
    for (file, sheet), entries in sorted(groups.items()):
        where = f"{file}[{sheet}]" if sheet else file
        positions = [int(e["column_position"]) for e in entries]
        if sorted(positions) != list(range(1, len(entries) + 1)):
            problems.append(Problem("mapping", where, f"positions are not 1..{len(entries)}"))
            continue
        for entry in entries:
            if entry["concept"] != NO_CONCEPT and entry["concept"] not in known:
                problems.append(Problem("mapping", where, f"unknown concept {entry['concept']!r}"))
        target = dataset_dir / "exports" / file
        if not target.is_file():
            problems.append(Problem("missing", f"exports/{file}", "file named in the key"))
            continue
        headers = [e["header"] for e in sorted(entries, key=lambda e: int(e["column_position"]))]
        if headers not in _file_header_rows(target, sheet):
            problems.append(Problem("mapping", where, f"no row matches the headers {headers}"))
    problems += _unmapped_sheets(dataset_dir, groups)
    return problems


def _unmapped_sheets(
    dataset_dir: Path, groups: dict[tuple[str, str], list[dict[str, str]]]
) -> list[Problem]:
    """Every exported file (and every sheet of a workbook) must appear in the key."""
    problems = []
    exports = dataset_dir / "exports"
    for path in sorted(p for p in exports.rglob("*") if p.is_file()):
        file = path.relative_to(exports).as_posix()
        if path.suffix == ".xlsx":
            workbook = load_workbook(path, read_only=True)
            try:
                names = list(workbook.sheetnames)
            finally:
                workbook.close()
            problems += [
                Problem("unrecorded", f"{file}[{name}]", "sheet has no column mapping")
                for name in names
                if (file, name) not in groups
            ]
        elif (file, "") not in groups:
            problems.append(Problem("unrecorded", file, "file has no column mapping"))
    return problems

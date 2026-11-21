"""Row provenance: where every exported row landed and which truth entities it stands for.

Written to ``truth/provenance.csv`` (one record per exported data row) and
``truth/source_id_map.csv`` (truth id to the source's own id). Both are internal: nothing here
ever appears in an export. ``verify_provenance`` re-reads the exported files and checks every
locator against the identifying values on the row, which catches off-by-one errors from preamble,
trailer, and spacer rows.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook

from onboardkit.datagen.answer_keys.writer import read_table, write_table
from onboardkit.datagen.manifest import Problem
from onboardkit.datagen.pipeline import AnswerKeyContext
from onboardkit.datagen.sources.base import ColumnSpec, SourceRow, TableSpec
from onboardkit.datagen.sources.writers import format_cell, to_text

PROVENANCE_FILE = "provenance.csv"
SOURCE_ID_MAP_FILE = "source_id_map.csv"
PROVENANCE_HEADER = (
    "row_uid",
    "source",
    "table",
    "file",
    "sheet",
    "row_number",
    "person_ids",
    "household_id",
    "account_id",
    "source_keys",
    "origin",
)
SOURCE_ID_HEADER = ("source", "entity_type", "truth_id", "source_id")
# Concepts whose cells identify a row, and the kind of entity each one refers to.
KEY_ENTITIES = {
    "person.source_id": "person",
    "household.source_id": "household",
    "account.number": "account",
}
ORIGINS = ("projected", "duplicate", "split", "stale_extra")


def key_columns(table: TableSpec) -> list[ColumnSpec]:
    """The columns of ``table`` whose cells identify a row."""
    return [c for c in table.columns if c.concept in KEY_ENTITIES]


def _origins(context: AnswerKeyContext) -> dict[str, str]:
    """Row uid to origin, for every row that is not simply projected."""
    origins: dict[str, str] = {}
    for event in context.mess_events:
        if event.mess_type == "households" and event.subtype in ("duplicate", "split"):
            for uid in event.row_uids:
                origins[uid] = event.subtype
    for coverage in context.coverage_events:
        if coverage.kind == "stale_extra" and coverage.row_uid:
            origins[coverage.row_uid] = "stale_extra"
    return origins


def _source_keys(table: TableSpec, row: SourceRow) -> list[tuple[ColumnSpec, str]]:
    keys = []
    for column in key_columns(table):
        text = to_text(format_cell(column, row))
        if text:
            keys.append((column, text))
    return keys


def build_provenance(context: AnswerKeyContext) -> tuple[list[list[str]], list[list[str]]]:
    """Provenance records and source-id map rows, as lists of cells (unsorted)."""
    origins = _origins(context)
    records: list[list[str]] = []
    mappings: set[tuple[str, str, str, str]] = set()
    for source, rows in context.rows.items():
        profile = context.profiles[source]
        for row in rows:
            locator = context.locators[source][row.row_uid]
            keys = _source_keys(profile.table(row.table), row)
            origin = origins.get(row.row_uid, "projected")
            refs = row.refs
            account_id = "" if origin == "stale_extra" else (refs.account_id or "")
            records.append(
                [
                    row.row_uid,
                    source,
                    row.table,
                    f"{source}/{locator.file}",
                    locator.sheet or "",
                    str(locator.row_number),
                    "|".join(refs.person_ids),
                    refs.household_id or "",
                    account_id,
                    "|".join(f"{column.header}={value}" for column, value in keys),
                    origin,
                ]
            )
            truth_ids = {
                "person": refs.person_ids[0] if len(refs.person_ids) == 1 else "",
                "household": refs.household_id or "",
                "account": account_id,
            }
            for column, value in keys:
                entity = KEY_ENTITIES[column.concept]
                if truth_ids[entity]:
                    mappings.add((source, entity, truth_ids[entity], value))
    return records, [list(m) for m in mappings]


def write_provenance(context: AnswerKeyContext) -> None:
    """Answer key writer: the provenance table and the source-id map under ``truth/``."""
    records, mappings = build_provenance(context)
    write_table(context.truth_dir / PROVENANCE_FILE, PROVENANCE_HEADER, records)
    write_table(context.truth_dir / SOURCE_ID_MAP_FILE, SOURCE_ID_HEADER, mappings)


def _csv_rows(path: Path) -> dict[int, list[str]]:
    rows: dict[int, list[str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        for cells in reader:
            rows[reader.line_num] = cells
    return rows


def _sheet_rows(path: Path, sheet: str) -> dict[int, list[str]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        rows: dict[int, list[str]] = {}
        for number, cells in enumerate(workbook[sheet].iter_rows(values_only=True), start=1):
            rows[number] = ["" if v is None else str(v) for v in cells]
        return rows
    finally:
        workbook.close()


def _parse_keys(text: str) -> list[tuple[str, str]]:
    pairs = []
    for part in text.split("|") if text else []:
        name, _, value = part.partition("=")
        pairs.append((name, value))
    return pairs


def verify_provenance(dataset_dir: Path) -> list[Problem]:
    """Re-read the exported files and check every provenance locator against the row's keys."""
    path = dataset_dir / "truth" / PROVENANCE_FILE
    if not path.is_file():
        return [Problem("missing", f"truth/{PROVENANCE_FILE}", "provenance file not found")]
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for record in read_table(path):
        groups[(record["file"], record["sheet"])].append(record)
    problems: list[Problem] = []
    for (file, sheet), records in sorted(groups.items()):
        target = dataset_dir / "exports" / file
        if not target.is_file():
            problems.append(Problem("missing", f"exports/{file}", "file named in provenance"))
            continue
        rows = _sheet_rows(target, sheet) if sheet else _csv_rows(target)
        problems += _check_group(file, sheet, records, rows)
    return problems


def _check_group(
    file: str, sheet: str, records: list[dict[str, str]], rows: dict[int, list[str]]
) -> list[Problem]:
    where = f"{file}[{sheet}]" if sheet else file
    names = {name for r in records for name, _ in _parse_keys(r["source_keys"])}
    header_number = next(
        (n for n, cells in sorted(rows.items()) if names and names <= set(cells)), None
    )
    if header_number is None:
        return [Problem("locator", where, f"no header row containing {sorted(names)}")]
    header = rows[header_number]
    problems: list[Problem] = []
    seen: dict[int, str] = {}
    for record in records:
        number = int(record["row_number"])
        uid = record["row_uid"]
        keys = _parse_keys(record["source_keys"])
        if number in seen:
            problems.append(
                Problem("locator", uid, f"{where} row {number} is also used by {seen[number]}")
            )
        seen[number] = uid
        cells = rows.get(number)
        if number <= header_number or cells is None:
            problems.append(Problem("locator", uid, f"{where} row {number} is not a data row"))
        elif not keys:
            problems.append(Problem("locator", uid, "record has no identifying key to verify"))
        else:
            for name, value in keys:
                column = header.index(name)
                found = cells[column] if column < len(cells) else ""
                if found != value:
                    detail = f"{where} row {number}: expected {name}={value!r}, found {found!r}"
                    problems.append(Problem("locator", uid, detail))
    key_indexes = [header.index(name) for name in sorted(names)]
    for number, cells in sorted(rows.items()):
        if number <= header_number or number in seen or len(cells) < len(header):
            continue
        if any(cells[i] for i in key_indexes):
            problems.append(Problem("unrecorded", where, f"row {number} has no provenance record"))
    return problems

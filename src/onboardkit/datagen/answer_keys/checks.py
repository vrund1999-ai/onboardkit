"""``check_truth``: the truth folder is complete, consistent, sorted, and kept out of the exports.

Everything is read back from the files of a finished dataset, so it also catches tampering.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from onboardkit.datagen.answer_keys.column_mappings import (
    COLUMN_MAPPINGS_FILE,
    verify_column_mappings,
)
from onboardkit.datagen.answer_keys.discrepancies import (
    BOOK,
    DISCREPANCIES_FILE,
    INHERENT,
    event_group,
)
from onboardkit.datagen.answer_keys.entity_matches import (
    ENTITY_GROUPS_FILE,
    ENTITY_MATCHES_FILE,
    UNSEEN_FILE,
)
from onboardkit.datagen.answer_keys.provenance import (
    PROVENANCE_FILE,
    SOURCE_ID_MAP_FILE,
    verify_provenance,
)
from onboardkit.datagen.answer_keys.summary import SUMMARY_FILE
from onboardkit.datagen.answer_keys.truth_files import (
    COVERAGE_EVENTS_FILE,
    FIRM_FILE,
    MESS_EVENTS_FILE,
    README_FILE,
)
from onboardkit.datagen.manifest import Problem

CSV_FILES = (
    PROVENANCE_FILE,
    SOURCE_ID_MAP_FILE,
    ENTITY_MATCHES_FILE,
    ENTITY_GROUPS_FILE,
    UNSEEN_FILE,
    COLUMN_MAPPINGS_FILE,
    DISCREPANCIES_FILE,
)
REQUIRED = (
    README_FILE,
    FIRM_FILE,
    SUMMARY_FILE,
    MESS_EVENTS_FILE,
    COVERAGE_EVENTS_FILE,
    *CSV_FILES,
)
TRUTH_ID = re.compile(r"(?<![A-Za-z0-9])(?:P-\d{5,}|HH-\d{4,}|ACCT-\d{6,}|HOLD-\d{6,}|SEC-\d{3,})")
ENTITY_TYPES = ("person", "household", "account")


def _problem(path: str, detail: str) -> Problem:
    return Problem("truth", f"truth/{path}", detail)


class Truth:
    """The parsed truth folder of one dataset."""

    def __init__(self, root: Path) -> None:
        self.dir = root / "truth"
        self.problems: list[Problem] = []
        self.tables: dict[str, list[dict[str, str]]] = {}
        self.raw: dict[str, list[list[str]]] = {}
        self.firm: dict[str, Any] = {}
        self.summary: dict[str, Any] = {}
        self.mess: list[dict[str, Any]] = []
        self.coverage: list[dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        for name in REQUIRED:
            if not (self.dir / name).is_file():
                self.problems.append(_problem(name, "required file is missing"))
        for name in CSV_FILES:
            self._load_csv(name)
        self.firm = self._load_json(FIRM_FILE)
        self.summary = self._load_json(SUMMARY_FILE)
        self.mess = self._load_lines(MESS_EVENTS_FILE)
        self.coverage = self._load_lines(COVERAGE_EVENTS_FILE)

    def _load_csv(self, name: str) -> None:
        path = self.dir / name
        if not path.is_file():
            return
        try:
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle))
            header, body = rows[0], rows[1:]
            if any(len(r) != len(header) for r in body):
                raise ValueError("rows differ in length from the header")
        except (OSError, ValueError, IndexError, UnicodeDecodeError) as exc:
            self.problems.append(_problem(name, f"cannot parse: {exc}"))
            return
        self.raw[name] = rows
        self.tables[name] = [dict(zip(header, r, strict=True)) for r in body]

    def _load_json(self, name: str) -> dict[str, Any]:
        path = self.dir / name
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self.problems.append(_problem(name, f"cannot parse: {exc}"))
            return {}
        if not isinstance(value, dict):
            self.problems.append(_problem(name, "expected a JSON object"))
            return {}
        return value

    def _load_lines(self, name: str) -> list[dict[str, Any]]:
        path = self.dir / name
        if not path.is_file():
            return []
        records = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                records.append(json.loads(line))
        except (OSError, ValueError) as exc:
            self.problems.append(_problem(name, f"cannot parse: {exc}"))
            return []
        return records

    def ids(self, entity_type: str) -> set[str]:
        key = {"person": "people", "household": "households", "account": "accounts"}[entity_type]
        field = f"{entity_type}_id"
        return {str(r[field]) for r in self.firm.get(key, [])}


def _check_sorted(truth: Truth) -> None:
    for name, rows in truth.raw.items():
        body = rows[1:]
        if name == COLUMN_MAPPINGS_FILE:
            ordered = sorted(body, key=lambda r: (r[0], r[1], r[2], int(r[3])))
        else:
            ordered = sorted(body)
        if body != ordered:
            truth.problems.append(_problem(name, "rows are not in the expected sorted order"))
    for name, records in ((MESS_EVENTS_FILE, truth.mess), (COVERAGE_EVENTS_FILE, truth.coverage)):
        ids = [str(r.get("event_id")) for r in records]
        if ids != sorted(ids) or len(set(ids)) != len(ids):
            truth.problems.append(_problem(name, "event ids are not unique and sorted"))


def _check_truth_ids(truth: Truth) -> None:
    known = {t: truth.ids(t) for t in ENTITY_TYPES}

    def need(name: str, entity_type: str, value: str, where: str) -> None:
        if value and value not in known[entity_type]:
            truth.problems.append(_problem(name, f"{where}: unknown {entity_type} id {value!r}"))

    for row in truth.tables.get(PROVENANCE_FILE, []):
        for person in filter(None, row["person_ids"].split("|")):
            need(PROVENANCE_FILE, "person", person, row["row_uid"])
        need(PROVENANCE_FILE, "household", row["household_id"], row["row_uid"])
        need(PROVENANCE_FILE, "account", row["account_id"], row["row_uid"])
    for name in (ENTITY_MATCHES_FILE, ENTITY_GROUPS_FILE, UNSEEN_FILE, SOURCE_ID_MAP_FILE):
        for row in truth.tables.get(name, []):
            need(name, row["entity_type"], row["truth_id"], row["truth_id"])
    for row in truth.tables.get(DISCREPANCIES_FILE, []):
        need(DISCREPANCIES_FILE, row["entity_type"], row["truth_id"], row["discrepancy_id"])
    uids = {r["row_uid"] for r in truth.tables.get(PROVENANCE_FILE, [])}
    for row in truth.tables.get(ENTITY_MATCHES_FILE, []):
        if row["row_uid"] not in uids:
            truth.problems.append(
                _problem(ENTITY_MATCHES_FILE, f"row_uid {row['row_uid']!r} is not in provenance")
            )


def _check_coverage_of_entities(truth: Truth) -> None:
    grouped: dict[str, set[str]] = defaultdict(set)
    for row in truth.tables.get(ENTITY_GROUPS_FILE, []):
        grouped[row["entity_type"]].add(row["truth_id"])
    unseen: dict[str, set[str]] = defaultdict(set)
    for row in truth.tables.get(UNSEEN_FILE, []):
        unseen[row["entity_type"]].add(row["truth_id"])
    for entity_type in ENTITY_TYPES:
        for truth_id in sorted(truth.ids(entity_type)):
            in_group, in_unseen = truth_id in grouped[entity_type], truth_id in unseen[entity_type]
            if in_group == in_unseen:
                state = "in a group and listed as not exported" if in_group else "in no group"
                truth.problems.append(_problem(ENTITY_GROUPS_FILE, f"{truth_id} is {state}"))


def _check_summary(truth: Truth) -> None:
    summary = truth.summary
    if not summary or not truth.firm:
        return
    expected = {
        "persons": len(truth.firm.get("people", [])),
        "households": len(truth.firm.get("households", [])),
        "accounts": len(truth.firm.get("accounts", [])),
    }
    if summary.get("truth") != expected:
        truth.problems.append(
            _problem(SUMMARY_FILE, f"truth counts differ from firm.json {expected}")
        )
    rows: dict[str, int] = defaultdict(int)
    for row in truth.tables.get(PROVENANCE_FILE, []):
        rows[row["source"]] += 1
    if summary.get("rows") != dict(rows):
        truth.problems.append(_problem(SUMMARY_FILE, "rows per source differ from provenance"))
    checks = {
        "discrepancies.total": (
            summary.get("discrepancies", {}).get("total"),
            len(truth.tables.get(DISCREPANCIES_FILE, [])),
        ),
        "mess_events.total": (summary.get("mess_events", {}).get("total"), len(truth.mess)),
        "coverage_events.total": (
            summary.get("coverage_events", {}).get("total"),
            len(truth.coverage),
        ),
    }
    for label, (recorded, actual) in checks.items():
        if recorded != actual:
            truth.problems.append(
                _problem(SUMMARY_FILE, f"{label} is {recorded}, files hold {actual}")
            )
    groups = sum(
        count
        for by_level in summary.get("entity_groups", {}).values()
        for count in by_level.values()
    )
    if groups != len(truth.tables.get(ENTITY_GROUPS_FILE, [])):
        truth.problems.append(
            _problem(SUMMARY_FILE, "entity group counts differ from entity_groups.csv")
        )


def _check_discrepancy_events(truth: Truth) -> None:
    rows = truth.tables.get(DISCREPANCIES_FILE, [])
    event_ids = {str(e["event_id"]) for e in truth.mess} | {
        str(e["event_id"]) for e in truth.coverage
    }
    cited: set[str] = set()
    for row in rows:
        for event_id in filter(None, row["origin_events"].split("|")):
            cited.add(event_id)
            if event_id != INHERENT and event_id not in event_ids:
                truth.problems.append(
                    _problem(
                        DISCREPANCIES_FILE,
                        f"{row['discrepancy_id']} cites unknown event {event_id}",
                    )
                )
    for event in truth.coverage:
        if event["event_id"] not in cited:
            truth.problems.append(
                _problem(DISCREPANCIES_FILE, f"coverage event {event['event_id']} is not listed")
            )
    in_book = {
        r["account_id"] for r in truth.tables.get(PROVENANCE_FILE, []) if r["source"] == BOOK
    }
    for event in truth.mess:
        account = event["refs"].get("account_id")
        group = event_group(event["subtype"], event["concept"])
        if event["effect"] != "value_conflict" or not account or not group:
            continue
        if event["subtype"] == "stale_value" and account not in in_book:
            continue
        if event["event_id"] not in cited:
            truth.problems.append(
                _problem(DISCREPANCIES_FILE, f"value conflict {event['event_id']} is not listed")
            )


def _export_texts(exports: Path) -> list[tuple[str, str]]:
    texts = []
    for path in sorted(p for p in exports.rglob("*") if p.is_file()):
        rel = path.relative_to(exports).as_posix()
        if path.suffix == ".xlsx":
            workbook = load_workbook(path, read_only=True, data_only=True)
            try:
                for sheet in workbook.worksheets:
                    for cells in sheet.iter_rows(values_only=True):
                        texts.append(
                            (
                                f"{rel}[{sheet.title}]",
                                " ".join(str(c) for c in cells if c is not None),
                            )
                        )
            finally:
                workbook.close()
        else:
            texts.append((rel, path.read_text(encoding="utf-8-sig", errors="replace")))
    return texts


def check_separation(dataset_dir: Path) -> list[Problem]:
    """No export contains a truth identifier, and no source id embeds one."""
    problems: list[Problem] = []
    exports = dataset_dir / "exports"
    if exports.is_dir():
        for where, text in _export_texts(exports):
            match = TRUTH_ID.search(text)
            if match:
                problems.append(
                    Problem("leak", f"exports/{where}", f"contains truth id {match.group()}")
                )
    path = dataset_dir / "truth" / SOURCE_ID_MAP_FILE
    if path.is_file():
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["truth_id"] and row["truth_id"] in row["source_id"]:
                    problems.append(
                        Problem("leak", f"{row['source']}", f"source id embeds {row['truth_id']}")
                    )
    return problems


def check_truth(dataset_dir: Path) -> list[Problem]:
    """All truth checks for one dataset directory; an empty list means it is sound."""
    truth = Truth(dataset_dir)
    notice = truth.dir / README_FILE
    if notice.is_file() and "INTERNAL" not in notice.read_text(encoding="utf-8"):
        truth.problems.append(_problem(README_FILE, "the internal-material notice is missing"))
    _check_sorted(truth)
    _check_truth_ids(truth)
    _check_coverage_of_entities(truth)
    _check_summary(truth)
    _check_discrepancy_events(truth)
    problems = list(truth.problems)
    if (truth.dir / COLUMN_MAPPINGS_FILE).is_file():
        problems += verify_column_mappings(dataset_dir)
    if (truth.dir / PROVENANCE_FILE).is_file():
        problems += verify_provenance(dataset_dir)
    problems += check_separation(dataset_dir)
    return problems

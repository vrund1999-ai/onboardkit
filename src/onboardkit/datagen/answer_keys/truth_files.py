"""The plain truth files: the notice, the complete truth firm, and the event logs.

Everything here is internal answer material. None of it may be read by the code that builds the
exports (enforced by an import-boundary test) and none of it may appear under ``exports/``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict
from typing import Any

from onboardkit.datagen.pipeline import AnswerKeyContext

README_FILE = "README.txt"
FIRM_FILE = "firm.json"
MESS_EVENTS_FILE = "mess_events.jsonl"
COVERAGE_EVENTS_FILE = "coverage_events.jsonl"

NOTICE = """INTERNAL ANSWER MATERIAL - DO NOT READ WHEN BUILDING THE PRODUCT PIPELINE

Everything in this folder is synthetic ground truth about the dataset next to it. It is how we
score the product, not part of what a firm would send us. A real firm delivers only the files
under exports/.

- Do not read this folder from any code that ingests, maps, matches, or reconciles the exports.
- Do not include this folder in any "firm delivery" listing, upload, or screenshot of a delivery.
- Do not copy anything from here into exports/. The checks (onboardkit-gen check) fail if a
  truth identifier (P-, HH-, ACCT-) appears in an export.

Files:
  summary.json          counts of everything below
  firm.json             the complete truth firm: people, households, accounts
  provenance.csv        where every exported row landed and which truth entities it stands for
  source_id_map.csv     truth id to the id each source uses
  entity_matches.csv    which rows refer to the same person, household or account
  entity_groups.csv     one line per entity group
  entities_not_exported.csv  truth entities that no export mentions
  column_mappings.csv   the meaning of every column of every exported file and sheet
  discrepancies.csv     every real disagreement between the sources
  mess_events.jsonl     every deliberate change the mess types made
  coverage_events.jsonl every row a source left out or kept by mistake
"""


def dump_json(value: Any) -> str:
    """Sorted keys, two-space indent, trailing newline."""
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def dump_lines(records: Iterable[dict[str, Any]]) -> str:
    return "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)


def write_readme(context: AnswerKeyContext) -> None:
    (context.truth_dir / README_FILE).write_text(NOTICE, encoding="utf-8", newline="\n")


def firm_record(context: AnswerKeyContext) -> dict[str, Any]:
    firm = context.firm
    # Securities and holdings are not part of the answer key yet (they are added with E9-S3).
    dumped = firm.model_dump(mode="json", exclude={"profile", "securities", "holdings"})
    return {"firm_name": firm.profile.firm.name, **dumped}


def write_firm(context: AnswerKeyContext) -> None:
    (context.truth_dir / FIRM_FILE).write_text(
        dump_json(firm_record(context)), encoding="utf-8", newline="\n"
    )


def write_events(context: AnswerKeyContext) -> None:
    mess = sorted((asdict(e) for e in context.mess_events), key=lambda r: r["event_id"])
    coverage: list[dict[str, Any]] = sorted(
        (
            {
                "event_id": e.event_id,
                "kind": e.kind,
                "source": e.source,
                "table": e.table,
                "row_uid": e.row_uid,
                "refs": asdict(e.refs),
            }
            for e in context.coverage_events
        ),
        key=lambda r: r["event_id"],
    )
    (context.truth_dir / MESS_EVENTS_FILE).write_text(
        dump_lines(mess), encoding="utf-8", newline="\n"
    )
    (context.truth_dir / COVERAGE_EVENTS_FILE).write_text(
        dump_lines(coverage), encoding="utf-8", newline="\n"
    )

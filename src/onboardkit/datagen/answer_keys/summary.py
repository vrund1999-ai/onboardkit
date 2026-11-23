"""``truth/summary.json``: how many of everything a dataset contains, taken from the keys."""

from __future__ import annotations

from collections import Counter
from typing import Any

from onboardkit.datagen.answer_keys.discrepancies import build_discrepancies, inherent_count
from onboardkit.datagen.answer_keys.entity_matches import (
    derive_groups,
    derive_memberships,
    unseen_entities,
)
from onboardkit.datagen.answer_keys.truth_files import dump_json
from onboardkit.datagen.pipeline import AnswerKeyContext

SUMMARY_FILE = "summary.json"


def nested(counter: Counter[tuple[str, ...]]) -> dict[str, Any]:
    """Counter keyed by tuples to nested dicts (sorted when dumped)."""
    result: dict[str, Any] = {}
    for key, count in counter.items():
        node = result
        for part in key[:-1]:
            node = node.setdefault(part, {})
        node[key[-1]] = count
    return result


def build_summary(context: AnswerKeyContext) -> dict[str, Any]:
    memberships = derive_memberships(context)
    groups = derive_groups(memberships)
    discrepancies = build_discrepancies(context)
    firm = context.firm
    return {
        "truth": {
            "persons": len(firm.people),
            "households": len(firm.households),
            "accounts": len(firm.accounts),
            "securities": len(firm.securities),
            "holdings": len(firm.holdings),
        },
        "rows": {source: len(rows) for source, rows in context.rows.items()},
        "entity_groups": nested(Counter((g[0], g[4]) for g in groups)),
        "entities_not_exported": nested(
            Counter((entity_type,) for entity_type, _ in unseen_entities(context, memberships))
        ),
        "discrepancies": {
            "total": len(discrepancies),
            "by_kind": nested(Counter((d.kind,) for d in discrepancies)),
            "by_kind_and_severity": nested(Counter((d.kind, d.severity) for d in discrepancies)),
            "inherent": inherent_count(context),
        },
        "mess_events": {
            "total": len(context.mess_events),
            "by_type": nested(Counter((e.mess_type,) for e in context.mess_events)),
            "by_subtype": nested(Counter((e.mess_type, e.subtype) for e in context.mess_events)),
        },
        "coverage_events": {
            "total": len(context.coverage_events),
            "by_kind": nested(Counter((e.kind,) for e in context.coverage_events)),
        },
    }


def write_summary(context: AnswerKeyContext) -> None:
    (context.truth_dir / SUMMARY_FILE).write_text(
        dump_json(build_summary(context)), encoding="utf-8", newline="\n"
    )

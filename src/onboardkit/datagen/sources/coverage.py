"""Source coverage and overlap: which truth entities each source leaves out or keeps by mistake.

Runs after projection and before mess. Every omission and every stale extra is logged as exactly
one ``CoverageEvent`` so the discrepancy answer key knows about it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from typing import Literal

from onboardkit.datagen.config import CoverageConfig
from onboardkit.datagen.rng import derive_rng
from onboardkit.datagen.sources.base import SourceRow, TruthRefs
from onboardkit.datagen.truth.model import TruthFirm

BOOK = "book_of_business"
STALE_TABLE = "archive"
SOURCE_ORDER = ("custodian", "crm", BOOK)  # restoration prefers the lowest-numbered source


@dataclass(frozen=True)
class CoverageEvent:
    kind: Literal["omitted", "stale_extra"]
    source: str
    table: str
    row_uid: str | None  # None when the row was dropped before it existed
    refs: TruthRefs


def _table_rates(config: CoverageConfig) -> dict[tuple[str, str], float]:
    return {
        ("custodian", "accounts"): config.custodian.accounts,
        ("crm", "contacts"): config.crm.persons,
        ("crm", "linked_accounts"): config.crm.account_links,
        (BOOK, "accounts"): config.book_of_business.accounts,
        (BOOK, "archive"): config.book_of_business.accounts,
    }


def _choose_omitted(items: list[str], rate: float, rng: random.Random) -> set[str]:
    """Shuffle sorted ids with the stream and cut at ``1 - rate``."""
    ordered = sorted(items)
    rng.shuffle(ordered)
    return set(ordered[: round(len(ordered) * (1.0 - rate))])


def _source_rank(source: str) -> int:
    return SOURCE_ORDER.index(source) if source in SOURCE_ORDER else len(SOURCE_ORDER)


def apply_coverage(
    rows_by_source: dict[str, list[SourceRow]],
    firm: TruthFirm,
    config: CoverageConfig,
    root_seed: int,
) -> tuple[dict[str, list[SourceRow]], list[CoverageEvent]]:
    """Drop rows, restore what the guarantee rule needs, and add stale extras."""
    omitted: dict[str, SourceRow] = {}  # row_uid -> row, in omission order

    # 1. Per source and table, an independent seeded selection of rows to omit.
    rates = _table_rates(config)
    for source in SOURCE_ORDER:
        for table in sorted({r.table for r in rows_by_source.get(source, [])}):
            rate = rates.get((source, table), 1.0)
            table_rows = {r.row_uid: r for r in rows_by_source[source] if r.table == table}
            if source == BOOK:
                table_rows = _after_household_omission(
                    rows_by_source[source], config, root_seed, omitted, table
                )
            rng = derive_rng(root_seed, "coverage", source, table)
            for uid in _choose_omitted(list(table_rows), rate, rng):
                omitted[uid] = table_rows[uid]

    # 2. Guarantee rule.
    _restore_for_guarantee(rows_by_source, omitted, firm)

    kept = {
        source: [r for r in rows if r.row_uid not in omitted]
        for source, rows in rows_by_source.items()
    }
    events = [
        CoverageEvent("omitted", row.source, row.table, row.row_uid, row.refs)
        for row in omitted.values()
    ]

    # 3. Stale extras in the spreadsheet.
    extras = _stale_extras(kept.get(BOOK, []), firm, config, root_seed)
    if extras:
        kept[BOOK] = [*kept[BOOK], *extras]
        events.extend(
            CoverageEvent("stale_extra", row.source, row.table, row.row_uid, row.refs)
            for row in extras
        )
    return kept, events


def _after_household_omission(
    rows: list[SourceRow],
    config: CoverageConfig,
    root_seed: int,
    omitted: dict[str, SourceRow],
    table: str,
) -> dict[str, SourceRow]:
    """Omit whole households from the spreadsheet (once), then return the rest of ``table``."""
    household_rate = config.book_of_business.households
    household_ids = sorted({str(r.refs.household_id) for r in rows})
    rng = derive_rng(root_seed, "coverage", BOOK, "households")
    gone = _choose_omitted(household_ids, household_rate, rng)
    for row in rows:
        if str(row.refs.household_id) in gone:
            omitted[row.row_uid] = row
    return {r.row_uid: r for r in rows if r.table == table and r.row_uid not in omitted}


def _restore_for_guarantee(
    rows_by_source: dict[str, list[SourceRow]], omitted: dict[str, SourceRow], firm: TruthFirm
) -> None:
    """Make sure every truth account and household stays in at least one source."""

    def remaining(rows: list[SourceRow]) -> list[SourceRow]:
        return [r for r in rows if r.row_uid not in omitted]

    for attribute, wanted in (
        ("account_id", [a.account_id for a in firm.accounts]),
        ("household_id", [h.household_id for h in firm.households]),
    ):
        present = {
            getattr(r.refs, attribute)
            for source in rows_by_source.values()
            for r in remaining(source)
        }
        for truth_id in wanted:
            if truth_id in present:
                continue
            candidates = sorted(
                (r for r in omitted.values() if getattr(r.refs, attribute) == truth_id),
                key=lambda r: (_source_rank(r.source), r.row_uid),
            )
            if candidates:
                del omitted[candidates[0].row_uid]
                present.add(truth_id)


def _stale_extras(
    book_rows: list[SourceRow], firm: TruthFirm, config: CoverageConfig, root_seed: int
) -> list[SourceRow]:
    rate = config.book_of_business.stale_extra_rate
    count = round(len(book_rows) * rate)
    if count == 0 or not book_rows:
        return []
    rng = derive_rng(root_seed, "coverage", BOOK, "stale_extra")
    truth_numbers = {a.account_number for a in firm.accounts}
    used: set[str] = set()
    prefix = firm.profile.account_number.prefix
    digits = firm.profile.account_number.digits
    ordered = sorted(book_rows, key=lambda r: r.row_uid)
    extras: list[SourceRow] = []
    for index in range(1, count + 1):
        template = rng.choice(ordered)
        while True:
            number = f"{prefix}{rng.randrange(10 ** (digits - 1), 10**digits)}"
            if number not in truth_numbers and number not in used:
                break
        used.add(number)
        extras.append(
            SourceRow(
                row_uid=f"{BOOK}:{STALE_TABLE}:stale-{index:06d}",
                source=BOOK,
                table=STALE_TABLE,
                values={**template.values, "account.number": number},
                refs=replace(template.refs, account_id=None),
            )
        )
    return extras

"""The ``balances`` mess type: deliberate, labelled disagreements between sources.

The custodian is authoritative for money. Only the book of business and the CRM's linked-account
table are made to disagree with it, with two documented exceptions in the custodian itself:
``stale_value`` rewinds the custodian balance to the previous quarter end (the custodian is the
only source with an as-of date).

| subtype               | where     | what changes                          | severity |
|-----------------------|-----------|----------------------------------------|----------|
| rounding_diff         | book      | balance off by $0.01 to $1.00          | immaterial |
| small_drift           | book      | balance off by up to 0.5 percent       | immaterial |
| transposed_digits     | book      | two adjacent digits swapped            | material |
| magnitude_error       | book      | an extra or missing zero (< $200,000)  | material |
| stale_value           | custodian | previous quarter-end value and as-of   | by size  |
| status_mismatch       | book      | note says closed (or active)           | material |
| type_mismatch         | book, CRM | a different account type               | material |
| registration_mismatch | book      | note names one owner of a joint account | material |

The book of business has no status or registration column, so those two mismatches are written as
a note in its free-text ``meta.notes`` column, the way a hand-kept spreadsheet would record them
(this is why ``meta.notes`` is among the touched concepts). Rows that already have a note are
left alone.

Each account gets at most one event per source. Events have ``effect = "value_conflict"``;
``before`` is the authoritative value and ``after`` the disagreeing one. Value events record the
tolerance (``detail``) and whether the difference falls inside it.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from onboardkit.datagen.mess.base import MessContext, MessEvent, Severity, SourceDataset
from onboardkit.datagen.mess.registry import register
from onboardkit.datagen.sources.base import RawText, SourceRow
from onboardkit.datagen.sources.formatters import NameParts
from onboardkit.datagen.truth.profile import AccountStatus, AccountType

BOOK = "book_of_business"
CUSTODIAN = "custodian"
CRM = "crm"
LINKED = "linked_accounts"
ACCOUNTS = "accounts"

BALANCE = "account.balance"
AS_OF = "account.balance_as_of"
STATUS = "account.status"
TYPE = "account.type"
REGISTRATION = "account.registration"
NOTES = "meta.notes"

CENT = Decimal("0.01")
TOLERANCE_ABS = Decimal("1.00")  # dollars
TOLERANCE_REL = Decimal("0.001")  # 0.1 percent
STALE_MATERIAL_SHARE = Decimal("0.02")
MAGNITUDE_LIMIT = Decimal("200000")
DETAIL_TOLERANCE = f"tolerance=max({TOLERANCE_ABS}, {TOLERANCE_REL * 100:.1f}%)"

# Relative weights for the book of business. Only the rows a subtype applies to compete for it;
# about 40 percent of the events end up immaterial.
BOOK_WEIGHTS = {
    "rounding_diff": 0.20,
    "small_drift": 0.18,
    "transposed_digits": 0.12,
    "magnitude_error": 0.10,
    "type_mismatch": 0.14,
    "status_mismatch": 0.14,
    "registration_mismatch": 0.40,  # only joint accounts qualify, so give them a real chance
}
STALE_SHARE = 0.12  # of custodian accounts, at the mess rate
CRM_TYPE_SHARE = 0.15  # of accounts' first CRM link, at the mess rate
IMMATERIAL = {"rounding_diff", "small_drift"}

TYPE_SWAP = {
    AccountType.ROTH_IRA: AccountType.TRADITIONAL_IRA,
    AccountType.TRADITIONAL_IRA: AccountType.ROTH_IRA,
    AccountType.ROLLOVER_IRA: AccountType.TRADITIONAL_IRA,
    AccountType.INDIVIDUAL: AccountType.JOINT,
    AccountType.JOINT: AccountType.INDIVIDUAL,
    AccountType.EDUCATION_529: AccountType.INDIVIDUAL,
}


def tolerance(authoritative: Decimal) -> Decimal:
    """The larger of $1.00 and 0.1 percent of the authoritative value."""
    return max(TOLERANCE_ABS, (abs(authoritative) * TOLERANCE_REL).quantize(CENT))


def within_tolerance(authoritative: Decimal, other: Decimal) -> bool:
    return abs(authoritative - other) <= tolerance(authoritative)


def previous_quarter_end(day: date) -> date:
    quarter_start = date(day.year, 3 * ((day.month - 1) // 3) + 1, 1)
    return quarter_start - timedelta(days=1)


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _is_money(value: Any) -> bool:
    return isinstance(value, Decimal) and value > 0


def _value_detail(authoritative: Decimal, other: Decimal) -> str:
    return f"{DETAIL_TOLERANCE}; within_tolerance={within_tolerance(authoritative, other)}"


def _rounding_diff(base: Decimal, rng: random.Random) -> Decimal | None:
    cents = rng.randrange(1, 101) * rng.choice([-1, 1])
    value = base + Decimal(cents) * CENT
    return value if value > 0 else base + abs(Decimal(cents)) * CENT


def _small_drift(base: Decimal, rng: random.Random) -> Decimal | None:
    share = Decimal(str(rng.uniform(0.0002, 0.005))) * rng.choice([-1, 1])
    value = _cents(base * (1 + share))
    return value if value > 0 and value != base else None


def _transposed(base: Decimal, rng: random.Random) -> Decimal | None:
    text = f"{base:f}"
    spots = [i for i in range(len(text) - 1) if text[i].isdigit() and text[i + 1].isdigit()]
    rng.shuffle(spots)
    for i in spots:
        if text[i] == text[i + 1]:
            continue
        swapped = text[:i] + text[i + 1] + text[i] + text[i + 2 :]
        if swapped[0] == "0":
            continue
        value = Decimal(swapped)
        if value > 0 and abs(value - base) > tolerance(base):
            return value
    return None


def _magnitude(base: Decimal, rng: random.Random) -> Decimal | None:
    if base >= MAGNITUDE_LIMIT:
        return None
    if base >= 100 and rng.random() < 0.4:
        return _cents(base / 10)
    return _cents(base * 10)


VALUE_MAKERS = {
    "rounding_diff": _rounding_diff,
    "small_drift": _small_drift,
    "transposed_digits": _transposed,
    "magnitude_error": _magnitude,
}


@register
class BalancesMess:
    name = "balances"
    description = "Balances, statuses, types and owners that disagree between sources."
    touches = frozenset({BALANCE, AS_OF, STATUS, TYPE, REGISTRATION, NOTES})
    structural = False
    max_rate = 0.25
    subtypes = frozenset({*BOOK_WEIGHTS, "stale_value"})

    def apply(self, ctx: MessContext, data: SourceDataset) -> list[MessEvent]:
        if ctx.rate <= 0:
            return []
        authority = {
            row.refs.account_id: row
            for row in data.get(CUSTODIAN, {}).get(ACCOUNTS, [])
            if row.refs.account_id and _is_money(row.values.get(BALANCE))
        }
        # Authoritative values are read before anything changes, including the custodian's own.
        facts = {
            account_id: (
                row.values[BALANCE],
                row.values.get(STATUS),
                row.values.get(TYPE),
                row.values.get(REGISTRATION),
                row.values.get(AS_OF),
                row.values.get("account.owner_names") or [],
            )
            for account_id, row in authority.items()
        }
        events: list[MessEvent] = []
        events += self._book(ctx, data, facts)
        events += self._crm_types(ctx, data, facts)
        events += self._custodian_stale(ctx, authority)
        return events

    @staticmethod
    def _first_rows(
        rows_by_table: dict[str, list[SourceRow]], tables: tuple[str, ...], known: set[str]
    ) -> dict[str, SourceRow]:
        first: dict[str, SourceRow] = {}
        for table in tables:
            for row in sorted(rows_by_table.get(table, []), key=lambda r: r.row_uid):
                account_id = row.refs.account_id
                if account_id in known and account_id not in first:
                    first[account_id] = row
        return first

    def _book(
        self, ctx: MessContext, data: SourceDataset, facts: dict[str, tuple[Any, ...]]
    ) -> list[MessEvent]:
        rng = ctx.rng(BOOK)
        tables = data.get(BOOK, {})
        events: list[MessEvent] = []
        rows = self._first_rows(tables, (ACCOUNTS, "archive"), set(facts))
        for account_id in sorted(rows):
            if rng.random() >= ctx.rate:
                continue
            row = rows[account_id]
            options = {
                name: weight
                for name, weight in BOOK_WEIGHTS.items()
                if self._applies(name, row, facts[account_id])
            }
            if not options:
                continue
            names = sorted(options)
            subtype = rng.choices(names, weights=[options[n] for n in names])[0]
            event = self._make_book_event(ctx, rng, subtype, row, facts[account_id])
            if event is not None:
                events.append(event)
        return events

    @staticmethod
    def _applies(subtype: str, row: SourceRow, fact: tuple[Any, ...]) -> bool:
        _, status, account_type, _, _, owners = fact
        current = row.values.get(BALANCE)
        if subtype in VALUE_MAKERS:
            return _is_money(current) and not isinstance(current, RawText)
        if subtype == "type_mismatch":
            return bool(account_type in TYPE_SWAP and row.values.get(TYPE) == account_type)
        free_note = not row.values.get(NOTES)
        if subtype == "status_mismatch":
            if not free_note:
                return False
            if row.table == ACCOUNTS:
                return bool(status == AccountStatus.OPEN)
            return bool(status == AccountStatus.CLOSED)
        if subtype == "registration_mismatch":
            return bool(free_note and account_type == AccountType.JOINT and len(owners) >= 2)
        return False

    def _make_book_event(
        self,
        ctx: MessContext,
        rng: random.Random,
        subtype: str,
        row: SourceRow,
        fact: tuple[Any, ...],
    ) -> MessEvent | None:
        balance, status, account_type, registration, _, owners = fact
        severity: Severity = "immaterial" if subtype in IMMATERIAL else "material"
        common: dict[str, Any] = {
            "source": BOOK,
            "table": row.table,
            "row_uids": (row.row_uid,),
            "effect": "value_conflict",
            "refs": row.refs,
            "severity": severity,
            "subtype": subtype,
        }
        if subtype in VALUE_MAKERS:
            new = VALUE_MAKERS[subtype](balance, rng)
            if new is None or new == balance:
                return None
            row.values[BALANCE] = new
            return ctx.event(
                **common,
                concept=BALANCE,
                before=f"{balance:f}",
                after=f"{new:f}",
                detail=_value_detail(balance, new),
            )
        if subtype == "type_mismatch":
            new_type = TYPE_SWAP[account_type]
            row.values[TYPE] = new_type
            return ctx.event(
                **common, concept=TYPE, before=account_type.value, after=new_type.value
            )
        if subtype == "status_mismatch":
            reported = "closed" if row.table == ACCOUNTS else "active"
            row.values[NOTES] = "Closed per client" if reported == "closed" else "Active, reopened"
            return ctx.event(
                **common,
                concept=None,
                before=str(status),
                after="closed" if reported == "closed" else "open",
                detail=f"book note: {row.values[NOTES]!r}",
            )
        owner = owners[0]
        name = f"{owner.first} {owner.last}" if isinstance(owner, NameParts) else str(owner)
        row.values[NOTES] = f"Sole owner: {name}"
        return ctx.event(**common, concept=None, before=str(registration), after=row.values[NOTES])

    def _crm_types(
        self, ctx: MessContext, data: SourceDataset, facts: dict[str, tuple[Any, ...]]
    ) -> list[MessEvent]:
        rng = ctx.rng(CRM)
        rows = self._first_rows(data.get(CRM, {}), (LINKED,), set(facts))
        events: list[MessEvent] = []
        for account_id in sorted(rows):
            if rng.random() >= ctx.rate * CRM_TYPE_SHARE:
                continue
            row = rows[account_id]
            account_type = facts[account_id][2]
            if account_type not in TYPE_SWAP or row.values.get(TYPE) != account_type:
                continue
            new_type = TYPE_SWAP[account_type]
            row.values[TYPE] = new_type
            events.append(
                ctx.event(
                    subtype="type_mismatch",
                    source=CRM,
                    table=LINKED,
                    row_uids=(row.row_uid,),
                    effect="value_conflict",
                    refs=row.refs,
                    concept=TYPE,
                    before=account_type.value,
                    after=new_type.value,
                    severity="material",
                )
            )
        return events

    def _custodian_stale(
        self, ctx: MessContext, authority: dict[str, SourceRow]
    ) -> list[MessEvent]:
        rng = ctx.rng(CUSTODIAN)
        events: list[MessEvent] = []
        for account_id in sorted(authority):
            if rng.random() >= ctx.rate * STALE_SHARE:
                continue
            row = authority[account_id]
            balance: Decimal = row.values[BALANCE]
            as_of = row.values.get(AS_OF)
            if not isinstance(as_of, date):
                continue
            move = Decimal(str(rng.uniform(0.005, 0.12))) * rng.choice([-1, 1])
            prior = _cents(balance * (1 + move))
            if prior <= 0 or prior == balance:
                continue
            prior_as_of = previous_quarter_end(as_of)
            share = abs(prior - balance) / balance
            row.values[BALANCE] = prior
            row.values[AS_OF] = prior_as_of
            events.append(
                ctx.event(
                    subtype="stale_value",
                    source=CUSTODIAN,
                    table=ACCOUNTS,
                    row_uids=(row.row_uid,),
                    effect="value_conflict",
                    refs=row.refs,
                    concept=None,
                    before=f"{balance:f}",
                    after=f"{prior:f}",
                    severity="material" if share > STALE_MATERIAL_SHARE else "immaterial",
                    detail=f"{_value_detail(balance, prior)}; prior_as_of={prior_as_of}",
                )
            )
        return events

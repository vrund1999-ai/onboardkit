"""The ``formats`` mess type: the same value written in a different textual form.

Hand-edited exports drift from their default format: a few dates in another style, account numbers
with stray separators, phone numbers in a second style, states spelled out, balances typed as text.
The value does not change, only how it is written, so events have ``effect = "format_variant"``.
A changed value becomes a ``RawText`` that writers emit verbatim; ``RawText.original`` keeps the
typed value for the answer key.

Rules:

- The rate applies per eligible value, capped at 0.5 per column; a column also never ends with more
  deviating values than default ones (``(n - 1) // 2`` at most), so the default format stays the
  majority.
- ``date_day_month_swap`` is only used when the day is 12 or lower and differs from the month,
  and is always labelled ``high``.
- A new account number never equals another account number in the same source.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from onboardkit.datagen.mess.base import MessContext, MessEvent, SourceDataset
from onboardkit.datagen.mess.registry import register
from onboardkit.datagen.sources.base import RawText, SourceRow

DATES = ("person.date_of_birth", "person.client_since", "account.open_date", "meta.review_date")
ACCOUNT = "account.number"
PHONE = "person.phone"
STATE = "person.address_state"
BALANCE = "account.balance"
MAX_COLUMN_SHARE = 0.5

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}  # fmt: skip

# The default date style of the columns that have one. Spreadsheet dates are real date cells.
DEFAULT_DATE_STYLE = {
    ("custodian", "account.open_date"): "us_slash",
    ("crm", "person.date_of_birth"): "iso",
    ("crm", "person.client_since"): "iso",
}

DATE_STYLES: dict[str, Callable[[date], str]] = {
    "iso": lambda d: d.isoformat(),
    "us_slash": lambda d: f"{d.month:02d}/{d.day:02d}/{d.year}",
    "day_month_name": lambda d: f"{d.day} {MONTHS[d.month - 1][:3]} {d.year}",
    "long": lambda d: f"{MONTHS[d.month - 1]} {d.day}, {d.year}",
    "dotted": lambda d: f"{d.day:02d}.{d.month:02d}.{d.year}",
}

AMBIGUITY: dict[str, str | None] = {
    "date_alt_format": "low",
    "date_two_digit_year": "medium",
    "date_day_month_swap": "high",
    "acct_separators": "low",
    "acct_leading_zeros": "medium",
    "acct_prefix_case": "low",
    "phone_style": "low",
    "state_full_name": "low",
    "money_text": "medium",
}

# concept kind -> subtype -> weight (weights favor the low-ambiguity subtypes)
SUBTYPES: dict[str, dict[str, float]] = {
    "date": {"date_alt_format": 0.60, "date_two_digit_year": 0.25, "date_day_month_swap": 0.15},
    "account": {"acct_separators": 0.50, "acct_prefix_case": 0.30, "acct_leading_zeros": 0.20},
    "phone": {"phone_style": 1.0},
    "state": {"state_full_name": 1.0},
    "money": {"money_text": 1.0},
}


@dataclass(frozen=True)
class Variant:
    subtype: str
    text: str
    original: Any
    before: str


def _kind(concept: str, source: str, table: str) -> str | None:
    if concept in DATES:
        return "date"
    if concept == ACCOUNT:
        return "account"
    if concept == PHONE:
        return "phone"
    if concept == STATE:
        return "state"
    if concept == BALANCE and source == "book_of_business":
        return "money"
    return None


def _present(value: Any) -> bool:
    return value not in (None, "") and not isinstance(value, RawText)


def _date_variant(
    subtype: str, value: date, default_style: str | None, rng: random.Random
) -> str | None:
    if subtype == "date_two_digit_year":
        return f"{value.month:02d}/{value.day:02d}/{value.year % 100:02d}"
    if subtype == "date_day_month_swap":
        if value.day > 12 or value.day == value.month:
            return None
        return f"{value.day:02d}/{value.month:02d}/{value.year}"
    styles = sorted(s for s in DATE_STYLES if s != default_style)
    return DATE_STYLES[rng.choice(styles)](value)


def _account_variant(subtype: str, value: str, rng: random.Random) -> str | None:
    match = re.fullmatch(r"([A-Za-z]*)(\d+)", value)
    if subtype == "acct_separators":
        if not match or not match.group(1):
            return None
        prefix, digits = match.groups()
        choice = rng.choice(["-", " ", "mid"])
        if choice == "mid":
            half = len(digits) // 2
            return f"{prefix}{digits[:half]}-{digits[half:]}"
        return f"{prefix}{choice}{digits}"
    if subtype == "acct_prefix_case":
        if rng.random() < 0.5 and match and match.group(1):
            return value.lower()
        return f"{value} "
    if subtype == "acct_leading_zeros":
        if not match or not match.group(2).startswith("0") or len(match.group(2).lstrip("0")) == 0:
            return None
        return f"{match.group(1)}{match.group(2).lstrip('0')}"
    return None


def _phone_variant(value: str, rng: random.Random) -> str | None:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    a, b, c = digits[:3], digits[3:6], digits[6:]
    options = [f"{a}.{b}.{c}", f"+1 {a} {b} {c}", f"{a}-{b}-{c}", f"1-{a}-{b}-{c}"]
    options = [o for o in options if o != value]
    return rng.choice(options)


def _money_variant(value: Decimal, rng: random.Random) -> str | None:
    whole = value == value.to_integral_value()
    options = [f"${value:,.2f}", f"{value:,.2f} ", f"~{value:f}"]
    if whole:
        options.append(f"${value:,.0f}")
    if value >= 1000 and value % 100 == 0:
        thousands = (value / 1000).normalize()
        options.append(f"${thousands:f}k")
    return rng.choice(options)


def make_variant(
    subtype: str, value: Any, source: str, concept: str, rng: random.Random
) -> Variant | None:
    """The text a value would take under ``subtype``, or ``None`` when it does not apply."""
    if subtype.startswith("date") and isinstance(value, date):
        style = DEFAULT_DATE_STYLE.get((source, concept))
        text = _date_variant(subtype, value, style, rng)
        return Variant(subtype, text, value, value.isoformat()) if text else None
    if subtype.startswith("acct") and isinstance(value, str):
        text = _account_variant(subtype, value, rng)
        return Variant(subtype, text, value, value) if text else None
    if subtype == "phone_style" and isinstance(value, str):
        text = _phone_variant(value, rng)
        return Variant(subtype, text, value, value) if text else None
    if subtype == "state_full_name" and isinstance(value, str) and value in STATES:
        return Variant(subtype, STATES[value], value, value)
    if subtype == "money_text" and isinstance(value, Decimal):
        text = _money_variant(value, rng)
        return Variant(subtype, text, value, f"{value:f}") if text else None
    return None


@register
class FormatsMess:
    name = "formats"
    description = "Dates, account numbers, phones, states and balances in a different text form."
    touches = frozenset({*DATES, ACCOUNT, PHONE, STATE, BALANCE})
    structural = False
    max_rate = 0.40
    subtypes = frozenset(AMBIGUITY)

    def apply(self, ctx: MessContext, data: SourceDataset) -> list[MessEvent]:
        rate = min(ctx.rate, MAX_COLUMN_SHARE)
        if rate <= 0:
            return []
        events: list[MessEvent] = []
        for source in sorted(data):
            rng = ctx.rng(source)
            taken = self._account_texts(data[source])
            for table in sorted(data[source]):
                rows = data[source][table]
                for concept in sorted(self.touches):
                    kind = _kind(concept, source, table)
                    if kind is None:
                        continue
                    events += self._column(
                        ctx, rng, rate, source, table, rows, concept, kind, taken
                    )
        return events

    @staticmethod
    def _account_texts(tables: dict[str, list[SourceRow]]) -> set[str]:
        return {
            str(row.values[ACCOUNT])
            for rows in tables.values()
            for row in rows
            if _present(row.values.get(ACCOUNT))
        }

    def _column(
        self,
        ctx: MessContext,
        rng: random.Random,
        rate: float,
        source: str,
        table: str,
        rows: list[SourceRow],
        concept: str,
        kind: str,
        taken: set[str],
    ) -> list[MessEvent]:
        eligible = [r for r in rows if _present(r.values.get(concept))]
        cap = (len(eligible) - 1) // 2
        chosen: list[tuple[SourceRow, Variant]] = []
        for row in eligible:
            if len(chosen) >= cap:
                break
            if rng.random() >= rate:
                continue
            variant = self._pick(rng, kind, source, concept, row.values[concept], taken)
            if variant is not None:
                chosen.append((row, variant))
        events = []
        for row, variant in chosen:
            row.values[concept] = RawText(variant.text, variant.original)
            events.append(
                ctx.event(
                    subtype=variant.subtype,
                    source=source,
                    table=table,
                    row_uids=(row.row_uid,),
                    effect="format_variant",
                    refs=row.refs,
                    concept=concept,
                    before=variant.before,
                    after=variant.text,
                    ambiguity=AMBIGUITY[variant.subtype],  # type: ignore[arg-type]
                )
            )
        return events

    @staticmethod
    def _pick(
        rng: random.Random, kind: str, source: str, concept: str, value: Any, taken: set[str]
    ) -> Variant | None:
        options = dict(SUBTYPES[kind])
        while options:
            names = sorted(options)
            subtype = rng.choices(names, weights=[options[n] for n in names])[0]
            del options[subtype]
            variant = make_variant(subtype, value, source, concept, rng)
            if variant is None or variant.text == variant.before:
                continue
            if kind == "account":
                if variant.text in taken:
                    continue
                taken.add(variant.text)
            return variant
        return None

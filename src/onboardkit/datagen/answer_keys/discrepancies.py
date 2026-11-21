"""Discrepancy answer key: every real disagreement between the exported sources.

Two independent derivations must agree:

* state-based: compare what the sources finally hold (typed values, with ``RawText.original``
  undoing format variants) using the authority table. This list is what gets written;
* event-based: what the coverage and mess events say they introduced. Every event-based entry must
  appear in the state-based list (``check_consistency``).

State-based entries with no explaining event have ``origin_events = inherent`` (the book of
business's rounding and drift).

Compared account facts: balance, type, status and registration. People and households only
appear as ``missing_in_source``.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from onboardkit.datagen.answer_keys.writer import write_table
from onboardkit.datagen.mess.balances import within_tolerance
from onboardkit.datagen.mess.base import MessEvent
from onboardkit.datagen.pipeline import AnswerKeyContext
from onboardkit.datagen.sources.base import RawText, SourceRow
from onboardkit.datagen.truth.profile import AccountStatus

DISCREPANCIES_FILE = "discrepancies.csv"
HEADER = (
    "discrepancy_id",
    "kind",
    "entity_type",
    "truth_id",
    "concept",
    "sources",
    "authoritative_source",
    "authoritative_value",
    "other_values",
    "severity",
    "origin_events",
)
CUSTODIAN, CRM, BOOK = "custodian", "crm", "book_of_business"
INHERENT = "inherent"
BOOK_TABLES = ("accounts", "archive")

# Roadmap defaults: money data from the custodian, people data from the CRM, the rest from the book.
AUTHORITY_BY_CONCEPT = {
    "account.balance": CUSTODIAN,
    "account.status": CUSTODIAN,
    "account.registration": CUSTODIAN,
    "account.type": CUSTODIAN,
    "account.number": CUSTODIAN,
}
AUTHORITY_BY_ENTITY = {"account": CUSTODIAN, "person": CRM, "household": CRM}

# What each source is expected to hold (the code below implements exactly this table).
EXPECTED = {
    CUSTODIAN: "every account",
    CRM: "every person and household, and a link for each owner of each account",
    BOOK: "every account (closed on Archive) and every household that has an account",
}
GROUPS = {
    "account.balance": "balance",
    "account.type": "type",
    "account.status": "status",
    "account.registration": "registration",
}
CONCEPT_OF_GROUP = {v: k for k, v in GROUPS.items()}
SOLE_OWNER = re.compile(r"^Sole owner:")

Key = tuple[str, ...]


def authority(concept: str) -> str:
    """The default source of truth for a concept."""
    if concept in AUTHORITY_BY_CONCEPT:
        return AUTHORITY_BY_CONCEPT[concept]
    if concept.startswith(("person.", "household.")):
        return CRM
    return BOOK


@dataclass
class Discrepancy:
    kind: str
    entity_type: str
    truth_id: str
    concept: str
    sources: tuple[str, ...]
    authoritative_source: str
    authoritative_value: str
    other_values: tuple[str, ...]
    severity: str
    origin_events: tuple[str, ...]
    key: Key

    def sort_key(self) -> Key:
        return (
            self.kind,
            self.entity_type,
            self.truth_id,
            self.concept,
            "|".join(self.sources),
            "|".join(self.other_values),
        )


def _text(value: Any) -> str:
    if isinstance(value, RawText):
        value = value.original
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return str(getattr(value, "value", value))


def _book_status(row: SourceRow) -> str:
    note = str(row.values.get("meta.notes") or "")
    if note.startswith("Closed"):
        return "closed"
    if note.startswith("Active"):
        return "open"
    return "closed" if row.table == "archive" else "open"


def _facts(context: AnswerKeyContext) -> dict[str, dict[str, dict[str, set[str]]]]:
    """Account id to fact group to source to the distinct rendered values it holds."""
    facts: dict[str, dict[str, dict[str, set[str]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(set))
    )
    for row in context.rows.get(CUSTODIAN, []):
        if not row.refs.account_id:
            continue
        for concept, group in GROUPS.items():
            if row.values.get(concept) is not None:
                facts[row.refs.account_id][group][CUSTODIAN].add(_text(row.values[concept]))
    for row in context.rows.get(CRM, []):
        if (
            row.table == "linked_accounts"
            and row.refs.account_id
            and row.values.get("account.type")
        ):
            facts[row.refs.account_id]["type"][CRM].add(_text(row.values["account.type"]))
    for row in context.rows.get(BOOK, []):
        if row.table not in BOOK_TABLES or not row.refs.account_id:
            continue
        book = facts[row.refs.account_id]
        book["balance"][BOOK].add(_text(row.values.get("account.balance")))
        book["type"][BOOK].add(_text(row.values.get("account.type")))
        book["status"][BOOK].add(_book_status(row))
        note = str(row.values.get("meta.notes") or "")
        if SOLE_OWNER.match(note):
            book["registration"][BOOK].add(note)
    return facts


def _differs(group: str, authoritative: str, other: str) -> bool:
    if group == "status":
        return (authoritative == AccountStatus.CLOSED.value) != (other == "closed")
    return authoritative != other


def event_group(subtype: str, concept: str | None) -> str | None:
    """The fact group (balance, type, status, registration) a value-conflict event is about."""
    by_subtype = {
        "stale_value": "balance",
        "status_mismatch": "status",
        "registration_mismatch": "registration",
    }
    return by_subtype.get(subtype) or GROUPS.get(concept or "")


def _event_index(context: AnswerKeyContext) -> dict[Key, list[str]]:
    """Key of every discrepancy the events claim to have caused, with the event ids."""
    index: dict[Key, list[str]] = defaultdict(list)
    coverage = context.coverage_events
    omitted_people: set[str] = set()
    omitted_book_accounts: set[str] = set()
    for c in coverage:
        refs = c.refs
        if c.kind == "stale_extra":
            index[("stale_extra", str(c.row_uid))].append(c.event_id)
        elif c.source == CUSTODIAN and refs.account_id:
            index[_missing("account", refs.account_id, CUSTODIAN)].append(c.event_id)
        elif c.source == CRM and c.table == "contacts":
            for person_id in refs.person_ids:
                index[_missing("person", person_id, CRM)].append(c.event_id)
                omitted_people.add(person_id)
        elif c.source == CRM and refs.account_id:
            for person_id in refs.person_ids:
                index[_missing("account", refs.account_id, CRM, person_id)].append(c.event_id)
        elif c.source == BOOK and refs.account_id:
            index[_missing("account", refs.account_id, BOOK)].append(c.event_id)
            omitted_book_accounts.add(refs.account_id)
    for household in context.firm.households:
        members = set(household.member_ids)
        if members and members <= omitted_people:
            index[_missing("household", household.household_id, CRM)] = [
                c.event_id
                for c in coverage
                if c.source == CRM and c.table == "contacts" and set(c.refs.person_ids) <= members
            ]
        accounts = {
            a.account_id for a in context.firm.accounts if a.household_id == household.household_id
        }
        if accounts and accounts <= omitted_book_accounts:
            index[_missing("household", household.household_id, BOOK)] = [
                c.event_id for c in coverage if c.source == BOOK and c.refs.account_id in accounts
            ]
    for event in context.mess_events:
        group = event_group(event.subtype, event.concept)
        if event.effect == "value_conflict" and event.refs.account_id and group:
            index[("value", event.refs.account_id, group)].append(event.event_id)
    return index


def _missing(entity_type: str, truth_id: str, source: str, link_person: str = "") -> Key:
    return ("missing", entity_type, truth_id, source, link_person)


def _severity(group: str, authoritative: str, others: list[str], events: list[MessEvent]) -> str:
    if events:
        return "material" if any(e.severity == "material" for e in events) else "immaterial"
    if group == "balance":
        base = Decimal(authoritative)
        return (
            "immaterial" if all(within_tolerance(base, Decimal(o)) for o in others) else "material"
        )
    return "material"


def _missing_records(context: AnswerKeyContext, index: dict[Key, list[str]]) -> list[Discrepancy]:
    firm = context.firm
    crm = context.rows.get(CRM, [])
    custodian = {r.refs.account_id for r in context.rows.get(CUSTODIAN, [])}
    people = {pid for r in crm if r.table == "contacts" for pid in r.refs.person_ids}
    households = {r.refs.household_id for r in crm if r.table == "contacts"}
    links = {
        (r.refs.account_id, pid)
        for r in crm
        if r.table == "linked_accounts"
        for pid in r.refs.person_ids
    }
    book = [r for r in context.rows.get(BOOK, []) if r.table in BOOK_TABLES]
    book_accounts = {r.refs.account_id for r in book}
    book_households = {r.refs.household_id for r in book}

    wanted: list[tuple[str, str, str, str]] = []
    for account in firm.accounts:
        if account.account_id not in custodian:
            wanted.append(("account", account.account_id, CUSTODIAN, ""))
        if account.account_id not in book_accounts:
            wanted.append(("account", account.account_id, BOOK, ""))
        wanted += [
            ("account", account.account_id, CRM, owner)
            for owner in account.owner_ids
            if (account.account_id, owner) not in links
        ]
    wanted += [("person", p.person_id, CRM, "") for p in firm.people if p.person_id not in people]
    wanted += [
        ("household", h.household_id, CRM, "")
        for h in firm.households
        if h.household_id not in households
    ]
    with_accounts = {a.household_id for a in firm.accounts}
    wanted += [("household", h, BOOK, "") for h in sorted(with_accounts - book_households)]
    found = []
    for entity_type, truth_id, source, link_person in wanted:
        key = _missing(entity_type, truth_id, source, link_person)
        found.append(
            Discrepancy(
                kind="missing_in_source",
                entity_type=entity_type,
                truth_id=truth_id,
                concept="",
                sources=(source,),
                authoritative_source=AUTHORITY_BY_ENTITY[entity_type],
                authoritative_value="",
                other_values=(f"{source}=no link for {link_person}",) if link_person else (),
                severity="material",
                origin_events=tuple(sorted(index.get(key, []))),
                key=key,
            )
        )
    return found


def _stale_extras(context: AnswerKeyContext, index: dict[Key, list[str]]) -> list[Discrepancy]:
    numbers = {a.account_number for a in context.firm.accounts}
    found = []
    for row in context.rows.get(BOOK, []):
        number = _text(row.values.get("account.number"))
        if row.table in BOOK_TABLES and number not in numbers:
            key = ("stale_extra", row.row_uid)
            found.append(
                Discrepancy(
                    kind="stale_extra",
                    entity_type="account",
                    truth_id="",
                    concept="",
                    sources=(BOOK,),
                    authoritative_source=CUSTODIAN,
                    authoritative_value="",
                    other_values=(f"{BOOK}={number}",),
                    severity="material",
                    origin_events=tuple(sorted(index.get(key, []))),
                    key=key,
                )
            )
    return found


def _value_conflicts(context: AnswerKeyContext, index: dict[Key, list[str]]) -> list[Discrepancy]:
    mess = {e.event_id: e for e in context.mess_events}
    found = []
    for account_id, groups in _facts(context).items():
        for group, by_source in groups.items():
            base = by_source.get(CUSTODIAN)
            if not base or len(base) != 1:
                continue
            (authoritative_value,) = base
            others = {
                source: sorted(v for v in values if _differs(group, authoritative_value, v))
                for source, values in by_source.items()
                if source != CUSTODIAN
            }
            others = {source: values for source, values in others.items() if values}
            if not others:
                continue
            key = ("value", account_id, group)
            event_ids = sorted(index.get(key, []))
            flat = [v for source in sorted(others) for v in others[source]]
            found.append(
                Discrepancy(
                    kind="value_conflict",
                    entity_type="account",
                    truth_id=account_id,
                    concept=CONCEPT_OF_GROUP[group],
                    sources=tuple(sorted({CUSTODIAN, *others})),
                    authoritative_source=authority(CONCEPT_OF_GROUP[group]),
                    authoritative_value=authoritative_value,
                    other_values=tuple(f"{s}={v}" for s in sorted(others) for v in others[s]),
                    severity=_severity(
                        group, authoritative_value, flat, [mess[i] for i in event_ids if i in mess]
                    ),
                    origin_events=tuple(event_ids) if event_ids else (INHERENT,),
                    key=key,
                )
            )
    return found


def build_discrepancies(context: AnswerKeyContext) -> list[Discrepancy]:
    """The state-based list, sorted (ids are assigned when written)."""
    index = _event_index(context)
    found = [
        *_missing_records(context, index),
        *_stale_extras(context, index),
        *_value_conflicts(context, index),
    ]
    found.sort(key=Discrepancy.sort_key)
    return found


def check_consistency(context: AnswerKeyContext) -> list[str]:
    """Event-based discrepancies that the state-based list lacks (empty when they agree).

    A custodian balance that went stale is only visible against another source's balance, so a
    stale event on an account no other source holds is not a failure.
    """
    state = {d.key for d in build_discrepancies(context)}
    in_book = {r.refs.account_id for r in context.rows.get(BOOK, [])}
    problems = []
    for key, ids in sorted(_event_index(context).items()):
        if key in state:
            continue
        if key[0] == "value" and key[2] == "balance" and key[1] not in in_book:
            continue
        problems.append(f"{key}: events {ids} produced no discrepancy")
    return problems


def inherent_count(context: AnswerKeyContext) -> int:
    """How many discrepancies no event explains (the book of business's own drift)."""
    return sum(1 for d in build_discrepancies(context) if d.origin_events == (INHERENT,))


def write_discrepancies(context: AnswerKeyContext) -> None:
    """Answer key writer: ``discrepancies.csv`` under ``truth/``."""
    rows = build_discrepancies(context)
    write_table(
        context.truth_dir / DISCREPANCIES_FILE,
        HEADER,
        (
            [
                f"D-{number:06d}",
                d.kind,
                d.entity_type,
                d.truth_id,
                d.concept,
                "|".join(d.sources),
                d.authoritative_source,
                d.authoritative_value,
                "|".join(d.other_values),
                d.severity,
                "|".join(d.origin_events),
            ]
            for number, d in enumerate(rows, start=1)
        ),
    )

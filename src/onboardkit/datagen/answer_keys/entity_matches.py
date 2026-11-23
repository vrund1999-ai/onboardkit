"""Entity match answer key: which exported rows refer to the same person, household, or account.

Groups come straight from the truth references in provenance (E5-S1), so they are exact. Each row
also gets a difficulty label that describes how much *constructed* variation touches it. The label
is the generator's view of its own mess, not a model of how hard a matcher would find the row.

Difficulty rules, applied to the events that touch a row (``MessEvent.row_uids``):

* ``hard``: an event with ambiguity ``high`` on an identifying value, a household ``split`` or
  ``duplicate``, or a varied name on the row of a person who shares a first initial and surname
  with another member of the same household (an unvaried name stays easy, so a ``clean`` dataset
  is all easy);
* ``moderate``: an ``entity_variant`` event with ambiguity ``low`` or ``medium``, a format variant
  on an account number, or a household whose id was blanked (``missing``);
* ``easy``: none of the above.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import combinations

from onboardkit.datagen.answer_keys.provenance import PROVENANCE_HEADER, build_provenance
from onboardkit.datagen.answer_keys.writer import write_table
from onboardkit.datagen.mess.base import MessEvent
from onboardkit.datagen.pipeline import AnswerKeyContext

ENTITY_MATCHES_FILE = "entity_matches.csv"
ENTITY_GROUPS_FILE = "entity_groups.csv"
UNSEEN_FILE = "entities_not_exported.csv"
UNSEEN_HEADER = ("entity_type", "truth_id")
NAME_CONCEPTS = frozenset({"person.first_name", "person.last_name", "person.suffix"})
MATCH_HEADER = (
    "entity_type",
    "truth_id",
    "row_uid",
    "source",
    "file",
    "sheet",
    "row_number",
    "difficulty",
    "variant_events",
)
GROUP_HEADER = ("entity_type", "truth_id", "row_count", "sources", "max_difficulty")
ENTITY_TYPES = ("person", "household", "account", "holding", "security")
DIFFICULTIES = ("easy", "moderate", "hard")
RANK = {name: index for index, name in enumerate(DIFFICULTIES)}

# Concepts whose values identify an entity (a variation here can make rows harder to match).
IDENTIFYING = frozenset(
    {
        "person.first_name",
        "person.last_name",
        "person.suffix",
        "person.date_of_birth",
        "person.tax_id_last4",
        "person.email",
        "person.phone",
        "person.address_line1",
        "person.address_city",
        "person.address_state",
        "person.address_postal",
        "person.source_id",
        "household.name",
        "household.source_id",
        "account.number",
        "holding.account_number",
        "account.owner_names",
    }
)
ACCOUNT_NUMBERS = frozenset({"account.number", "holding.account_number"})
HOUSEHOLD_STRUCTURE = {"split": "hard", "duplicate": "hard", "missing": "moderate"}


@dataclass(frozen=True)
class Membership:
    """One exported row's membership in one entity group."""

    entity_type: str
    truth_id: str
    row_uid: str
    source: str
    file: str
    sheet: str
    row_number: int
    difficulty: str
    variant_events: tuple[str, ...]


def event_difficulty(event: MessEvent) -> str | None:
    """The difficulty this event adds to a row it touches, or None when it adds none."""
    if event.mess_type == "households":
        return HOUSEHOLD_STRUCTURE.get(event.subtype)
    if event.effect not in ("entity_variant", "format_variant"):
        return None
    if event.concept is not None and event.concept not in IDENTIFYING:
        return None
    if event.ambiguity == "high":
        return "hard"
    if event.effect == "entity_variant" and event.ambiguity in ("low", "medium"):
        return "moderate"
    if event.effect == "format_variant" and event.concept in ACCOUNT_NUMBERS:
        return "moderate"
    return None


def confusable_people(context: AnswerKeyContext) -> frozenset[str]:
    """People who share a first initial and surname with another member of their household."""
    seen: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for person in context.firm.people:
        key = (person.household_id, person.first_name[:1].lower(), person.last_name.lower())
        seen[key].append(person.person_id)
    return frozenset(pid for ids in seen.values() if len(ids) > 1 for pid in ids)


def _events_by_row(context: AnswerKeyContext) -> dict[str, list[tuple[str, str]]]:
    """Row uid to (event id, difficulty) for every event that adds difficulty."""
    by_row: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for event in context.mess_events:
        difficulty = event_difficulty(event)
        if difficulty is None:
            continue
        for uid in event.row_uids:
            by_row[uid].append((event.event_id, difficulty))
    return by_row


def _name_varied_rows(context: AnswerKeyContext) -> set[str]:
    return {
        uid
        for event in context.mess_events
        if event.effect == "entity_variant" and event.concept in NAME_CONCEPTS
        for uid in event.row_uids
    }


def derive_memberships(context: AnswerKeyContext) -> list[Membership]:
    """Every (entity, row) membership with its difficulty, sorted for stable output."""
    records, _ = build_provenance(context)
    index = {name: position for position, name in enumerate(PROVENANCE_HEADER)}
    by_row = _events_by_row(context)
    confusable = confusable_people(context)
    name_varied = _name_varied_rows(context)
    memberships: list[Membership] = []
    for cells in records:
        uid = cells[index["row_uid"]]
        people = [p for p in cells[index["person_ids"]].split("|") if p]
        references = {
            "household": [cells[index["household_id"]]],
            "account": [cells[index["account_id"]]],
            "holding": [cells[index["holding_id"]]],
            "security": [cells[index["security_id"]]],
        }
        row_events = sorted(by_row.get(uid, []))
        for entity_type in ENTITY_TYPES:
            ids = people if entity_type == "person" else references[entity_type]
            for truth_id in (i for i in ids if i):
                level = max((d for _, d in row_events), key=RANK.__getitem__, default="easy")
                at_risk = [truth_id] if entity_type == "person" else people
                if uid in name_varied and confusable.intersection(at_risk):
                    level = "hard"
                memberships.append(
                    Membership(
                        entity_type=entity_type,
                        truth_id=truth_id,
                        row_uid=uid,
                        source=cells[index["source"]],
                        file=cells[index["file"]],
                        sheet=cells[index["sheet"]],
                        row_number=int(cells[index["row_number"]]),
                        difficulty=level,
                        variant_events=tuple(e for e, _ in row_events),
                    )
                )
    memberships.sort(key=lambda m: (m.entity_type, m.truth_id, m.row_uid))
    return memberships


def unseen_entities(context: AnswerKeyContext, memberships: list[Membership]) -> list[list[str]]:
    """Truth entities that no exported row refers to (for example a dependent the CRM omitted)."""
    truth_ids = {
        "person": {p.person_id for p in context.firm.people},
        "household": {h.household_id for h in context.firm.households},
        "account": {a.account_id for a in context.firm.accounts},
        "holding": {h.holding_id for h in context.firm.holdings},
        "security": {s.security_id for s in context.firm.securities},
    }
    seen: dict[str, set[str]] = defaultdict(set)
    for m in memberships:
        seen[m.entity_type].add(m.truth_id)
    return [
        [entity_type, truth_id]
        for entity_type in ENTITY_TYPES
        for truth_id in sorted(truth_ids[entity_type] - seen[entity_type])
    ]


def derive_groups(memberships: list[Membership]) -> list[list[str]]:
    grouped: dict[tuple[str, str], list[Membership]] = defaultdict(list)
    for m in memberships:
        grouped[(m.entity_type, m.truth_id)].append(m)
    rows = []
    for (entity_type, truth_id), members in sorted(grouped.items()):
        hardest = max((m.difficulty for m in members), key=RANK.__getitem__)
        sources = "|".join(sorted({m.source for m in members}))
        rows.append([entity_type, truth_id, str(len(members)), sources, hardest])
    return rows


def expected_pairs(memberships: list[Membership], entity_type: str) -> Iterator[tuple[str, str]]:
    """Every unordered pair of distinct rows in one group of ``entity_type``, as sorted uids."""
    grouped: dict[str, set[str]] = defaultdict(set)
    for m in memberships:
        if m.entity_type == entity_type:
            grouped[m.truth_id].add(m.row_uid)
    for truth_id in sorted(grouped):
        yield from combinations(sorted(grouped[truth_id]), 2)


def write_entity_matches(context: AnswerKeyContext) -> None:
    """Answer key writer: the match, group, and not-exported files under ``truth/``."""
    memberships = derive_memberships(context)
    write_table(
        context.truth_dir / ENTITY_MATCHES_FILE,
        MATCH_HEADER,
        (
            [
                m.entity_type,
                m.truth_id,
                m.row_uid,
                m.source,
                m.file,
                m.sheet,
                str(m.row_number),
                m.difficulty,
                "|".join(m.variant_events),
            ]
            for m in memberships
        ),
    )
    write_table(context.truth_dir / ENTITY_GROUPS_FILE, GROUP_HEADER, derive_groups(memberships))
    write_table(
        context.truth_dir / UNSEEN_FILE, UNSEEN_HEADER, unseen_entities(context, memberships)
    )

"""The ``households`` mess type: households that are duplicated, split, or missing.

Only the CRM and the spreadsheet have a household concept, so only they are touched. This is a
structural type: it adds rows (``duplicate``) and runs before the value types. Each truth
household gets at most one event, and every event lists all the rows it added or changed.

| subtype   | weight | what happens |
|-----------|--------|--------------|
| duplicate | 0.35   | its CRM contacts are copied under new contact and household ids |
| split     | 0.40   | a spouse or dependent moves to a new CRM household as its primary |
| missing   | 0.25   | its CRM contacts lose their household fields, or the first row of its |
|           |        | block in the spreadsheet loses the household name |

Truth references never change, so the answer key can derive the correct merge groups. Contact ids
do not change when a contact moves, so linked-account rows stay valid. New ids copy the format of
the ids already in the CRM (a letter and a fixed number of digits) and avoid every existing id.
"""

from __future__ import annotations

import copy
import random
from collections import defaultdict
from typing import Any

from onboardkit.datagen.mess.base import MessContext, MessEvent, SourceDataset
from onboardkit.datagen.mess.registry import register
from onboardkit.datagen.sources.base import SourceRow, TruthRefs
from onboardkit.datagen.sources.book_of_business import ACCOUNTS as BOOK_ACCOUNTS
from onboardkit.datagen.sources.book_of_business import ARCHIVE as BOOK_ARCHIVE
from onboardkit.datagen.sources.book_of_business import SOURCE as BOOK
from onboardkit.datagen.sources.crm import CONTACTS
from onboardkit.datagen.sources.crm import SOURCE as CRM
from onboardkit.datagen.truth.model import HouseholdRole, TruthPerson

PERSON_ID = "person.source_id"
HOUSEHOLD_ID = "household.source_id"
HOUSEHOLD_NAME = "household.name"
ROLE = "person.household_role"
ADVISOR = "household.advisor"

WEIGHTS = {"duplicate": 0.35, "split": 0.40, "missing": 0.25}
DUPLICATE_SUFFIX = "-dup"


def _next_id(rng: random.Random, existing: set[str], sample: str, default: str) -> str:
    """A new id shaped like ``sample`` (a letter and N digits) that is not in ``existing``."""
    prefix, digits = (sample[0], len(sample) - 1) if sample else (default[0], len(default) - 1)
    while True:
        candidate = f"{prefix}{rng.randrange(10 ** (digits - 1), 10**digits):0{digits}d}"
        if candidate not in existing:
            existing.add(candidate)
            return candidate


def _display_names(adults: list[TruthPerson], rng: random.Random) -> str:
    """A mild variation of ``Smith Household``: ``Smith, John & Jane`` or ``The Smiths``."""
    last = adults[0].last_name
    listed = " & ".join(p.first_name for p in adults)
    return rng.choice([f"{last}, {listed}", f"The {last}s"])


@register
class HouseholdsMess:
    name = "households"
    description = "Households duplicated, split across two, or left without a household."
    touches = frozenset({HOUSEHOLD_ID, HOUSEHOLD_NAME, PERSON_ID, ROLE, ADVISOR})
    structural = True
    max_rate = 0.15

    def apply(self, ctx: MessContext, data: SourceDataset) -> list[MessEvent]:
        if ctx.rate <= 0:
            return []
        rng = ctx.rng(CRM)
        people = ctx.firm.people_by_id()
        contacts = data.get(CRM, {}).get(CONTACTS, [])
        by_household: dict[str, list[SourceRow]] = defaultdict(list)
        for row in contacts:
            if row.refs.household_id:
                by_household[row.refs.household_id].append(row)
        book_blocks = self._book_blocks(data)
        used_contacts = {str(r.values.get(PERSON_ID)) for r in contacts}
        used_households = {str(r.values.get(HOUSEHOLD_ID)) for r in contacts}
        sample_contact = next(iter(sorted(used_contacts - {""})), "C000000")
        sample_household = next(iter(sorted(used_households - {""})), "H0000")

        events: list[MessEvent] = []
        for household_id in sorted(set(by_household) | {h for h, _ in book_blocks}):
            if rng.random() >= ctx.rate:
                continue
            members = by_household.get(household_id, [])
            blocks = [key for key in book_blocks if key[0] == household_id]
            options = self._options(members, blocks)
            if not options:
                continue
            subtype = self._choose(options, rng)
            if subtype == "duplicate":
                event = self._duplicate(
                    ctx,
                    rng,
                    people,
                    members,
                    data,
                    used_contacts,
                    used_households,
                    (sample_contact, sample_household),
                )
            elif subtype == "split":
                event = self._split(ctx, rng, people, members, used_households, sample_household)
            else:
                event = self._missing(ctx, rng, members, blocks, book_blocks)
            events.append(event)
        return events

    @staticmethod
    def _book_blocks(data: SourceDataset) -> dict[tuple[str, str], list[SourceRow]]:
        """Spreadsheet blocks keyed by (truth household, table), with a household name cell."""
        blocks: dict[tuple[str, str], list[SourceRow]] = defaultdict(list)
        for table in (BOOK_ACCOUNTS, BOOK_ARCHIVE):
            for row in data.get(BOOK, {}).get(table, []):
                if row.refs.household_id:
                    blocks[(row.refs.household_id, table)].append(row)
        return {
            key: sorted(rows, key=lambda r: r.row_uid)
            for key, rows in blocks.items()
            if any(r.values.get(HOUSEHOLD_NAME) for r in rows)
        }

    @staticmethod
    def _options(members: list[SourceRow], blocks: list[tuple[str, str]]) -> dict[str, float]:
        options: dict[str, float] = {}
        if members:
            options["duplicate"] = WEIGHTS["duplicate"]
        movable = [m for m in members if m.values.get(ROLE) != HouseholdRole.PRIMARY]
        if len(members) >= 2 and movable:
            options["split"] = WEIGHTS["split"]
        if members or blocks:
            options["missing"] = WEIGHTS["missing"]
        return options

    @staticmethod
    def _choose(options: dict[str, float], rng: random.Random) -> str:
        names = sorted(options)
        return rng.choices(names, weights=[options[n] for n in names])[0]

    def _duplicate(
        self,
        ctx: MessContext,
        rng: random.Random,
        people: dict[str, TruthPerson],
        members: list[SourceRow],
        data: SourceDataset,
        used_contacts: set[str],
        used_households: set[str],
        samples: tuple[str, str],
    ) -> MessEvent:
        original_household = str(members[0].values.get(HOUSEHOLD_ID))
        new_household = _next_id(rng, used_households, samples[1], "H0000")
        adults = [
            people[pid]
            for row in members
            for pid in row.refs.person_ids
            if people[pid].household_role != HouseholdRole.DEPENDENT
        ] or [people[members[0].refs.person_ids[0]]]
        new_name = _display_names(adults, rng)
        copies: list[SourceRow] = []
        for row in members:
            values: dict[str, Any] = copy.deepcopy(row.values)
            values[PERSON_ID] = _next_id(rng, used_contacts, samples[0], "C000000")
            values[HOUSEHOLD_ID] = new_household
            values[HOUSEHOLD_NAME] = new_name
            copies.append(
                SourceRow(
                    row_uid=f"{row.row_uid}{DUPLICATE_SUFFIX}",
                    source=row.source,
                    table=row.table,
                    values=values,
                    refs=row.refs,
                )
            )
        data[CRM][CONTACTS].extend(copies)
        return ctx.event(
            subtype="duplicate",
            source=CRM,
            table=CONTACTS,
            row_uids=tuple(c.row_uid for c in copies),
            effect="structural",
            refs=self._refs(members),
            before=original_household,
            after=new_household,
        )

    def _split(
        self,
        ctx: MessContext,
        rng: random.Random,
        people: dict[str, TruthPerson],
        members: list[SourceRow],
        used_households: set[str],
        sample_household: str,
    ) -> MessEvent:
        movable = [m for m in members if m.values.get(ROLE) != HouseholdRole.PRIMARY]
        moved = rng.choice(movable)
        person = people[moved.refs.person_ids[0]]
        old_household = str(moved.values.get(HOUSEHOLD_ID))
        new_household = _next_id(rng, used_households, sample_household, "H0000")
        moved.values[HOUSEHOLD_ID] = new_household
        moved.values[HOUSEHOLD_NAME] = f"{person.first_name} {person.last_name} Household"
        moved.values[ROLE] = HouseholdRole.PRIMARY
        return ctx.event(
            subtype="split",
            source=CRM,
            table=CONTACTS,
            row_uids=(moved.row_uid,),
            effect="structural",
            refs=self._refs([moved]),
            before=old_household,
            after=new_household,
        )

    def _missing(
        self,
        ctx: MessContext,
        rng: random.Random,
        members: list[SourceRow],
        blocks: list[tuple[str, str]],
        book_blocks: dict[tuple[str, str], list[SourceRow]],
    ) -> MessEvent:
        in_crm = bool(members)
        if in_crm and (not blocks or rng.random() < 0.5):
            original = str(members[0].values.get(HOUSEHOLD_ID))
            for row in members:
                row.values[HOUSEHOLD_ID] = None
                row.values[HOUSEHOLD_NAME] = None
                row.values[ROLE] = None
            return ctx.event(
                subtype="missing",
                source=CRM,
                table=CONTACTS,
                row_uids=tuple(r.row_uid for r in members),
                effect="structural",
                refs=self._refs(members),
                before=original,
            )
        key = rng.choice(sorted(blocks))
        first = book_blocks[key][0]
        original = str(first.values.get(HOUSEHOLD_NAME))
        first.values[HOUSEHOLD_NAME] = ""
        return ctx.event(
            subtype="missing",
            source=BOOK,
            table=key[1],
            row_uids=(first.row_uid,),
            effect="structural",
            refs=first.refs,
            before=original,
            after="",
        )

    @staticmethod
    def _refs(rows: list[SourceRow]) -> TruthRefs:
        ids = tuple(pid for row in rows for pid in row.refs.person_ids)
        return TruthRefs(person_ids=ids, household_id=rows[0].refs.household_id)

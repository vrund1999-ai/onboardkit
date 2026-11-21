"""The ``names`` mess type: the same person written in different ways.

A selected row gets exactly one variant. Subtype weights (and how hard each is to match):

| subtype            | weight | ambiguity |
|--------------------|--------|-----------|
| nickname           | 0.25   | low       |
| initial_only       | 0.20   | medium (high when it matches another household member) |
| order_swap         | 0.15   | low       |
| suffix_change      | 0.10   | medium    |
| case_change        | 0.10   | low       |
| typo               | 0.10   | medium    |
| hyphen_or_maiden   | 0.05   | high      |
| whitespace_punct   | 0.05   | low       |

Where a subtype does not apply to a row (for example no known nickname), the next subtype in a
weighted order is tried; a missing nickname falls back to ``initial_only``. Case changes are not
made to the custodian's owner names and registration because that source upper-cases them when it
writes, so a change there would never be visible.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from onboardkit.datagen.mess.base import (
    Ambiguity,
    MessContext,
    MessEvent,
    SourceDataset,
)
from onboardkit.datagen.mess.registry import register
from onboardkit.datagen.sources.base import SourceRow
from onboardkit.datagen.sources.formatters import NameParts
from onboardkit.datagen.truth.model import TruthPerson

DATA_FILE = Path(__file__).with_name("data") / "nicknames.yaml"

FIRST = "person.first_name"
LAST = "person.last_name"
SUFFIX = "person.suffix"
OWNERS = "account.owner_names"
REGISTRATION = "account.registration"
HOUSEHOLD = "household.name"

WEIGHTS: dict[str, float] = {
    "nickname": 0.25,
    "initial_only": 0.20,
    "order_swap": 0.15,
    "suffix_change": 0.10,
    "case_change": 0.10,
    "typo": 0.10,
    "hyphen_or_maiden": 0.05,
    "whitespace_punct": 0.05,
}
AMBIGUITY: dict[str, Ambiguity] = {
    "nickname": "low",
    "initial_only": "medium",
    "order_swap": "low",
    "suffix_change": "medium",
    "case_change": "low",
    "typo": "medium",
    "hyphen_or_maiden": "high",
    "whitespace_punct": "low",
}
SUFFIX_ADDED = "Jr."
_WORD = re.compile(r"[A-Za-z'-]+")


@lru_cache(maxsize=1)
def _data() -> dict[str, Any]:
    with DATA_FILE.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    assert isinstance(loaded, dict)
    return loaded


def nicknames() -> dict[str, list[str]]:
    """Lower-case formal name to its nicknames (title case)."""
    table = _data()["nicknames"]
    return {formal.lower(): list(options) for formal, options in table.items()}


def other_surnames() -> list[str]:
    return list(_data()["other_surnames"])


@dataclass
class _Change:
    """One value change: what to write, how to describe it, and how to apply it."""

    concept: str
    before: str | None
    after: str | None
    apply: Callable[[], None]
    ambiguity: Ambiguity | None = None
    subtype: str = ""  # set by the picker, or by a handler that falls back to another subtype


@dataclass
class _RowContext:
    row: SourceRow
    people: list[TruthPerson]  # people the row refers to, then their household's members
    members: list[TruthPerson]  # household members, for ambiguity checks

    def parts(self) -> list[tuple[str, str]]:
        """Separate name-part concepts with text in this row."""
        found = []
        for concept in (FIRST, LAST):
            value = self.row.values.get(concept)
            if isinstance(value, str) and value.strip():
                found.append((concept, value))
        return found

    def owners(self) -> list[tuple[int, NameParts]]:
        value = self.row.values.get(OWNERS)
        if not isinstance(value, list):
            return []
        return [(i, part) for i, part in enumerate(value) if isinstance(part, NameParts)]

    def strings(self) -> list[tuple[str, str]]:
        """Free-text concepts that contain names."""
        found = []
        for concept in (REGISTRATION, HOUSEHOLD):
            value = self.row.values.get(concept)
            if isinstance(value, str) and value.strip():
                found.append((concept, value))
        return found

    def person_for_part(self) -> TruthPerson | None:
        ids = self.row.refs.person_ids
        by_id = {p.person_id: p for p in self.people}
        return by_id.get(ids[0]) if ids else None

    def person_for_owner(self, index: int) -> TruthPerson | None:
        ids = self.row.refs.person_ids
        by_id = {p.person_id: p for p in self.people}
        return by_id.get(ids[index]) if index < len(ids) else None


def render(part: NameParts) -> str:
    return " ".join(p for p in (part.first, part.middle, part.last, part.suffix) if p)


def _match_case(original: str, new: str) -> str:
    if len(original) > 1 and original.isupper():
        return new.upper()
    if original.islower():
        return new.lower()
    return new


def _words(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group()) for m in _WORD.finditer(text)]


def _splice(text: str, start: int, end: int, new: str) -> str:
    return text[:start] + new + text[end:]


def _set_value(row: SourceRow, concept: str, value: Any) -> Callable[[], None]:
    def apply() -> None:
        row.values[concept] = value

    return apply


def _set_owner(row: SourceRow, index: int, part: NameParts) -> Callable[[], None]:
    def apply() -> None:
        owners = list(row.values[OWNERS])
        owners[index] = part
        row.values[OWNERS] = owners

    return apply


def _typo_word(word: str, rng: random.Random) -> str | None:
    """A single edit that never touches the first letter."""
    if len(word) < 3:
        return None
    for _ in range(8):
        operation = rng.choice(("delete", "insert", "substitute", "transpose"))
        position = rng.randrange(1, len(word))
        letter = rng.choice("abcdefghijklmnopqrstuvwxyz")
        letter = letter.upper() if word[position].isupper() else letter
        if operation == "delete":
            result = word[:position] + word[position + 1 :]
        elif operation == "insert":
            result = word[:position] + letter + word[position:]
        elif operation == "substitute":
            result = word[:position] + letter + word[position + 1 :]
        elif position + 1 < len(word):
            result = word[:position] + word[position + 1] + word[position] + word[position + 2 :]
        else:
            continue
        if result != word and result[0] == word[0]:
            return result
    return None


def _clashes(rc: _RowContext, person: TruthPerson | None, initial: str) -> bool:
    """Would this initial also fit another member of the same household?"""
    if person is None:
        return False
    return any(
        other.person_id != person.person_id
        and other.last_name.lower() == person.last_name.lower()
        and other.first_name[:1].lower() == initial[:1].lower()
        for other in rc.members
    )


Handler = Callable[[_RowContext, random.Random], list[_Change]]


def _name_words(
    rc: _RowContext, text: str, wanted: Callable[[TruthPerson], list[str]]
) -> list[tuple[int, int, str, TruthPerson]]:
    """Words in ``text`` equal to one of the names ``wanted`` returns for a known person."""
    found = []
    for start, end, word in _words(text):
        for person in rc.people:
            if word.lower() in {name.lower() for name in wanted(person)}:
                found.append((start, end, word, person))
                break
    return found


def _nickname(rc: _RowContext, rng: random.Random) -> list[_Change]:
    table = nicknames()
    candidates: list[_Change] = []
    for concept, value in rc.parts():
        if concept == FIRST and value.lower() in table:
            new = _match_case(value, rng.choice(table[value.lower()]))
            candidates.append(_Change(concept, value, new, _set_value(rc.row, concept, new)))
    for index, part in rc.owners():
        if part.first.lower() in table:
            new = _match_case(part.first, rng.choice(table[part.first.lower()]))
            changed = replace(part, first=new)
            candidates.append(
                _Change(OWNERS, render(part), render(changed), _set_owner(rc.row, index, changed))
            )
    for concept, text in rc.strings():
        words = _name_words(
            rc, text, lambda p: [p.first_name] if p.first_name.lower() in table else []
        )
        for start, end, word, person in words:
            new = _match_case(word, rng.choice(table[person.first_name.lower()]))
            result = _splice(text, start, end, new)
            candidates.append(_Change(concept, text, result, _set_value(rc.row, concept, result)))
    if not candidates:
        fallback = _initial_only(rc, rng)
        for change in fallback:
            change.subtype = "initial_only"
        return fallback
    return [rng.choice(candidates)]


def _initial_only(rc: _RowContext, rng: random.Random) -> list[_Change]:
    candidates: list[_Change] = []
    for concept, value in rc.parts():
        if concept == FIRST and len(value) > 1 and not value.endswith("."):
            new = f"{value[0]}."
            high = _clashes(rc, rc.person_for_part(), value[0])
            candidates.append(
                _Change(
                    concept, value, new, _set_value(rc.row, concept, new), "high" if high else None
                )
            )
    for index, part in rc.owners():
        if len(part.first) > 1 and not part.first.endswith("."):
            changed = replace(part, first=f"{part.first[0]}.")
            high = _clashes(rc, rc.person_for_owner(index), part.first[0])
            candidates.append(
                _Change(
                    OWNERS,
                    render(part),
                    render(changed),
                    _set_owner(rc.row, index, changed),
                    "high" if high else None,
                )
            )
    for concept, text in rc.strings():
        for start, end, word, person in _name_words(rc, text, lambda p: [p.first_name]):
            if len(word) > 1:
                result = _splice(text, start, end, f"{word[0]}.")
                high = _clashes(rc, person, word[0])
                candidates.append(
                    _Change(
                        concept,
                        text,
                        result,
                        _set_value(rc.row, concept, result),
                        "high" if high else None,
                    )
                )
    return [rng.choice(candidates)] if candidates else []


def _suffix_change(rc: _RowContext, rng: random.Random) -> list[_Change]:
    candidates: list[_Change] = []
    if SUFFIX in rc.row.values:
        old = rc.row.values[SUFFIX]
        new = None if old else SUFFIX_ADDED
        candidates.append(_Change(SUFFIX, old or None, new, _set_value(rc.row, SUFFIX, new)))
    for index, part in rc.owners():
        changed = replace(part, suffix=None if part.suffix else SUFFIX_ADDED)
        candidates.append(
            _Change(OWNERS, render(part), render(changed), _set_owner(rc.row, index, changed))
        )
    return [rng.choice(candidates)] if candidates else []


def _order_swap(rc: _RowContext, rng: random.Random) -> list[_Change]:
    candidates: list[list[_Change]] = []
    parts = dict(rc.parts())
    if FIRST in parts and LAST in parts and parts[FIRST].lower() != parts[LAST].lower():
        first, last = parts[FIRST], parts[LAST]
        candidates.append(
            [
                _Change(FIRST, first, last, _set_value(rc.row, FIRST, last)),
                _Change(LAST, last, first, _set_value(rc.row, LAST, first)),
            ]
        )
    for index, part in rc.owners():
        if part.first.lower() != part.last.lower():
            changed = replace(part, first=part.last, last=part.first)
            candidates.append(
                [_Change(OWNERS, render(part), render(changed), _set_owner(rc.row, index, changed))]
            )
    household = rc.row.values.get(HOUSEHOLD)
    if isinstance(household, str):
        match = re.fullmatch(r"([^,]+),\s*(.+)", household)
        if match:
            result = f"{match.group(2)} {match.group(1)}"
            candidates.append(
                [_Change(HOUSEHOLD, household, result, _set_value(rc.row, HOUSEHOLD, result))]
            )
    return rng.choice(candidates) if candidates else []


def _case_change(rc: _RowContext, rng: random.Random) -> list[_Change]:
    candidates: list[_Change] = []
    for concept, value in [*rc.parts(), *[(c, t) for c, t in rc.strings() if c == HOUSEHOLD]]:
        options = sorted({value.upper(), value.lower(), value.title()} - {value})
        if options:
            new = rng.choice(options)
            candidates.append(_Change(concept, value, new, _set_value(rc.row, concept, new)))
    return [rng.choice(candidates)] if candidates else []


def _typo(rc: _RowContext, rng: random.Random) -> list[_Change]:
    candidates: list[_Change] = []
    for concept, value in rc.parts():
        new = _typo_word(value, rng)
        if new:
            candidates.append(_Change(concept, value, new, _set_value(rc.row, concept, new)))
    for index, part in rc.owners():
        for attribute in ("first", "last"):
            new = _typo_word(getattr(part, attribute), rng)
            if new:
                changed = replace(part, **{attribute: new})
                candidates.append(
                    _Change(
                        OWNERS, render(part), render(changed), _set_owner(rc.row, index, changed)
                    )
                )
    for concept, text in rc.strings():
        for start, end, word, _ in _name_words(rc, text, lambda p: [p.first_name, p.last_name]):
            new = _typo_word(word, rng)
            if new:
                result = _splice(text, start, end, new)
                candidates.append(
                    _Change(concept, text, result, _set_value(rc.row, concept, result))
                )
    return [rng.choice(candidates)] if candidates else []


def _hyphen_or_maiden(rc: _RowContext, rng: random.Random) -> list[_Change]:
    surnames = other_surnames()
    candidates: list[_Change] = []
    for concept, value in rc.parts():
        if concept == LAST and "-" not in value:
            options = [s for s in surnames if s.lower() != value.lower()]
            new = f"{value}-{rng.choice(options)}"
            candidates.append(_Change(concept, value, new, _set_value(rc.row, concept, new)))
    for index, part in rc.owners():
        if "-" not in part.last:
            options = [s for s in surnames if s.lower() != part.last.lower()]
            changed = replace(part, last=f"{part.last}-{rng.choice(options)}")
            candidates.append(
                _Change(OWNERS, render(part), render(changed), _set_owner(rc.row, index, changed))
            )
    return [rng.choice(candidates)] if candidates else []


def _whitespace_punct(rc: _RowContext, rng: random.Random) -> list[_Change]:
    candidates: list[_Change] = []
    for concept, value in rc.parts():
        new = rng.choice([value + " ", " " + value, value + "."])
        candidates.append(_Change(concept, value, new, _set_value(rc.row, concept, new)))
    for index, part in rc.owners():
        attribute = rng.choice(("first", "last"))
        value = getattr(part, attribute)
        changed = replace(part, **{attribute: rng.choice([value + " ", " " + value, value + "."])})
        candidates.append(
            _Change(OWNERS, render(part), render(changed), _set_owner(rc.row, index, changed))
        )
    for concept, text in rc.strings():
        options = [text + ".", text + " "]
        if " " in text:
            options.append(text.replace(" ", "  ", 1))
        new = rng.choice(options)
        candidates.append(_Change(concept, text, new, _set_value(rc.row, concept, new)))
    return [rng.choice(candidates)] if candidates else []


HANDLERS: dict[str, Handler] = {
    "nickname": _nickname,
    "initial_only": _initial_only,
    "order_swap": _order_swap,
    "suffix_change": _suffix_change,
    "case_change": _case_change,
    "typo": _typo,
    "hyphen_or_maiden": _hyphen_or_maiden,
    "whitespace_punct": _whitespace_punct,
}


def _weighted_order(rng: random.Random) -> list[str]:
    """Subtypes in a random order where heavier weights tend to come first."""
    keys = {name: rng.random() ** (1.0 / weight) for name, weight in WEIGHTS.items()}
    return sorted(keys, key=lambda name: keys[name], reverse=True)


@register
class NamesMess:
    name = "names"
    description = "Nicknames, initials, suffixes, order, case, typos, and hyphenated surnames."
    touches = frozenset({FIRST, LAST, SUFFIX, OWNERS, REGISTRATION, HOUSEHOLD})
    structural = False
    max_rate = 0.35
    subtypes = frozenset(WEIGHTS)

    def apply(self, ctx: MessContext, data: SourceDataset) -> list[MessEvent]:
        if ctx.rate <= 0:
            return []
        people = ctx.firm.people_by_id()
        households = ctx.firm.households_by_id()
        events: list[MessEvent] = []
        for source in sorted(data):
            rng = ctx.rng(source)
            for table in sorted(data[source]):
                for row in data[source][table]:
                    if not self._eligible(row) or rng.random() >= ctx.rate:
                        continue
                    household = households.get(str(row.refs.household_id))
                    members = (
                        [people[m] for m in household.member_ids] if household is not None else []
                    )
                    known = {p.person_id: p for p in members}
                    known.update({pid: people[pid] for pid in row.refs.person_ids})
                    row_context = _RowContext(row, list(known.values()), members)
                    for change in self._pick(row_context, rng):
                        change.apply()
                        events.append(
                            ctx.event(
                                subtype=change.subtype,
                                source=source,
                                table=table,
                                row_uids=(row.row_uid,),
                                effect="entity_variant",
                                refs=row.refs,
                                concept=change.concept,
                                before=change.before,
                                after=change.after,
                                ambiguity=change.ambiguity or AMBIGUITY[change.subtype],
                            )
                        )
        return events

    def _eligible(self, row: SourceRow) -> bool:
        return any(row.values.get(concept) not in (None, "", []) for concept in self.touches)

    def _pick(self, rc: _RowContext, rng: random.Random) -> list[_Change]:
        for subtype in _weighted_order(rng):
            changes = HANDLERS[subtype](rc, rng)
            if changes and all(c.before != c.after for c in changes):
                for change in changes:
                    change.subtype = change.subtype or subtype
                return changes
        return []

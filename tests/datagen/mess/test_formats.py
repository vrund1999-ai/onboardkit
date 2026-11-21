import copy
import random
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest
from mess_helpers import firm_of, projection

from onboardkit.datagen.mess.base import MessContext, MessEvent, SourceDataset, group_by_table
from onboardkit.datagen.mess.engine import run_mess
from onboardkit.datagen.mess.formats import (
    AMBIGUITY,
    DATES,
    STATES,
    SUBTYPES,
    FormatsMess,
    make_variant,
)
from onboardkit.datagen.mess.registry import DEFAULT_REGISTRY
from onboardkit.datagen.sources.base import RawText
from onboardkit.datagen.sources.book_of_business import BookOfBusinessExporter
from onboardkit.datagen.sources.crm import CrmExporter
from onboardkit.datagen.sources.custodian import CustodianExporter

AS_OF = date(2025, 12, 31)
ACCOUNT = "account.number"


def run(firm_size: int, rate: float, seed: int = 42) -> tuple[SourceDataset, list[MessEvent]]:
    firm = firm_of(firm_size)
    data = group_by_table(copy.deepcopy(projection(firm)))
    events = run_mess(
        data, ["formats"], lambda mess: MessContext(mess.name, rate, seed, firm, AS_OF)
    )
    return data, events


def test_registered_with_story_settings() -> None:
    mess = DEFAULT_REGISTRY.get("formats")
    assert mess.max_rate == 0.40
    assert not mess.structural
    assert mess.touches == {
        "person.date_of_birth",
        "person.client_since",
        "account.open_date",
        "meta.review_date",
        "account.number",
        "person.phone",
        "person.address_state",
        "account.balance",
    }
    assert set(AMBIGUITY) == {s for group in SUBTYPES.values() for s in group}


def test_zero_intensity_changes_nothing() -> None:
    firm = firm_of(15)
    before = group_by_table(copy.deepcopy(projection(firm)))
    data, events = run(15, 0.0)
    assert events == []
    assert data == before


def test_every_subtype_occurs_and_every_event_is_a_format_variant() -> None:
    _, events = run(300, 0.4)
    assert {e.subtype for e in events} >= set(AMBIGUITY) - {"acct_leading_zeros"}
    for event in events:
        assert event.effect == "format_variant"
        assert event.mess_type == "formats"
        assert event.ambiguity == AMBIGUITY[event.subtype]
        assert event.before is not None
        assert event.after is not None
        assert event.before != event.after


def test_changed_values_are_raw_text_that_keeps_the_original() -> None:
    data, events = run(60, 0.4)
    by_uid = {r.row_uid: r for tables in data.values() for rows in tables.values() for r in rows}
    assert events
    for event in events:
        value = by_uid[event.row_uids[0]].values[event.concept or ""]
        assert isinstance(value, RawText)
        assert value.text == event.after
        original = value.original
        if isinstance(original, date):
            assert original.isoformat() == event.before
        elif isinstance(original, Decimal):
            assert f"{original:f}" == event.before
        else:
            assert original == event.before


def test_at_least_three_date_formats_in_crm_date_of_birth_at_high_intensity() -> None:
    data, _ = run(300, 0.4)
    shapes = set()
    for row in data["crm"]["contacts"]:
        value = row.values["person.date_of_birth"]
        if isinstance(value, RawText):
            shapes.add(re.sub(r"[A-Za-z]+", "A", re.sub(r"\d", "9", value.text)))
    assert len(shapes) >= 3


DATE_PARSERS = {
    "date_alt_format": ["%m/%d/%Y", "%d %b %Y", "%B %d, %Y", "%d.%m.%Y", "%Y-%m-%d"],
    "date_two_digit_year": ["%m/%d/%y"],
}


def parse(text: str, patterns: list[str]) -> date | None:
    for pattern in patterns:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def test_date_variants_parse_back_to_the_original() -> None:
    _, events = run(300, 0.4)
    checked: Counter[str] = Counter()
    for event in events:
        if event.concept not in DATES or event.subtype not in DATE_PARSERS:
            continue
        original = date.fromisoformat(event.before or "")
        parsed = parse(event.after or "", DATE_PARSERS[event.subtype])
        assert parsed is not None
        if event.subtype == "date_two_digit_year":
            assert (parsed.month, parsed.day) == (original.month, original.day)
            assert parsed.year % 100 == original.year % 100
        else:
            assert parsed == original
        checked[event.subtype] += 1
    assert set(checked) == set(DATE_PARSERS)


def test_day_month_swap_is_only_used_for_days_up_to_twelve_and_is_high() -> None:
    _, events = run(300, 0.4)
    swaps = [e for e in events if e.subtype == "date_day_month_swap"]
    assert swaps
    for event in swaps:
        original = date.fromisoformat(event.before or "")
        assert original.day <= 12
        assert original.day != original.month
        assert event.ambiguity == "high"
        assert event.after == f"{original.day:02d}/{original.month:02d}/{original.year}"
    others = [e for e in events if e.subtype != "date_day_month_swap" and e.concept in DATES]
    assert all(e.ambiguity != "high" for e in others)
    rng = random.Random(1)
    assert make_variant("date_day_month_swap", date(1980, 3, 25), "crm", DATES[0], rng) is None
    assert make_variant("date_day_month_swap", date(1980, 4, 4), "crm", DATES[0], rng) is None
    assert make_variant("date_day_month_swap", date(1980, 3, 4), "crm", DATES[0], rng)


def test_account_numbers_stay_unique_per_source() -> None:
    firm = firm_of(300)
    original = group_by_table(copy.deepcopy(projection(firm)))
    data, events = run(300, 0.4)
    assert any(e.concept == ACCOUNT for e in events)

    def texts(dataset: SourceDataset, source: str) -> list[str]:
        out = []
        for rows in dataset[source].values():
            for r in rows:
                if ACCOUNT in r.values:
                    value = r.values[ACCOUNT]
                    out.append(value.text if isinstance(value, RawText) else str(value))
        return out

    for source in data:
        before = Counter(texts(original, source))
        after = Counter(texts(data, source))
        assert sum(after.values()) == sum(before.values())
        # a variant never equals another account's number: distinct count only grows
        assert len(after) >= len(before)
        changed = {
            e.after for e in events if e.source == source and e.concept == ACCOUNT and e.after
        }
        assert not changed & set(before)


def test_account_variants_normalise_to_the_original() -> None:
    _, events = run(300, 0.4)
    subtypes = {e.subtype for e in events if e.concept == ACCOUNT}
    assert {"acct_separators", "acct_prefix_case"} <= subtypes
    for event in events:
        if event.concept == ACCOUNT and event.subtype != "acct_leading_zeros":
            assert re.sub(r"[\s-]", "", event.after or "").upper() == event.before


def test_leading_zero_variant_strips_zeros_only_when_they_exist() -> None:
    rng = random.Random(1)
    variant = make_variant("acct_leading_zeros", "AB000123", "custodian", ACCOUNT, rng)
    assert variant is not None
    assert variant.text == "AB123"
    assert make_variant("acct_leading_zeros", "AB143753", "custodian", ACCOUNT, rng) is None


def test_phone_state_and_money_variants() -> None:
    _, events = run(300, 0.4)
    phones = [e for e in events if e.subtype == "phone_style"]
    states = [e for e in events if e.subtype == "state_full_name"]
    money = [e for e in events if e.subtype == "money_text"]
    assert phones
    assert states
    assert money
    for e in phones:
        assert re.sub(r"\D", "", e.after or "")[-10:] == re.sub(r"\D", "", e.before or "")[-10:]
    for e in states:
        assert STATES[e.before or ""] == e.after
    assert {e.source for e in money} == {"book_of_business"}
    for e in money:
        text = (e.after or "").strip().lstrip("~$").replace(",", "")
        amount = Decimal(text[:-1]) * 1000 if text.endswith("k") else Decimal(text)
        assert amount == Decimal(e.before or "")
    assert not any(
        e.concept == "account.balance" and e.source != "book_of_business" for e in events
    )


def test_majority_of_every_column_keeps_the_default_format() -> None:
    data, _ = run(300, 1.0)  # the rate is capped at half
    columns: dict[tuple[str, str, str], list[bool]] = defaultdict(list)
    for source, tables in data.items():
        for table, rows in tables.items():
            for row in rows:
                for concept, value in row.values.items():
                    if concept in FormatsMess.touches:
                        columns[(source, table, concept)].append(isinstance(value, RawText))
    assert columns
    for flags in columns.values():
        assert sum(flags) <= len(flags) / 2
    assert any(sum(flags) > 0 for flags in columns.values())


def test_readme_account_number_headers_remain_unchanged(tmp_path: Path) -> None:
    firm = firm_of(60)
    data, _ = run(60, 0.4)
    custodian = CustodianExporter.for_firm(firm)
    custodian.project(firm)
    custodian.write([r for t in data["custodian"].values() for r in t], tmp_path)
    crm = CrmExporter()
    crm.project(firm)
    crm.write([r for t in data["crm"].values() for r in t], tmp_path)
    book = BookOfBusinessExporter()
    book.project(firm)
    result = book.write([r for t in data["book_of_business"].values() for r in t], tmp_path)
    custodian_text = (tmp_path / "custodian_accounts.csv").read_text(encoding="utf-8-sig")
    assert '"Acct #"' in custodian_text
    crm_header = (tmp_path / "crm_linked_accounts.csv").read_text(encoding="utf-8").splitlines()[0]
    assert "account_number" in crm_header
    sheet = openpyxl.load_workbook(result.files[0])["Archive"]
    assert "AcctNo" in [c.value for c in sheet[5]]


@pytest.mark.parametrize("seed", [1, 2])
def test_same_seed_same_events(seed: int) -> None:
    assert run(60, 0.3, seed=seed)[1] == run(60, 0.3, seed=seed)[1]


def test_other_seed_differs() -> None:
    assert run(60, 0.3, seed=1)[1] != run(60, 0.3, seed=2)[1]

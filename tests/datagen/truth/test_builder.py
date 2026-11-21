import re
from collections import Counter
from decimal import Decimal
from pathlib import Path
from statistics import median

import pytest

from onboardkit.datagen.truth.builder import build_firm
from onboardkit.datagen.truth.model import HouseholdRole, TruthAccount, TruthFirm
from onboardkit.datagen.truth.profile import IRA_TYPES, AccountType, Archetype, load_profile
from onboardkit.datagen.truth.validate import validate_firm

PROFILE = load_profile()
SRC = Path(__file__).resolve().parents[3] / "src" / "onboardkit" / "datagen"


@pytest.fixture(scope="module")
def default_firm() -> TruthFirm:
    return build_firm(PROFILE, 300, 42)


@pytest.mark.parametrize("n", [15, 300])
def test_builds_and_validates(n: int) -> None:
    firm = build_firm(PROFILE, n, 42)
    assert len(firm.households) == n
    validate_firm(firm)


@pytest.mark.parametrize("seed", [1, 2, 3, 7, 99])
def test_validates_across_seeds(seed: int) -> None:
    validate_firm(build_firm(PROFILE, 120, seed))


def test_identical_arguments_give_equal_firms() -> None:
    a = build_firm(PROFILE, 40, 5)
    b = build_firm(PROFILE, 40, 5)
    assert a == b
    assert a.model_dump_json() == b.model_dump_json()


def test_different_seed_changes_output() -> None:
    assert build_firm(PROFILE, 20, 1).people != build_firm(PROFILE, 20, 2).people


def test_sample_is_a_prefix_of_default(default_firm: TruthFirm) -> None:
    sample = build_firm(PROFILE, 15, 42)
    assert default_firm.households[:15] == sample.households
    assert default_firm.people[: len(sample.people)] == sample.people
    assert default_firm.accounts[: len(sample.accounts)] == sample.accounts


def test_first_person_of_seed_42_is_pinned() -> None:
    # Surfaces unintended changes in the Faker version or the stream layout.
    person = build_firm(PROFILE, 1, 42).people[0]
    assert person.person_id == "P-00001"
    assert person.full_name() == "Wesley V Arnold"
    assert person.date_of_birth.isoformat() == "1990-03-14"
    assert person.email == "wesley.arnold89@example.com"


def test_archetype_shares_close_to_profile(default_firm: TruthFirm) -> None:
    counts = Counter(h.archetype for h in default_firm.households)
    for archetype in Archetype:
        observed = counts[archetype] / 300
        assert abs(observed - PROFILE.archetypes[archetype].share) < 0.05, archetype


def test_account_count_shares_close_to_profile(default_firm: TruthFirm) -> None:
    per_household = Counter(a.household_id for a in default_firm.accounts)
    assert len(per_household) == 300
    for bucket in PROFILE.account_counts:
        low, high = bucket.accounts
        observed = sum(low <= n <= high for n in per_household.values()) / 300
        assert abs(observed - bucket.share) < 0.07, bucket


def test_ownership_rules_hold_for_every_account(default_firm: TruthFirm) -> None:
    people = default_firm.people_by_id()
    held: set[tuple[str, AccountType]] = set()
    seen = Counter(a.account_type for a in default_firm.accounts)
    assert set(seen) == set(AccountType)  # every type occurs, so every rule is exercised
    for account in default_firm.accounts:
        for owner_id in account.owner_ids:
            assert people[owner_id].household_role is not HouseholdRole.DEPENDENT
            assert people[owner_id].household_id == account.household_id
        if account.account_type in IRA_TYPES:
            assert len(account.owner_ids) == 1
            key = (account.owner_ids[0], account.account_type)
            assert key not in held
            held.add(key)
        elif account.account_type is AccountType.JOINT:
            assert len(set(account.owner_ids)) == 2
        elif account.account_type is AccountType.EDUCATION_529:
            assert len(account.owner_ids) == 1
            assert account.beneficiary_id is not None
            beneficiary = people[account.beneficiary_id]
            assert beneficiary.household_role is HouseholdRole.DEPENDENT
            assert beneficiary.household_id == account.household_id
        else:
            assert len(account.owner_ids) == 1
        if account.account_type is not AccountType.EDUCATION_529:
            assert account.beneficiary_id is None


def test_single_adult_households_never_get_joint_or_529(default_firm: TruthFirm) -> None:
    single = {
        h.household_id for h in default_firm.households if h.archetype is Archetype.SINGLE_ADULT
    }
    assert single
    for account in default_firm.accounts:
        if account.household_id in single:
            assert account.account_type not in {AccountType.JOINT, AccountType.EDUCATION_529}


def test_money_is_decimal_with_two_places(default_firm: TruthFirm) -> None:
    for account in default_firm.accounts:
        assert isinstance(account.balance, Decimal)
        assert account.balance.as_tuple().exponent == -2
        assert account.balance > 0
    assert "float" not in str(TruthAccount.model_fields["balance"].annotation)


def test_balance_distribution_matches_profile() -> None:
    values: list[Decimal] = []
    for seed in range(1, 4):
        firm = build_firm(PROFILE, 300, seed)
        values += [
            a.balance for a in firm.accounts if a.account_type is not AccountType.EDUCATION_529
        ]
    assert abs(float(median(values)) - 150_000) / 150_000 < 0.15
    assert min(values) >= Decimal(PROFILE.balances.min)
    assert max(values) <= Decimal(PROFILE.balances.max)


def test_account_numbers_use_fictional_prefix_and_are_unique(default_firm: TruthFirm) -> None:
    numbers = [a.account_number for a in default_firm.accounts]
    assert len(numbers) == len(set(numbers))
    assert all(re.fullmatch(r"MC\d{6}", n) for n in numbers)


def test_registration_titles(default_firm: TruthFirm) -> None:
    for account in default_firm.accounts:
        title = account.registration_title
        assert title == title.upper()
        if account.account_type is AccountType.JOINT:
            assert title.endswith(" JTWROS")
            assert " & " in title
        if account.account_type is AccountType.ROTH_IRA:
            assert title.endswith(" ROTH IRA")
        if account.account_type is AccountType.EDUCATION_529:
            assert " FBO " in title
            assert title.endswith(" 529")


@pytest.mark.parametrize(
    "name", ["rng.py", "truth/builder.py", "truth/model.py", "truth/validate.py"]
)
def test_no_clock_or_global_random_state(name: str) -> None:
    source = (SRC / name).read_text(encoding="utf-8")
    for forbidden in ("datetime.now", "date.today", "time.time", "uuid", "random.seed"):
        assert forbidden not in source
    assert not re.search(r"(?<![\w.])random\.(random|randint|choice|choices|shuffle)\(", source)

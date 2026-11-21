"""Deterministic builder for the fictional firm.

Stream independence: every household draws from its own streams, named by its index, so household
``i`` is identical whatever number of households is built. A 15-household firm is therefore a
prefix of the 300-household firm (people and account attributes; identifiers are sequential in
creation order, so they match as well). Nothing here reads the clock or global random state.
"""

from __future__ import annotations

import math
import random
import string
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

from faker import Faker

from onboardkit.datagen.rng import derive_rng, derive_seed
from onboardkit.datagen.truth.holdings import build_holdings, build_securities
from onboardkit.datagen.truth.model import (
    HouseholdRole,
    TruthAccount,
    TruthFirm,
    TruthHousehold,
    TruthPerson,
)
from onboardkit.datagen.truth.profile import (
    IRA_TYPES,
    AccountType,
    FirmProfile,
)

_CENT = Decimal("0.01")
_SUFFIXES = ("Jr.", "Sr.", "II", "III")
_NUMBER_STRIDE = 7919  # prime, so coprime with any power of ten: a bijection on the number space


def add_years(day: date, years: int) -> date:
    """Return ``day`` shifted by whole years (29 February moves to 28 February)."""
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)


def _random_date(rng: random.Random, low: date, high: date) -> date:
    if low > high:
        raise ValueError(f"empty date range {low}..{high}")
    return low + timedelta(days=rng.randint(0, (high - low).days))


def _pick[T](rng: random.Random, items: list[T], weights: list[float]) -> T:
    return rng.choices(items, weights=weights, k=1)[0]


def _first_name(rng: random.Random, fake: Faker) -> str:
    return str(fake.first_name_male() if rng.random() < 0.5 else fake.first_name_female())


def _person(
    rng: random.Random,
    fake: Faker,
    *,
    person_id: str,
    household_id: str,
    role: HouseholdRole,
    last_name: str,
    dob: date,
    address: tuple[str, str, str, str],
) -> TruthPerson:
    first = _first_name(rng, fake)
    adult = role is not HouseholdRole.DEPENDENT
    middle = rng.choice(string.ascii_uppercase) if adult and rng.random() < 0.6 else None
    suffix = rng.choice(_SUFFIXES) if adult and rng.random() < 0.05 else None
    # example.com is reserved for documentation, so these addresses can never be real.
    email = (
        f"{first}.{last_name}{rng.randint(1, 99)}@example.com".lower().replace("'", "")
        if adult
        else None
    )
    # 555-01xx numbers are reserved for fiction.
    phone = f"({rng.randint(201, 989)}) 555-01{rng.randint(0, 99):02d}" if adult else None
    return TruthPerson(
        person_id=person_id,
        first_name=first,
        middle_initial=middle,
        last_name=last_name,
        suffix=suffix,
        date_of_birth=dob,
        email=email,
        phone=phone,
        address_line1=address[0],
        address_city=address[1],
        address_state=address[2],
        address_postal=address[3],
        tax_id_last4=f"{rng.randint(0, 9999):04d}",
        household_id=household_id,
        household_role=role,
    )


def _pid(count_before: int) -> str:
    return f"P-{count_before + 1:05d}"


def _title_name(person: TruthPerson) -> str:
    return person.full_name().upper()


def registration_title(
    account_type: AccountType, owners: list[TruthPerson], beneficiary: TruthPerson | None
) -> str:
    names = [_title_name(o) for o in owners]
    match account_type:
        case AccountType.INDIVIDUAL:
            return f"{names[0]} INDIVIDUAL"
        case AccountType.JOINT:
            return f"{names[0]} & {names[1]} JTWROS"
        case AccountType.TRADITIONAL_IRA:
            return f"{names[0]} TRADITIONAL IRA"
        case AccountType.ROTH_IRA:
            return f"{names[0]} ROTH IRA"
        case AccountType.ROLLOVER_IRA:
            return f"{names[0]} ROLLOVER IRA"
        case AccountType.EDUCATION_529:
            if beneficiary is None:
                raise ValueError("a 529 needs a beneficiary")
            return f"{names[0]} FBO {_title_name(beneficiary)} 529"


def _draw_balance(rng: random.Random, profile: FirmProfile, account_type: AccountType) -> Decimal:
    rules = profile.balances
    scale = rules.type_scale.get(account_type, 1.0)
    value = rng.lognormvariate(math.log(rules.median * scale), rules.sigma)
    clamped = min(max(value, rules.min), rules.max)
    return Decimal(repr(clamped)).quantize(_CENT, rounding=ROUND_HALF_EVEN)


def _account_number(profile: FirmProfile, offset: int, sequence: int) -> str:
    fmt = profile.account_number
    space = 10**fmt.digits
    if sequence >= space:
        raise ValueError("account number space exhausted")
    return f"{fmt.prefix}{(offset + sequence * _NUMBER_STRIDE) % space:0{fmt.digits}d}"


def build_firm(
    profile: FirmProfile,
    n_households: int,
    root_seed: int,
    as_of_date: date | None = None,
) -> TruthFirm:
    """Build the complete, clean fictional firm."""
    as_of = as_of_date or profile.firm.as_of_date
    rules = profile.people
    dates = profile.dates
    fake = Faker("en_US")
    number_offset = derive_rng(root_seed, "accounts", "numbers").randrange(
        10**profile.account_number.digits
    )

    archetypes = list(profile.archetypes)
    archetype_weights = [profile.archetypes[a].share for a in archetypes]
    advisor_names = [a.name for a in profile.advisors]
    advisor_weights = [a.share for a in profile.advisors]
    status_items = list(profile.account_status)
    status_weights = [profile.account_status[s] for s in status_items]

    households: list[TruthHousehold] = []
    people: list[TruthPerson] = []
    accounts: list[TruthAccount] = []

    for index in range(n_households):
        rng = derive_rng(root_seed, "household", str(index))
        fake.seed_instance(derive_seed(root_seed, "faker", "household", str(index)))
        household_id = f"HH-{index + 1:04d}"

        archetype = _pick(rng, archetypes, archetype_weights)
        rule = profile.archetypes[archetype]
        has_children = rule.children[1] > 0

        # Birth-date range for the adults of this household.
        low_year, high_year = dates.adult_birth_years
        adult_low = date(low_year, 1, 1)
        adult_high = date(high_year, 12, 31)
        if has_children:
            adult_low = max(adult_low, date(rules.dependents_parent_birth_year_min, 1, 1))
        if rule.min_age is not None:
            adult_high = min(
                adult_high,
                date(dates.retired_birth_year_max, 12, 31),
                add_years(as_of, -rule.min_age),
            )

        address = (
            str(fake.street_address()),
            str(fake.city()),
            str(fake.state_abbr(include_territories=False)),
            str(fake.postcode()),
        )
        primary_dob = _random_date(rng, adult_low, adult_high)
        last_name = str(fake.last_name())
        members: list[TruthPerson] = []

        members.append(
            _person(
                rng,
                fake,
                person_id=_pid(len(people) + len(members)),
                household_id=household_id,
                role=HouseholdRole.PRIMARY,
                last_name=last_name,
                dob=primary_dob,
                address=address,
            )
        )
        if rule.adults == 2:
            gap = timedelta(days=round(365.25 * rules.couple_age_gap_max_years))
            spouse_dob = _random_date(
                rng,
                max(adult_low, primary_dob - gap),
                min(adult_high, primary_dob + gap),
            )
            different = rng.random() < rules.couples_with_different_surnames
            members.append(
                _person(
                    rng,
                    fake,
                    person_id=_pid(len(people) + len(members)),
                    household_id=household_id,
                    role=HouseholdRole.SPOUSE,
                    last_name=str(fake.last_name()) if different else last_name,
                    dob=spouse_dob,
                    address=address,
                )
            )
        adults = list(members)
        n_children = rng.randint(*rule.children)
        if n_children:
            youngest_parent = max(a.date_of_birth for a in adults)
            child_low = max(
                date(dates.child_birth_years[0], 1, 1),
                add_years(youngest_parent, rules.parent_child_gap_min_years),
            )
            child_high = date(dates.child_birth_years[1], 12, 31)
            child_dobs = sorted(_random_date(rng, child_low, child_high) for _ in range(n_children))
            for child_dob in child_dobs:
                members.append(
                    _person(
                        rng,
                        fake,
                        person_id=_pid(len(people) + len(members)),
                        household_id=household_id,
                        role=HouseholdRole.DEPENDENT,
                        last_name=last_name,
                        dob=child_dob,
                        address=address,
                    )
                )
        children = [m for m in members if m.household_role is HouseholdRole.DEPENDENT]

        advisor = _pick(rng, advisor_names, advisor_weights)
        earliest = max(
            add_years(as_of, -dates.client_since_years_back),
            add_years(primary_dob, dates.primary_min_age_at_client_since),
        )
        client_since = _random_date(rng, earliest, as_of)

        households.append(
            TruthHousehold(
                household_id=household_id,
                archetype=archetype,
                display_name=f"{last_name} Household",
                advisor=advisor,
                client_since=client_since,
                member_ids=tuple(m.person_id for m in members),
            )
        )

        bucket = _pick(rng, list(profile.account_counts), [b.share for b in profile.account_counts])
        n_accounts = rng.randint(*bucket.accounts)
        held: set[tuple[str, AccountType]] = set()
        for _ in range(n_accounts):
            weights: dict[AccountType, float] = {}
            for kind, type_rule in profile.account_types.items():
                if kind is AccountType.JOINT and len(adults) < 2:
                    continue
                if kind is AccountType.EDUCATION_529 and not children:
                    continue
                if kind in IRA_TYPES and all((a.person_id, kind) in held for a in adults):
                    continue
                weights[kind] = type_rule.weight
            kinds = list(weights)
            kind = _pick(rng, kinds, [weights[k] for k in kinds])

            beneficiary: TruthPerson | None = None
            if kind is AccountType.JOINT:
                owners = list(adults)
            elif kind in IRA_TYPES:
                owners = [rng.choice([a for a in adults if (a.person_id, kind) not in held])]
                held.add((owners[0].person_id, kind))
            elif kind is AccountType.EDUCATION_529:
                owners = [rng.choice(adults)]
                beneficiary = rng.choice(children)
            else:
                owners = [rng.choice(adults)]

            open_low = client_since
            for owner in owners:
                open_low = max(open_low, add_years(owner.date_of_birth, 18))
            if beneficiary is not None:
                open_low = max(open_low, beneficiary.date_of_birth)
            sequence = len(accounts)
            accounts.append(
                TruthAccount(
                    account_id=f"ACCT-{sequence + 1:06d}",
                    account_number=_account_number(profile, number_offset, sequence),
                    account_type=kind,
                    owner_ids=tuple(o.person_id for o in owners),
                    beneficiary_id=beneficiary.person_id if beneficiary else None,
                    registration_title=registration_title(kind, owners, beneficiary),
                    status=_pick(rng, status_items, status_weights),
                    open_date=_random_date(rng, open_low, as_of),
                    balance=_draw_balance(rng, profile, kind),
                    balance_as_of=as_of,
                    household_id=household_id,
                )
            )
        people.extend(members)

    securities = build_securities(profile.holdings, root_seed)
    return TruthFirm(
        root_seed=root_seed,
        as_of_date=as_of,
        profile=profile,
        households=tuple(households),
        people=tuple(people),
        accounts=tuple(accounts),
        securities=securities,
        holdings=build_holdings(profile.holdings, securities, tuple(accounts), root_seed),
    )

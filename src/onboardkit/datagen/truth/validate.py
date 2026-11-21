"""Invariants every truth firm must satisfy."""

from __future__ import annotations

import re
from decimal import Decimal

from onboardkit.datagen.truth.builder import add_years
from onboardkit.datagen.truth.model import HouseholdRole, TruthFirm
from onboardkit.datagen.truth.profile import IRA_TYPES, AccountType


class FirmValidationError(ValueError):
    """Raised when a firm breaks one or more invariants."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__(f"{len(problems)} problem(s): " + "; ".join(problems[:5]))


def find_problems(firm: TruthFirm) -> list[str]:
    problems: list[str] = []
    people = firm.people_by_id()
    households = firm.households_by_id()
    rules = firm.profile.people

    for label, ids in (
        ("person", [p.person_id for p in firm.people]),
        ("household", [h.household_id for h in firm.households]),
        ("account", [a.account_id for a in firm.accounts]),
        ("account number", [a.account_number for a in firm.accounts]),
    ):
        if len(ids) != len(set(ids)):
            problems.append(f"duplicate {label} ids")

    number_format = firm.profile.account_number
    number_pattern = re.compile(rf"^{re.escape(number_format.prefix)}\d{{{number_format.digits}}}$")

    for household in firm.households:
        members = []
        for member_id in household.member_ids:
            person = people.get(member_id)
            if person is None:
                problems.append(f"{household.household_id}: unknown member {member_id}")
            elif person.household_id != household.household_id:
                problems.append(f"{member_id}: household_id does not match its household")
            else:
                members.append(person)
        roles = [m.household_role for m in members]
        if roles.count(HouseholdRole.PRIMARY) != 1:
            problems.append(f"{household.household_id}: needs exactly one primary")
        adults = [m for m in members if m.is_adult]
        children = [m for m in members if not m.is_adult]
        rule = firm.profile.archetypes[household.archetype]
        if len(adults) != rule.adults or not rule.children[0] <= len(children) <= rule.children[1]:
            problems.append(f"{household.household_id}: members do not fit {household.archetype}")
        if household.client_since > firm.as_of_date:
            problems.append(f"{household.household_id}: client_since is after the as-of date")
        if len(adults) == 2:
            gap = abs((adults[0].date_of_birth - adults[1].date_of_birth).days)
            if gap > round(365.25 * rules.couple_age_gap_max_years) + 1:
                problems.append(f"{household.household_id}: couple age gap too large")
        for child in children:
            for parent in adults:
                limit = add_years(parent.date_of_birth, rules.parent_child_gap_min_years)
                if child.date_of_birth < limit:
                    problems.append(f"{child.person_id}: less than the minimum gap to a parent")
        if adults and household.client_since < add_years(
            adults[0].date_of_birth, firm.profile.dates.primary_min_age_at_client_since
        ):
            problems.append(f"{household.household_id}: client since before primary was old enough")

    held: set[tuple[str, AccountType]] = set()
    for account in firm.accounts:
        label = account.account_id
        account_household = households.get(account.household_id)
        if account_household is None:
            problems.append(f"{label}: unknown household")
            continue
        if not number_pattern.match(account.account_number):
            problems.append(f"{label}: account number does not match the fictional format")
        if account.balance <= 0:
            problems.append(f"{label}: balance must be positive")
        if account.balance_as_of != firm.as_of_date:
            problems.append(f"{label}: balance_as_of is not the as-of date")
        if not account_household.client_since <= account.open_date <= firm.as_of_date:
            problems.append(f"{label}: open date outside client-since..as-of")
        owners = []
        for owner_id in account.owner_ids:
            owner = people.get(owner_id)
            if owner is None or owner.household_id != account.household_id:
                problems.append(f"{label}: owner {owner_id} not in the account's household")
                continue
            owners.append(owner)
            if not owner.is_adult:
                problems.append(f"{label}: owner {owner_id} is not an adult")
            if account.open_date < add_years(owner.date_of_birth, 18):
                problems.append(f"{label}: opened before owner {owner_id} turned 18")
        expected_owners = firm.profile.account_types[account.account_type].owners
        if len(owners) != expected_owners:
            problems.append(f"{label}: {account.account_type} needs {expected_owners} owner(s)")
        if account.account_type is AccountType.JOINT and len({o.person_id for o in owners}) != 2:
            problems.append(f"{label}: joint account needs two distinct adults")
        if account.account_type in IRA_TYPES:
            key = (account.owner_ids[0], account.account_type)
            if key in held:
                problems.append(f"{label}: owner holds a second {account.account_type}")
            held.add(key)
        beneficiary = people.get(account.beneficiary_id) if account.beneficiary_id else None
        if account.account_type is AccountType.EDUCATION_529:
            if beneficiary is None or beneficiary.is_adult:
                problems.append(f"{label}: 529 needs a dependent beneficiary")
            elif (
                beneficiary.household_id != account.household_id
                or account.open_date < beneficiary.date_of_birth
            ):
                problems.append(f"{label}: 529 beneficiary not in household or born later")
        elif account.beneficiary_id is not None:
            problems.append(f"{label}: only a 529 has a beneficiary")
    problems += _holding_problems(firm)
    return problems


def _holding_problems(firm: TruthFirm) -> list[str]:
    """Holdings must belong to known accounts and securities, and add up to each balance."""
    if not firm.securities and not firm.holdings:
        return []
    problems: list[str] = []
    securities = {s.security_id: s for s in firm.securities}
    if len(securities) != len(firm.securities):
        problems.append("duplicate security ids")
    if len({s.symbol for s in firm.securities}) != len(firm.securities):
        problems.append("duplicate security symbols")
    if len({h.holding_id for h in firm.holdings}) != len(firm.holdings):
        problems.append("duplicate holding ids")
    banned = {s.upper() for s in firm.profile.holdings.forbidden_symbols}
    for security in firm.securities:
        if security.symbol.upper() in banned:
            problems.append(f"{security.security_id}: {security.symbol} is a real ticker")
    totals: dict[str, Decimal] = {}
    seen: set[tuple[str, str]] = set()
    accounts = {a.account_id: a for a in firm.accounts}
    for holding in firm.holdings:
        label = holding.holding_id
        if holding.account_id not in accounts:
            problems.append(f"{label}: unknown account {holding.account_id}")
            continue
        if holding.security_id not in securities:
            problems.append(f"{label}: unknown security {holding.security_id}")
        key = (holding.account_id, holding.security_id)
        if key in seen:
            problems.append(f"{holding.account_id}: holds {holding.security_id} twice")
        seen.add(key)
        totals[holding.account_id] = totals.get(holding.account_id, Decimal("0.00")) + holding.value
    for account in firm.accounts:
        total = totals.get(account.account_id)
        if total is None:
            problems.append(f"{account.account_id}: has no holdings")
        elif total != account.balance:
            problems.append(
                f"{account.account_id}: holdings sum to {total}, balance is {account.balance}"
            )
    return problems


def validate_firm(firm: TruthFirm) -> None:
    """Raise ``FirmValidationError`` if the firm breaks any invariant."""
    problems = find_problems(firm)
    if problems:
        raise FirmValidationError(problems)

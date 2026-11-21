"""Truth entities: the clean fictional firm.

This is internal to the generator. It is not the M1 common data model, and truth identifiers never
appear in an export.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from onboardkit.datagen.truth.profile import AccountStatus, AccountType, Archetype, FirmProfile


class HouseholdRole(StrEnum):
    PRIMARY = "primary"
    SPOUSE = "spouse"
    DEPENDENT = "dependent"


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TruthPerson(_Frozen):
    person_id: str = Field(pattern=r"^P-\d{5,}$")
    first_name: str
    middle_initial: str | None = None
    last_name: str
    suffix: str | None = None
    date_of_birth: date
    email: str | None = None
    phone: str | None = None
    address_line1: str
    address_city: str
    address_state: str
    address_postal: str
    tax_id_last4: str = Field(pattern=r"^\d{4}$")
    household_id: str
    household_role: HouseholdRole

    @property
    def is_adult(self) -> bool:
        return self.household_role is not HouseholdRole.DEPENDENT

    def full_name(self) -> str:
        parts = [self.first_name, self.middle_initial, self.last_name, self.suffix]
        return " ".join(p for p in parts if p)


class TruthHousehold(_Frozen):
    household_id: str = Field(pattern=r"^HH-\d{4,}$")
    archetype: Archetype
    display_name: str
    advisor: str
    client_since: date
    member_ids: tuple[str, ...]


class TruthAccount(_Frozen):
    account_id: str = Field(pattern=r"^ACCT-\d{6,}$")
    account_number: str
    account_type: AccountType
    owner_ids: tuple[str, ...] = Field(min_length=1)
    beneficiary_id: str | None = None
    registration_title: str
    status: AccountStatus
    open_date: date
    balance: Decimal = Field(gt=0)
    balance_as_of: date
    household_id: str

    @field_validator("balance")
    @classmethod
    def _two_places(cls, value: Decimal) -> Decimal:
        if value.as_tuple().exponent != -2:
            raise ValueError("balance must have exactly two decimal places")
        return value


class TruthFirm(_Frozen):
    root_seed: int
    as_of_date: date
    profile: FirmProfile
    households: tuple[TruthHousehold, ...]
    people: tuple[TruthPerson, ...]
    accounts: tuple[TruthAccount, ...]

    def people_by_id(self) -> dict[str, TruthPerson]:
        return {p.person_id: p for p in self.people}

    def households_by_id(self) -> dict[str, TruthHousehold]:
        return {h.household_id: h for h in self.households}

    def members_of(self, household_id: str) -> tuple[TruthPerson, ...]:
        return tuple(p for p in self.people if p.household_id == household_id)

    def accounts_of(self, household_id: str) -> tuple[TruthAccount, ...]:
        return tuple(a for a in self.accounts if a.household_id == household_id)

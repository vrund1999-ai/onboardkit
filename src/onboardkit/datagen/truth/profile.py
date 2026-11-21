"""The firm profile: every number that shapes the fictional firm, validated on load."""

from __future__ import annotations

import math
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

PROFILE_PATH = Path(__file__).with_name("firm_profile.yaml")


class Archetype(StrEnum):
    SINGLE_ADULT = "single_adult"
    COUPLE = "couple"
    COUPLE_DEPENDENTS = "couple_dependents"
    SINGLE_PARENT = "single_parent"
    RETIRED_SINGLE = "retired_single"


class AccountType(StrEnum):
    INDIVIDUAL = "individual"
    JOINT = "joint"
    TRADITIONAL_IRA = "traditional_ira"
    ROTH_IRA = "roth_ira"
    ROLLOVER_IRA = "rollover_ira"
    EDUCATION_529 = "education_529"


class AccountStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    RESTRICTED = "restricted"


IRA_TYPES = frozenset({AccountType.TRADITIONAL_IRA, AccountType.ROTH_IRA, AccountType.ROLLOVER_IRA})


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FirmInfo(_Frozen):
    name: str
    custodian: str
    crm: str
    spreadsheet: str
    as_of_date: date


class Sizes(_Frozen):
    sample: int = Field(gt=0)
    default: int = Field(gt=0)


class AdvisorShare(_Frozen):
    name: str
    share: float = Field(gt=0, le=1)


class ArchetypeRule(_Frozen):
    share: float = Field(ge=0, le=1)
    adults: Literal[1, 2]
    children: tuple[int, int]
    min_age: int | None = None

    @model_validator(mode="after")
    def _children_range(self) -> ArchetypeRule:
        low, high = self.children
        if not 0 <= low <= high:
            raise ValueError("children must be [low, high] with 0 <= low <= high")
        return self


class PeopleRules(_Frozen):
    couple_age_gap_max_years: int = Field(ge=0)
    parent_child_gap_min_years: int = Field(ge=0)
    couples_with_different_surnames: float = Field(ge=0, le=1)
    dependents_parent_birth_year_min: int


class AccountCountBucket(_Frozen):
    accounts: tuple[int, int]
    share: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _range(self) -> AccountCountBucket:
        low, high = self.accounts
        if not 1 <= low <= high:
            raise ValueError("accounts must be [low, high] with 1 <= low <= high")
        return self


class AccountTypeRule(_Frozen):
    weight: int = Field(gt=0)
    owners: Literal[1, 2]
    needs_child_beneficiary: bool = False


class AccountNumberFormat(_Frozen):
    prefix: str = Field(min_length=1)
    digits: int = Field(ge=4, le=12)


class BalanceRules(_Frozen):
    distribution: Literal["lognormal"]
    median: int = Field(gt=0)
    p90: int = Field(gt=0)
    min: int = Field(gt=0)
    max: int = Field(gt=0)
    type_scale: dict[AccountType, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _ordering(self) -> BalanceRules:
        if not self.min < self.median < self.p90 < self.max:
            raise ValueError("balances need min < median < p90 < max")
        if any(scale <= 0 for scale in self.type_scale.values()):
            raise ValueError("type_scale values must be positive")
        return self

    @property
    def sigma(self) -> float:
        """Log-normal sigma implied by the median and 90th percentile (z90 = 1.2816)."""
        return math.log(self.p90 / self.median) / 1.2815515655446004


class DateRules(_Frozen):
    client_since_years_back: int = Field(gt=0)
    primary_min_age_at_client_since: int = Field(ge=0)
    adult_birth_years: tuple[int, int]
    retired_birth_year_max: int
    child_birth_years: tuple[int, int]


def _sums_to_one(label: str, values: list[float]) -> None:
    if not math.isclose(sum(values), 1.0, abs_tol=1e-9):
        raise ValueError(f"{label} shares must sum to 1, got {sum(values)}")


class FirmProfile(_Frozen):
    firm: FirmInfo
    sizes: Sizes
    advisors: tuple[AdvisorShare, ...]
    archetypes: dict[Archetype, ArchetypeRule]
    people: PeopleRules
    account_counts: tuple[AccountCountBucket, ...]
    account_types: dict[AccountType, AccountTypeRule]
    account_status: dict[AccountStatus, float]
    account_number: AccountNumberFormat
    balances: BalanceRules
    dates: DateRules

    @model_validator(mode="after")
    def _consistent(self) -> FirmProfile:
        _sums_to_one("advisor", [a.share for a in self.advisors])
        _sums_to_one("archetype", [a.share for a in self.archetypes.values()])
        _sums_to_one("account count", [b.share for b in self.account_counts])
        _sums_to_one("account status", list(self.account_status.values()))
        if len({a.name for a in self.advisors}) != len(self.advisors):
            raise ValueError("advisor names must be unique")
        if set(self.archetypes) != set(Archetype):
            raise ValueError("every archetype needs a rule")
        if set(self.account_types) != set(AccountType):
            raise ValueError("every account type needs a rule")
        if set(self.account_status) != set(AccountStatus):
            raise ValueError("every account status needs a share")
        for kind, rule in self.account_types.items():
            expected = 2 if kind is AccountType.JOINT else 1
            if rule.owners != expected:
                raise ValueError(f"{kind} must have {expected} owner(s)")
            if rule.needs_child_beneficiary != (kind is AccountType.EDUCATION_529):
                raise ValueError("only education_529 needs a child beneficiary")
        return self


def load_profile(path: Path = PROFILE_PATH) -> FirmProfile:
    with path.open(encoding="utf-8") as handle:
        return FirmProfile.model_validate(yaml.safe_load(handle))

from datetime import date
from decimal import Decimal

import pytest

from onboardkit.datagen.truth.builder import build_firm
from onboardkit.datagen.truth.model import TruthFirm
from onboardkit.datagen.truth.profile import AccountType, load_profile
from onboardkit.datagen.truth.validate import FirmValidationError, find_problems, validate_firm

FIRM = build_firm(load_profile(), 60, 11)


def _replace_account(index: int, **update: object) -> TruthFirm:
    accounts = list(FIRM.accounts)
    accounts[index] = accounts[index].model_copy(update=update)
    return FIRM.model_copy(update={"accounts": tuple(accounts)})


def _first(kind: AccountType) -> int:
    return next(i for i, a in enumerate(FIRM.accounts) if a.account_type is kind)


def test_clean_firm_has_no_problems() -> None:
    assert find_problems(FIRM) == []
    validate_firm(FIRM)


def test_zero_balance_is_reported() -> None:
    firm = _replace_account(0, balance=Decimal("0.00"))
    assert any("balance must be positive" in p for p in find_problems(firm))


def test_wrong_balance_date_is_reported() -> None:
    firm = _replace_account(0, balance_as_of=date(2020, 1, 1))
    assert any("balance_as_of" in p for p in find_problems(firm))


def test_duplicate_account_number_is_reported() -> None:
    accounts = list(FIRM.accounts)
    accounts[1] = accounts[1].model_copy(update={"account_number": accounts[0].account_number})
    firm = FIRM.model_copy(update={"accounts": tuple(accounts)})
    assert any("duplicate account number" in p for p in find_problems(firm))


def test_joint_with_one_owner_is_reported() -> None:
    index = _first(AccountType.JOINT)
    owner = FIRM.accounts[index].owner_ids[0]
    firm = _replace_account(index, owner_ids=(owner,))
    assert any("needs 2 owner" in p for p in find_problems(firm))


def test_owner_from_another_household_is_reported() -> None:
    account = FIRM.accounts[0]
    stranger = next(p for p in FIRM.people if p.household_id != account.household_id)
    firm = _replace_account(0, owner_ids=(stranger.person_id,))
    assert any("not in the account's household" in p for p in find_problems(firm))


def test_529_with_adult_beneficiary_is_reported() -> None:
    index = _first(AccountType.EDUCATION_529)
    owner = FIRM.accounts[index].owner_ids[0]
    firm = _replace_account(index, beneficiary_id=owner)
    assert any("dependent beneficiary" in p for p in find_problems(firm))


def test_validate_firm_raises_with_all_problems() -> None:
    firm = _replace_account(0, balance=Decimal("0.00"))
    with pytest.raises(FirmValidationError) as info:
        validate_firm(firm)
    assert info.value.problems

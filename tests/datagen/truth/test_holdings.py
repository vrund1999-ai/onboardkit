from collections import defaultdict
from decimal import Decimal

import pytest

from onboardkit.datagen.truth.builder import build_firm
from onboardkit.datagen.truth.model import TruthFirm, TruthHolding
from onboardkit.datagen.truth.profile import (
    AccountStatus,
    AssetClass,
    FirmProfile,
    load_profile,
)
from onboardkit.datagen.truth.validate import find_problems

PROFILE = load_profile()
FIRM = build_firm(PROFILE, 40, 11)


def _with_holdings(holdings: list[TruthHolding]) -> TruthFirm:
    return FIRM.model_copy(update={"holdings": tuple(holdings)})


@pytest.mark.parametrize("seed", [1, 7, 42, 2024])
def test_holdings_sum_exactly_to_every_balance(seed: int) -> None:
    firm = build_firm(PROFILE, 25, seed)
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for holding in firm.holdings:
        totals[holding.account_id] += holding.value
    assert {a.account_id for a in firm.accounts} == set(totals)
    assert all(totals[a.account_id] == a.balance for a in firm.accounts)
    assert find_problems(firm) == []


def test_every_account_has_holdings_and_closed_accounts_hold_only_cash() -> None:
    cash = FIRM.securities[0]
    assert cash.asset_class is AssetClass.CASH
    for account in FIRM.accounts:
        held = FIRM.holdings_of(account.account_id)
        assert held
        if account.status is AccountStatus.CLOSED:
            assert [h.security_id for h in held] == [cash.security_id]
        assert len({h.security_id for h in held}) == len(held)


def test_quantities_and_values_are_positive_with_fixed_places() -> None:
    for holding in FIRM.holdings:
        assert holding.quantity > 0
        assert holding.value > 0
        assert holding.quantity.as_tuple().exponent == -4
        assert holding.value.as_tuple().exponent == -2


def test_the_security_master_is_small_fictional_and_unique() -> None:
    securities = FIRM.securities
    assert len(securities) == PROFILE.holdings.security_count + 1
    assert len({s.symbol for s in securities}) == len(securities)
    assert len({s.name for s in securities}) == len(securities)
    banned = {s.upper() for s in PROFILE.holdings.forbidden_symbols}
    assert not banned & {s.symbol for s in securities}
    classes = {s.asset_class for s in securities}
    assert classes == set(AssetClass)


def test_the_security_master_does_not_depend_on_firm_size() -> None:
    assert build_firm(PROFILE, 5, 11).securities == FIRM.securities


def test_a_small_firm_is_a_prefix_of_a_large_one() -> None:
    small = build_firm(PROFILE, 8, 11)
    assert FIRM.holdings[: len(small.holdings)] == small.holdings


def test_the_same_seed_gives_identical_holdings_and_another_seed_differs() -> None:
    assert build_firm(PROFILE, 40, 11).holdings == FIRM.holdings
    assert build_firm(PROFILE, 40, 12).holdings != FIRM.holdings


def test_small_accounts_hold_fewer_positions() -> None:
    rules = PROFILE.holdings
    for account in FIRM.accounts:
        invested = [
            h
            for h in FIRM.holdings_of(account.account_id)
            if h.security_id != FIRM.securities[0].security_id
        ]
        limit = rules.small_account_positions[1]
        if account.balance < rules.small_account_threshold:
            assert len(invested) <= limit
        assert len(invested) <= rules.positions[1]


def test_an_altered_holding_value_is_reported_with_the_account() -> None:
    first = FIRM.holdings[0]
    altered = [first.model_copy(update={"value": first.value + Decimal("0.01")})]
    firm = _with_holdings(altered + list(FIRM.holdings[1:]))
    assert any(p.startswith(f"{first.account_id}: holdings sum to") for p in find_problems(firm))


def test_an_unknown_security_and_an_unknown_account_are_reported() -> None:
    first = FIRM.holdings[0]
    bad_security = first.model_copy(update={"security_id": "SEC-999"})
    bad_account = first.model_copy(update={"account_id": "ACCT-999999"})
    rest = list(FIRM.holdings[1:])
    assert any(
        "unknown security" in p for p in find_problems(_with_holdings([bad_security, *rest]))
    )
    assert any("unknown account" in p for p in find_problems(_with_holdings([bad_account, *rest])))


def test_a_repeated_security_in_an_account_is_reported() -> None:
    first = FIRM.holdings[0]
    twin = first.model_copy(update={"holding_id": "HOLD-999999"})
    problems = find_problems(_with_holdings([*FIRM.holdings, twin]))
    assert any("twice" in p for p in problems)


def test_an_account_without_holdings_is_reported() -> None:
    gone = FIRM.accounts[0].account_id
    firm = _with_holdings([h for h in FIRM.holdings if h.account_id != gone])
    assert f"{gone}: has no holdings" in find_problems(firm)


def test_a_famous_real_ticker_is_reported() -> None:
    securities = list(FIRM.securities)
    securities[1] = securities[1].model_copy(update={"symbol": "AAPL"})
    firm = FIRM.model_copy(update={"securities": tuple(securities)})
    assert any("is a real ticker" in p for p in find_problems(firm))


def test_a_firm_without_holdings_still_validates() -> None:
    legacy = FIRM.model_copy(update={"securities": (), "holdings": ()})
    assert find_problems(legacy) == []


def test_the_profile_rejects_bad_holdings_rules() -> None:
    data = PROFILE.model_dump(mode="json")
    data["holdings"]["class_shares"] = {"equity": 0.5, "fixed_income": 0.2, "fund": 0.2}
    with pytest.raises(ValueError, match="sum to 1"):
        FirmProfile.model_validate(data)
    data = PROFILE.model_dump(mode="json")
    data["holdings"]["cash_share"] = [0.5, 0.1]
    with pytest.raises(ValueError, match="cash_share"):
        FirmProfile.model_validate(data)


@pytest.mark.parametrize("balance", ["2500.00", "10000000.00"])
def test_extreme_balances_still_reconcile(balance: str) -> None:
    from onboardkit.datagen.truth.holdings import build_holdings

    account = FIRM.accounts[0].model_copy(
        update={"balance": Decimal(balance), "status": AccountStatus.OPEN}
    )
    holdings = build_holdings(PROFILE.holdings, FIRM.securities, (account,), 11)
    assert sum((h.value for h in holdings), Decimal("0.00")) == Decimal(balance)

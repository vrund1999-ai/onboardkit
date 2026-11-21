"""Securities and holdings for the fictional firm.

Everything here draws from its own named streams (``holdings``/...), so adding holdings changes
no existing generated data. The security master does not depend on the number of households, and
each account's holdings depend only on that account, so a small firm is a prefix of a large one.
"""

from __future__ import annotations

import random
import string
from decimal import ROUND_HALF_EVEN, Decimal

from onboardkit.datagen.rng import derive_rng
from onboardkit.datagen.truth.model import TruthAccount, TruthHolding, TruthSecurity
from onboardkit.datagen.truth.profile import (
    INVESTED_CLASSES,
    AccountStatus,
    AssetClass,
    HoldingsRules,
)

CASH_SYMBOL = "CASH"
_CENT = Decimal("0.01")
_PRICE = Decimal("0.0001")
_MINIMUM_QUANTITY = Decimal("0.0001")


def _decimal(value: float) -> Decimal:
    return Decimal(repr(value))


def _class_counts(rules: HoldingsRules) -> dict[AssetClass, int]:
    """How many securities of each class; any rounding remainder goes to equities."""
    counts = {
        cls: round(rules.security_count * rules.class_shares[cls]) for cls in INVESTED_CLASSES
    }
    counts[AssetClass.EQUITY] += rules.security_count - sum(counts.values())
    return counts


def _symbol(rng: random.Random, asset_class: AssetClass, taken: set[str], banned: set[str]) -> str:
    """An invented identifier, unique in the master and never a famous real ticker."""
    while True:
        match asset_class:
            case AssetClass.EQUITY:
                symbol = "".join(rng.choices(string.ascii_uppercase, k=4))
            case AssetClass.FUND:
                symbol = "".join(rng.choices(string.ascii_uppercase, k=4)) + "X"
            case _:
                symbol = (
                    "".join(rng.choices(string.ascii_uppercase, k=2))
                    + f"{rng.randint(0, 9999):04d}"
                )
        if symbol not in taken and symbol not in banned:
            return symbol


def _name(rng: random.Random, rules: HoldingsRules, asset_class: AssetClass) -> str:
    words = rules.name_words
    first = rng.choice(words.first)
    match asset_class:
        case AssetClass.EQUITY:
            return f"{first} {rng.choice(words.second)} {rng.choice(words.equity_suffixes)}"
        case AssetClass.FUND:
            return f"{first} {rng.choice(words.second)} {rng.choice(words.fund_types)}"
        case _:
            coupon = Decimal(rng.randint(8, 24)) / 4
            return f"{first} Municipal Bond {coupon}% {rng.randint(2028, 2040)}"


def build_securities(rules: HoldingsRules, root_seed: int) -> tuple[TruthSecurity, ...]:
    """The security master: cash first, then equities, bonds and funds in a fixed order."""
    rng = derive_rng(root_seed, "holdings", "securities")
    banned = {s.upper() for s in rules.forbidden_symbols}
    securities = [
        TruthSecurity(
            security_id="SEC-001",
            symbol=CASH_SYMBOL,
            name="Cash and Money Market",
            asset_class=AssetClass.CASH,
            price=Decimal("1.0000"),
        )
    ]
    taken = {CASH_SYMBOL}
    names: set[str] = set()
    counts = _class_counts(rules)
    for asset_class in INVESTED_CLASSES:
        low, high = rules.price_ranges[asset_class]
        for _ in range(counts[asset_class]):
            name = _name(rng, rules, asset_class)
            while name in names:
                name = _name(rng, rules, asset_class)
            names.add(name)
            symbol = _symbol(rng, asset_class, taken, banned)
            taken.add(symbol)
            securities.append(
                TruthSecurity(
                    security_id=f"SEC-{len(securities) + 1:03d}",
                    symbol=symbol,
                    name=name,
                    asset_class=asset_class,
                    price=_decimal(rng.uniform(low, high)).quantize(_PRICE, ROUND_HALF_EVEN),
                )
            )
    return tuple(securities)


def _choose_securities(
    rng: random.Random,
    rules: HoldingsRules,
    account: TruthAccount,
    by_class: dict[AssetClass, list[TruthSecurity]],
    count: int,
) -> list[TruthSecurity]:
    mix = rules.class_mix[account.account_type]
    classes = list(INVESTED_CLASSES)
    weights = [mix[c] for c in classes]
    everything = [s for c in classes for s in by_class[c]]
    chosen: list[TruthSecurity] = []
    for _ in range(count):
        asset_class = rng.choices(classes, weights=weights, k=1)[0]
        pool = [s for s in by_class[asset_class] if s not in chosen] or [
            s for s in everything if s not in chosen
        ]
        chosen.append(rng.choice(pool))
    return chosen


def _account_holdings(
    rules: HoldingsRules,
    securities: tuple[TruthSecurity, ...],
    account: TruthAccount,
    root_seed: int,
    first_number: int,
) -> list[TruthHolding]:
    cash = securities[0]
    balance = account.balance

    def holding(
        number: int, security: TruthSecurity, value: Decimal, quantity: Decimal
    ) -> TruthHolding:
        return TruthHolding(
            holding_id=f"HOLD-{number:06d}",
            account_id=account.account_id,
            security_id=security.security_id,
            quantity=quantity,
            value=value,
        )

    if account.status is AccountStatus.CLOSED:
        return [holding(first_number, cash, balance, balance.quantize(_PRICE))]

    rng = derive_rng(root_seed, "holdings", "account", account.account_id)
    small = balance < rules.small_account_threshold
    low, high = rules.small_account_positions if small else rules.positions
    by_class = {c: [s for s in securities if s.asset_class is c] for c in INVESTED_CLASSES}
    chosen = _choose_securities(rng, rules, account, by_class, rng.randint(low, high))
    chosen.sort(key=lambda s: s.security_id)

    cash_fraction = _decimal(rng.uniform(*rules.cash_share))
    invested = balance * (1 - cash_fraction)
    raw = [0.05 + rng.random() ** 2 for _ in chosen]
    total = sum(raw)

    entries: list[tuple[TruthSecurity, Decimal, Decimal]] = []
    for security, weight in zip(chosen, raw, strict=True):
        target = (invested * _decimal(weight / total)).quantize(_CENT, ROUND_HALF_EVEN)
        quantity = max(
            (target / security.price).quantize(_PRICE, ROUND_HALF_EVEN), _MINIMUM_QUANTITY
        )
        entries.append((security, quantity, (quantity * security.price).quantize(_CENT)))

    # The cash holding absorbs the remainder, so the holdings sum to the balance to the cent.
    cash_value = balance - sum((value for _, _, value in entries), Decimal("0.00"))
    if cash_value <= 0:
        raise ValueError(f"{account.account_id}: holdings leave no room for cash")
    entries.insert(0, (cash, cash_value.quantize(_PRICE), cash_value))
    return [
        holding(first_number + offset, security, value, quantity)
        for offset, (security, quantity, value) in enumerate(entries)
    ]


def build_holdings(
    rules: HoldingsRules,
    securities: tuple[TruthSecurity, ...],
    accounts: tuple[TruthAccount, ...],
    root_seed: int,
) -> tuple[TruthHolding, ...]:
    """Holdings for every account, numbered in account order."""
    holdings: list[TruthHolding] = []
    for account in accounts:
        holdings.extend(_account_holdings(rules, securities, account, root_seed, len(holdings) + 1))
    return tuple(holdings)

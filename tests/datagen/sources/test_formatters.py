from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from onboardkit.datagen.sources.formatters import FORMATTERS, NameParts, apply_formatter

NAME = NameParts(first="John", middle="A", last="Smith", suffix="Jr.")
PLAIN_NAME = NameParts(first="Jane", last="Doe")


@pytest.mark.parametrize(
    ("value", "options", "expected"),
    [
        (date(2025, 12, 31), {}, "2025-12-31"),
        (date(2025, 3, 4), {"pattern": "%m/%d/%Y"}, "03/04/2025"),
        (date(2025, 3, 4), {"pattern": "%d %b %Y"}, "04 Mar 2025"),
        (date(2024, 2, 29), {"pattern": "%m/%d/%y"}, "02/29/24"),
        (None, {}, ""),
    ],
)
def test_date(value: Any, options: dict[str, Any], expected: str) -> None:
    assert apply_formatter("date", value, options) == expected


def test_date_rejects_text() -> None:
    with pytest.raises(TypeError):
        apply_formatter("date", "2025-12-31")


@pytest.mark.parametrize(
    ("value", "style", "expected"),
    [
        (Decimal("1234.5"), "plain", "1234.50"),
        (Decimal("0"), "plain", "0.00"),
        (Decimal("-1234.5"), "plain", "-1234.50"),
        (Decimal("1234567.891"), "plain", "1234567.89"),
        (Decimal("1234.5"), "dollar_commas", "$1,234.50"),
        (Decimal("0"), "dollar_commas", "$0.00"),
        (Decimal("-1234.5"), "dollar_commas", "-$1,234.50"),
        (Decimal("1234.5"), "parens_negative", "1,234.50"),
        (Decimal("-1234.5"), "parens_negative", "(1,234.50)"),
        (Decimal("0"), "parens_negative", "0.00"),
        (Decimal("0.005"), "plain", "0.00"),
        (Decimal("0.015"), "plain", "0.02"),
        (None, "plain", ""),
    ],
)
def test_money(value: Decimal | None, style: str, expected: str) -> None:
    assert apply_formatter("money", value, {"style": style}) == expected


def test_money_number_style_returns_quantized_decimal() -> None:
    result = apply_formatter("money", Decimal("12.3"), {"style": "number"})
    assert result == Decimal("12.30")
    assert isinstance(result, Decimal)


def test_money_never_accepts_float() -> None:
    with pytest.raises(TypeError, match="float"):
        apply_formatter("money", 12.5)
    with pytest.raises(TypeError):
        apply_formatter("money", "12.50")


def test_money_unknown_style() -> None:
    with pytest.raises(ValueError, match="style"):
        apply_formatter("money", Decimal(1), {"style": "euros"})


@pytest.mark.parametrize(
    ("name", "formatter", "options", "expected"),
    [
        (NAME, "name_first_last", {}, "John A Smith Jr."),
        (NAME, "name_last_first", {}, "Smith, John A Jr."),
        (NAME, "name_last_first", {"upper": True}, "SMITH, JOHN A JR."),
        (PLAIN_NAME, "name_first_last", {}, "Jane Doe"),
        (PLAIN_NAME, "name_last_first", {}, "Doe, Jane"),
        (PLAIN_NAME, "name_first_last", {"upper": True}, "JANE DOE"),
        (None, "name_first_last", {}, ""),
        (None, "name_last_first", {}, ""),
    ],
)
def test_names(name: Any, formatter: str, options: dict[str, Any], expected: str) -> None:
    assert apply_formatter(formatter, name, options) == expected


def test_name_formatter_rejects_text() -> None:
    with pytest.raises(TypeError, match="NameParts"):
        apply_formatter("name_first_last", "John Smith")


@pytest.mark.parametrize(
    ("value", "style", "expected"),
    [
        ("(905) 555-0157", "parens", "(905) 555-0157"),
        ("(905) 555-0157", "dashes", "905-555-0157"),
        ("(905) 555-0157", "dots", "905.555.0157"),
        ("(905) 555-0157", "digits", "9055550157"),
        ("(905) 555-0157", "e164", "+19055550157"),
        ("1-905-555-0157", "dashes", "905-555-0157"),
        ("555-0157", "dashes", "555-0157"),
        ("", "dashes", ""),
        (None, "dashes", ""),
    ],
)
def test_phone(value: str | None, style: str, expected: str) -> None:
    assert apply_formatter("phone", value, {"style": style}) == expected


def test_phone_unknown_style() -> None:
    with pytest.raises(ValueError, match="style"):
        apply_formatter("phone", "9055550157", {"style": "morse"})


@pytest.mark.parametrize(
    ("value", "options", "expected"),
    [
        (True, {}, "Y"),
        (False, {}, "N"),
        (True, {"true": "TRUE", "false": "FALSE"}, "TRUE"),
        (False, {"true": "TRUE", "false": "FALSE"}, "FALSE"),
        (None, {}, ""),
    ],
)
def test_boolean(value: bool | None, options: dict[str, Any], expected: str) -> None:
    assert apply_formatter("boolean", value, options) == expected


def test_boolean_rejects_text() -> None:
    with pytest.raises(TypeError):
        apply_formatter("boolean", "yes")


@pytest.mark.parametrize(
    ("formatter", "value", "expected"),
    [
        ("upper", "Smith", "SMITH"),
        ("upper", "", ""),
        ("upper", None, ""),
        ("passthrough", "abc", "abc"),
        ("passthrough", 0, "0"),
        ("passthrough", None, ""),
        ("passthrough", date(2025, 1, 2), "2025-01-02"),
    ],
)
def test_upper_and_passthrough(formatter: str, value: Any, expected: str) -> None:
    assert apply_formatter(formatter, value) == expected


def test_passthrough_rejects_float() -> None:
    with pytest.raises(TypeError, match="float"):
        apply_formatter("passthrough", 1.5)


def test_every_registered_formatter_handles_none() -> None:
    for name in FORMATTERS:
        assert apply_formatter(name, None) == ""


def test_unknown_formatter_lists_available() -> None:
    with pytest.raises(ValueError, match="available"):
        apply_formatter("shout", "x")

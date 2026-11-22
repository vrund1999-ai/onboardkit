"""Pure value formatters: ``(value, options) -> text`` (or a ``Decimal`` for numeric cells).

``None`` always formats as an empty string, except where a formatter says otherwise. Money is
always ``Decimal``; a ``float`` is a bug and raises.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

Options = Mapping[str, Any]
Formatted = str | Decimal | date
Formatter = Callable[[Any, Options], Formatted]

_CENT = Decimal("0.01")


@dataclass(frozen=True)
class NameParts:
    """A person's name in parts, so formatters can write it in any order."""

    first: str
    last: str
    middle: str | None = None
    suffix: str | None = None


def format_date(value: Any, options: Options) -> Formatted:
    """``pattern`` is a strftime pattern (default ISO)."""
    if value is None:
        return ""
    if not isinstance(value, date):
        raise TypeError(f"date formatter needs a date, got {type(value).__name__}")
    return value.strftime(str(options.get("pattern", "%Y-%m-%d")))


def format_excel_date(value: Any, options: Options) -> Formatted:
    """Keep a real date so a spreadsheet cell can hold a date value; blank when missing."""
    if value is None:
        return ""
    if not isinstance(value, date):
        raise TypeError(f"excel_date formatter needs a date, got {type(value).__name__}")
    return value


def format_money(value: Any, options: Options) -> Formatted:
    """``style``: ``plain`` (1234.50), ``commas`` (1,234.50), ``dollar_commas`` ($1,234.50),
    ``parens_negative`` (1,234.50 and (1,234.50)), or ``number`` (a quantized ``Decimal``)."""
    if value is None:
        return ""
    if isinstance(value, float):
        raise TypeError("money must be a Decimal, never a float")
    if not isinstance(value, Decimal):
        raise TypeError(f"money formatter needs a Decimal, got {type(value).__name__}")
    amount = value.quantize(_CENT, rounding=ROUND_HALF_EVEN)
    style = options.get("style", "plain")
    negative = amount < 0
    magnitude = abs(amount)
    if style == "number":
        return amount
    if style == "plain":
        return f"{amount:.2f}"
    if style == "commas":
        return f"{'-' if negative else ''}{magnitude:,.2f}"
    if style == "dollar_commas":
        return f"{'-' if negative else ''}${magnitude:,.2f}"
    if style == "parens_negative":
        return f"({magnitude:,.2f})" if negative else f"{magnitude:,.2f}"
    raise ValueError(f"unknown money style {style!r}")


def format_decimal(value: Any, options: Options) -> Formatted:
    """A non-money number: ``places`` decimals (default 4) and ``commas`` for thousands."""
    if value is None:
        return ""
    if isinstance(value, float):
        raise TypeError("decimal must be a Decimal, never a float")
    if not isinstance(value, Decimal):
        raise TypeError(f"decimal formatter needs a Decimal, got {type(value).__name__}")
    places = int(options.get("places", 4))
    amount = value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)
    return f"{amount:,.{places}f}" if options.get("commas") else f"{amount:.{places}f}"


def _select(value: Any, options: Options) -> Any:
    """Pick ``options["index"]`` from a list of values (blank when out of range)."""
    if isinstance(value, list | tuple):
        index = int(options.get("index", 0))
        return value[index] if index < len(value) else None
    return value


def _name_parts(value: Any) -> tuple[str, str | None, str, str | None]:
    if isinstance(value, NameParts):
        return value.first, value.middle, value.last, value.suffix
    raise TypeError(f"name formatter needs NameParts, got {type(value).__name__}")


def _apply_case(text: str, options: Options) -> str:
    return text.upper() if options.get("upper") else text


def format_name_first_last(value: Any, options: Options) -> Formatted:
    """``John A Smith Jr.``; ``upper: true`` upper-cases; ``index`` picks from a list."""
    value = _select(value, options)
    if value is None:
        return ""
    first, middle, last, suffix = _name_parts(value)
    return _apply_case(" ".join(p for p in (first, middle, last, suffix) if p), options)


def format_name_last_first(value: Any, options: Options) -> Formatted:
    """``Smith, John A Jr.``; ``upper: true`` upper-cases; ``index`` picks from a list."""
    value = _select(value, options)
    if value is None:
        return ""
    first, middle, last, suffix = _name_parts(value)
    given = " ".join(p for p in (first, middle, suffix) if p)
    return _apply_case(f"{last}, {given}", options)


_PHONE_STYLES = {
    "parens": "({a}) {b}-{c}",
    "dashes": "{a}-{b}-{c}",
    "dots": "{a}.{b}.{c}",
    "digits": "{a}{b}{c}",
    "e164": "+1{a}{b}{c}",
}


def format_phone(value: Any, options: Options) -> Formatted:
    """``style``: parens, dashes, dots, digits, or e164. Unparseable input is returned as is."""
    if value is None:
        return ""
    style = options.get("style", "parens")
    if style not in _PHONE_STYLES:
        raise ValueError(f"unknown phone style {style!r}; available: {sorted(_PHONE_STYLES)}")
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return str(value)
    return _PHONE_STYLES[style].format(a=digits[:3], b=digits[3:6], c=digits[6:])


def format_boolean(value: Any, options: Options) -> Formatted:
    """``true`` and ``false`` give the labels (default ``Y`` and ``N``)."""
    if value is None:
        return ""
    if not isinstance(value, bool):
        raise TypeError(f"boolean formatter needs a bool, got {type(value).__name__}")
    return str(options.get("true", "Y")) if value else str(options.get("false", "N"))


def format_map(value: Any, options: Options) -> Formatted:
    """Translate through ``mapping`` (keys compared as text); unmapped values are an error."""
    if value is None:
        return ""
    mapping: Mapping[str, str] = options["mapping"]
    key = str(value)
    if key not in mapping:
        raise ValueError(f"value {key!r} is not in the mapping {sorted(mapping)}")
    return mapping[key]


def format_upper(value: Any, options: Options) -> Formatted:
    return "" if value is None else str(value).upper()


def format_passthrough(value: Any, options: Options) -> Formatted:
    if value is None:
        return ""
    if isinstance(value, float):
        raise TypeError("floats are not written; use Decimal and the money formatter")
    return value if isinstance(value, Decimal) else str(value)


FORMATTERS: dict[str, Formatter] = {
    "date": format_date,
    "decimal": format_decimal,
    "excel_date": format_excel_date,
    "money": format_money,
    "name_first_last": format_name_first_last,
    "name_last_first": format_name_last_first,
    "phone": format_phone,
    "boolean": format_boolean,
    "map": format_map,
    "upper": format_upper,
    "passthrough": format_passthrough,
}


def apply_formatter(name: str, value: Any, options: Options | None = None) -> Formatted:
    try:
        formatter = FORMATTERS[name]
    except KeyError:
        raise ValueError(f"unknown formatter {name!r}; available: {sorted(FORMATTERS)}") from None
    return formatter(value, options or {})

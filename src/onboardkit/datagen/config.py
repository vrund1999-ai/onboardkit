"""Dataset configuration: one validated object that fully describes a dataset.

Nothing in this module reads environment variables or the clock. Every input that influences the
generated data is a field of ``DatasetConfig``, so equal configs always produce identical data.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

PRESETS_DIR = Path(__file__).with_name("presets")

SIZES: dict[str, int] = {"sample": 15, "default": 300}
MAX_HOUSEHOLDS = 5000
DEFAULT_AS_OF_DATE = date(2025, 12, 31)
FIRM_PROFILES = ("lantern_ridge",)

# Placeholder until the mess registry (E3-S1) exists; E3-S2 replaces this with registered types.
MESS_TYPE_NAMES = ("names", "households", "formats", "balances")

_HASH_FLOAT_PLACES = 6


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SizeConfig(_Frozen):
    households: int = Field(ge=1, le=MAX_HOUSEHOLDS)


class MessSetting(_Frozen):
    enabled: bool = False
    intensity: float = Field(default=0.0, ge=0.0, le=1.0)


class MessConfig(RootModel[dict[str, MessSetting]]):
    """Mess settings keyed by mess type name. Missing types are disabled."""

    model_config = ConfigDict(frozen=True)

    @field_validator("root")
    @classmethod
    def _known_types(cls, value: dict[str, MessSetting]) -> dict[str, MessSetting]:
        unknown = sorted(set(value) - set(MESS_TYPE_NAMES))
        if unknown:
            raise ValueError(f"unknown mess type(s) {unknown}; valid: {list(MESS_TYPE_NAMES)}")
        return value

    @property
    def settings(self) -> dict[str, MessSetting]:
        return self.root


class CustodianCoverage(_Frozen):
    accounts: float = Field(default=1.0, ge=0.0, le=1.0)


class CrmCoverage(_Frozen):
    persons: float = Field(default=1.0, ge=0.0, le=1.0)
    account_links: float = Field(default=1.0, ge=0.0, le=1.0)


class BookCoverage(_Frozen):
    households: float = Field(default=1.0, ge=0.0, le=1.0)
    accounts: float = Field(default=1.0, ge=0.0, le=1.0)
    stale_extra_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class CoverageConfig(_Frozen):
    """Share of rows each source keeps. The selection logic arrives with E2-S5."""

    custodian: CustodianCoverage = Field(default_factory=CustodianCoverage)
    crm: CrmCoverage = Field(default_factory=CrmCoverage)
    book_of_business: BookCoverage = Field(default_factory=BookCoverage)


class BookOfBusinessConfig(_Frozen):
    """Habits of the hand-kept spreadsheet that exist even in a "clean" world.

    ``inherent_drift`` is the largest fraction a hand-typed balance may be off by, and
    ``round_to`` is the amount balances are rounded to. Larger, deliberate mismatches belong to
    the balances mess type.
    """

    inherent_drift: float = Field(default=0.12, ge=0.0, le=0.5)
    round_to: float = Field(default=100.0, gt=0.0)


class DatasetConfig(_Frozen):
    preset: str | None = None  # informational: resolved before use, excluded from the hash
    size: SizeConfig
    seed: int = Field(ge=0, le=2**63 - 1)
    as_of_date: date = DEFAULT_AS_OF_DATE
    firm_profile: str = "lantern_ridge"
    coverage: CoverageConfig
    book_of_business: BookOfBusinessConfig = Field(default_factory=BookOfBusinessConfig)
    mess: MessConfig

    @model_validator(mode="after")
    def _known_profile(self) -> DatasetConfig:
        if self.firm_profile not in FIRM_PROFILES:
            raise ValueError(f"unknown firm_profile {self.firm_profile!r}; valid: {FIRM_PROFILES}")
        return self


# --- loading -------------------------------------------------------------------------------


def available_presets() -> list[str]:
    return sorted(path.stem for path in PRESETS_DIR.glob("*.yaml"))


def load_preset(name: str) -> dict[str, Any]:
    path = PRESETS_DIR / f"{name}.yaml"
    if not path.is_file():
        raise ValueError(f"unknown preset {name!r}; available: {available_presets()}")
    with path.open(encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle)
    return data


def load_config(path: Path) -> DatasetConfig:
    """Load a complete dataset configuration from YAML. Unknown keys are an error."""
    with path.open(encoding="utf-8") as handle:
        return DatasetConfig.model_validate(yaml.safe_load(handle))


def _deep_merge(base: dict[str, Any], extra: Mapping[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def households_for(size: str | int) -> int:
    """Resolve ``sample``, ``default``, or an explicit household count."""
    if isinstance(size, str):
        if size in SIZES:
            return SIZES[size]
        if size.isdigit():
            return int(size)
        raise ValueError(f"unknown size {size!r}; use one of {list(SIZES)} or a number")
    return size


def resolve_config(
    preset: str,
    size: str | int,
    seed: int,
    overrides: Mapping[str, Any] | None = None,
    as_of_date: date | None = None,
) -> DatasetConfig:
    """Build a validated config from a preset, a size, a seed, and optional overrides.

    ``overrides`` is a nested mapping merged over the preset, for example
    ``{"mess": {"names": {"enabled": True, "intensity": 0.8}}}``.
    """
    preset_data = load_preset(preset)
    data: dict[str, Any] = {
        "preset": preset,
        "size": {"households": households_for(size)},
        "seed": seed,
        "coverage": preset_data.get("coverage", {}),
        "book_of_business": preset_data.get("book_of_business", {}),
        "mess": preset_data.get("mess", {}),
    }
    if as_of_date is not None:
        data["as_of_date"] = as_of_date
    if overrides:
        data = _deep_merge(data, overrides)
    return DatasetConfig.model_validate(data)


# --- canonical form, hash, identifier -----------------------------------------------------


def _normalize(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, _HASH_FLOAT_PLACES)
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


def canonical_json(config: DatasetConfig) -> str:
    """Stable text form: sorted keys, no whitespace, floats rounded to 6 places.

    The ``preset`` label is excluded: it is informational, and two configs with identical
    settings describe the same data whatever they are called.
    """
    data = config.model_dump(mode="json", exclude={"preset"})
    return json.dumps(_normalize(data), sort_keys=True, separators=(",", ":"))


def config_hash(config: DatasetConfig) -> str:
    """First 12 hex characters of the SHA-256 of the canonical form. A public format."""
    return hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()[:12]


def size_label(households: int) -> str:
    for label, count in SIZES.items():
        if count == households:
            return label
    return f"n{households}"


def dataset_id(config: DatasetConfig) -> str:
    """For example ``typical-default-s42-3fa9c1d2``."""
    preset = config.preset or "custom"
    return f"{preset}-{size_label(config.size.households)}-s{config.seed}-{config_hash(config)[:8]}"

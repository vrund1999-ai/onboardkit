from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from onboardkit.datagen.config import (
    LEVELS,
    MESS_TYPE_NAMES,
    MessConfig,
    MessSetting,
    apply_overrides,
    effective_rate,
    load_config,
    parse_level,
    resolve_config,
)


@dataclass(frozen=True)
class FakeType:
    name: str
    max_rate: float


def config(**settings: tuple[bool, float]) -> MessConfig:
    return MessConfig.model_validate(
        {name: {"enabled": on, "intensity": value} for name, (on, value) in settings.items()}
    )


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("off", 0.0),
        ("light", 0.2),
        ("moderate", 0.5),
        ("heavy", 0.8),
        ("max", 1.0),
        ("HEAVY", 0.8),
        (" light ", 0.2),
        ("0.4", 0.4),
        ("1", 1.0),
        ("0", 0.0),
        (0.25, 0.25),
        (1, 1.0),
    ],
)
def test_parse_level_accepts_words_and_numbers(given: str | float, expected: float) -> None:
    assert parse_level(given) == expected


@pytest.mark.parametrize(
    "bad", ["", "loud", "1.5", "-0.1", "nan", "inf", "0,5", 1.5, -1, float("nan"), True]
)
def test_parse_level_rejects_everything_else(bad: str | float) -> None:
    with pytest.raises(ValueError, match="invalid level"):
        parse_level(bad)


def test_level_words_are_documented_values() -> None:
    assert LEVELS == {"off": 0.0, "light": 0.2, "moderate": 0.5, "heavy": 0.8, "max": 1.0}


def test_unknown_mess_name_lists_valid_names() -> None:
    with pytest.raises(ValidationError) as caught:
        MessConfig.model_validate({"nmes": {"enabled": True, "intensity": 0.3}})
    message = str(caught.value)
    assert "nmes" in message
    assert all(name in message for name in MESS_TYPE_NAMES)


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_intensity_out_of_range_fails(bad: float) -> None:
    with pytest.raises(ValidationError):
        MessSetting(enabled=True, intensity=bad)


def test_disabled_with_intensity_is_inactive_and_has_zero_rate() -> None:
    cfg = config(names=(False, 0.9), formats=(True, 0.0), balances=(True, 0.5))
    assert not cfg.is_active("names")
    assert not cfg.is_active("formats")
    assert cfg.is_active("balances")
    assert not cfg.is_active("households")  # missing key
    assert effective_rate(cfg, FakeType("names", 0.35)) == 0.0
    assert cfg.active_names() == ["balances"]


@pytest.mark.parametrize(
    ("intensity", "max_rate", "expected"),
    [(0.5, 0.35, 0.175), (1.0, 0.15, 0.15), (0.2, 0.4, 0.08), (0.0, 0.25, 0.0)],
)
def test_effective_rate_is_intensity_times_max_rate(
    intensity: float, max_rate: float, expected: float
) -> None:
    cfg = config(names=(True, intensity))
    assert effective_rate(cfg, FakeType("names", max_rate)) == pytest.approx(expected)


def test_active_names_follow_canonical_order() -> None:
    cfg = config(balances=(True, 0.5), names=(True, 0.1), households=(True, 0.2))
    assert cfg.active_names() == ["names", "households", "balances"]


def test_overrides_enable_types_and_return_a_new_object() -> None:
    original = config(names=(False, 0.0), balances=(True, 0.3))
    snapshot = original.model_dump()
    updated = apply_overrides(original, ["names=heavy", "households=0.4"])
    assert updated is not original
    assert original.model_dump() == snapshot
    assert updated.settings["names"] == MessSetting(enabled=True, intensity=0.8)
    assert updated.settings["households"] == MessSetting(enabled=True, intensity=0.4)
    assert updated.settings["balances"] == original.settings["balances"]


def test_override_off_disables_and_later_items_win() -> None:
    updated = apply_overrides(config(names=(True, 0.5)), ["names=off"])
    assert updated.settings["names"] == MessSetting(enabled=False, intensity=0.0)
    again = apply_overrides(config(), ["formats=light", "formats=max"])
    assert again.settings["formats"].intensity == 1.0


@pytest.mark.parametrize("bad", ["names", "=heavy", "names=loud", "names=2"])
def test_malformed_overrides_fail(bad: str) -> None:
    with pytest.raises(ValueError, match="invalid"):
        apply_overrides(config(), [bad])


def test_override_with_unknown_name_lists_valid_names() -> None:
    with pytest.raises(ValueError, match=r"unknown mess type 'nmes'.*names.*balances"):
        apply_overrides(config(), ["nmes=heavy"])


def test_yaml_round_trip(tmp_path: Path) -> None:
    base = resolve_config("clean", "sample", 3)
    cfg = apply_overrides(base.mess, ["names=heavy", "balances=0.4"])
    dumped = yaml.safe_dump(cfg.model_dump())
    assert MessConfig.model_validate(yaml.safe_load(dumped)) == cfg

    full = base.model_copy(update={"mess": cfg})
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(full.model_dump(mode="json")), encoding="utf-8")
    assert load_config(path) == full


def test_yaml_with_bad_intensity_or_name_fails(tmp_path: Path) -> None:
    for body, needle in (
        ("mess: {names: {enabled: true, intensity: 1.5}}", "less than or equal to 1"),
        ("mess: {nmes: {enabled: true, intensity: 0.5}}", "unknown mess type"),
    ):
        path = tmp_path / "bad.yaml"
        path.write_text(
            f"size: {{households: 5}}\nseed: 1\ncoverage: {{}}\n{body}\n", encoding="utf-8"
        )
        with pytest.raises(ValidationError) as caught:
            load_config(path)
        assert needle in str(caught.value)
        assert "Field required" not in str(caught.value)

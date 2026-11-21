import os
import re
import time
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from onboardkit.datagen import config as config_module
from onboardkit.datagen.config import (
    DatasetConfig,
    available_presets,
    canonical_json,
    config_hash,
    dataset_id,
    load_config,
    resolve_config,
)

NAMES_ON: dict[str, Any] = {"mess": {"names": {"enabled": True, "intensity": 0.5}}}


def _base() -> DatasetConfig:
    return resolve_config("clean", "default", 42)


def test_sample_and_default_sizes() -> None:
    assert resolve_config("clean", "sample", 1).size.households == 15
    assert resolve_config("clean", "default", 1).size.households == 300
    assert resolve_config("clean", 120, 1).size.households == 120
    assert resolve_config("clean", "120", 1).size.households == 120


@pytest.mark.parametrize("size", [0, 5001, -3, "huge"])
def test_bad_sizes_rejected(size: str | int) -> None:
    with pytest.raises(ValueError, match=r"size|households|greater|less"):
        resolve_config("clean", size, 1)


def test_unknown_preset_lists_available() -> None:
    with pytest.raises(ValueError, match="clean"):
        resolve_config("missing", "sample", 1)


@pytest.mark.parametrize("seed", [-1, 2**63])
def test_seed_range(seed: int) -> None:
    with pytest.raises(ValidationError):
        resolve_config("clean", "sample", seed)


def test_unknown_key_in_yaml_names_the_key(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "size: {households: 15}\nseed: 1\ncoverage: {}\nmess: {}\nsede: 2\n", encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="sede"):
        load_config(path)


def test_unknown_mess_type_lists_valid_names() -> None:
    with pytest.raises(ValidationError, match=r"valid: .*names"):
        resolve_config("clean", "sample", 1, {"mess": {"nmes": {"enabled": True}}})


def test_coverage_rates_must_be_between_zero_and_one() -> None:
    with pytest.raises(ValidationError):
        resolve_config("clean", "sample", 1, {"coverage": {"crm": {"persons": 1.2}}})


def test_unknown_firm_profile_rejected() -> None:
    with pytest.raises(ValidationError, match="firm_profile"):
        resolve_config("clean", "sample", 1, {"firm_profile": "other"})


def test_equal_configs_have_equal_hashes() -> None:
    assert config_hash(_base()) == config_hash(_base())
    assert _base() == _base()


@pytest.mark.parametrize(
    "change",
    [
        {"seed": 43},
        {"size": {"households": 301}},
        {"as_of_date": date(2024, 12, 31)},
        NAMES_ON,
        {"mess": {"balances": {"enabled": True, "intensity": 0.1}}},
        {"coverage": {"crm": {"persons": 0.97}}},
        {"coverage": {"book_of_business": {"stale_extra_rate": 0.03}}},
        {"coverage": {"custodian": {"accounts": 0.99}}},
    ],
)
def test_hash_changes_when_any_field_group_changes(change: dict[str, Any]) -> None:
    changed = resolve_config("clean", "default", 42, change)
    assert config_hash(changed) != config_hash(_base())
    assert dataset_id(changed) != dataset_id(_base())


def test_intensity_change_changes_hash() -> None:
    low = resolve_config(
        "clean", "default", 42, {"mess": {"names": {"enabled": True, "intensity": 0.5}}}
    )
    high = resolve_config(
        "clean", "default", 42, {"mess": {"names": {"enabled": True, "intensity": 0.6}}}
    )
    assert config_hash(low) != config_hash(high)


def test_float_noise_beyond_six_places_does_not_change_hash() -> None:
    a = resolve_config(
        "clean", "default", 42, {"mess": {"names": {"enabled": True, "intensity": 0.5}}}
    )
    b = resolve_config(
        "clean", "default", 42, {"mess": {"names": {"enabled": True, "intensity": 0.5 + 1e-9}}}
    )
    assert config_hash(a) == config_hash(b)


def test_yaml_key_order_does_not_change_hash(tmp_path: Path) -> None:
    first = (
        "size: {households: 15}\nseed: 7\ncoverage: {}\n"
        "mess:\n  names: {enabled: true, intensity: 0.4}\n"
    )
    second = (
        "mess:\n  names: {intensity: 0.4, enabled: true}\ncoverage: {}\n"
        "seed: 7\nsize: {households: 15}\n"
    )
    (tmp_path / "a.yaml").write_text(first, encoding="utf-8")
    (tmp_path / "b.yaml").write_text(second, encoding="utf-8")
    assert config_hash(load_config(tmp_path / "a.yaml")) == config_hash(
        load_config(tmp_path / "b.yaml")
    )


def test_preset_label_is_not_part_of_the_hash() -> None:
    labelled = _base()
    unlabelled = labelled.model_copy(update={"preset": None})
    assert config_hash(labelled) == config_hash(unlabelled)
    assert dataset_id(unlabelled).startswith("custom-")


def test_hash_is_pinned() -> None:
    # Guards accidental changes to the canonical form: every dataset id depends on it.
    config = resolve_config("clean", "default", 42)
    assert canonical_json(config).startswith('{"as_of_date":"2025-12-31","coverage":')
    assert config_hash(config) == "79dbff01d7b7"


def test_dataset_id_shape() -> None:
    identifier = dataset_id(_base())
    assert re.fullmatch(r"clean-default-s42-[0-9a-f]{8}", identifier)
    assert dataset_id(resolve_config("clean", "sample", 7)).startswith("clean-sample-s7-")
    assert dataset_id(resolve_config("clean", 50, 7)).startswith("clean-n50-s7-")


def test_overrides_do_not_mutate_the_preset() -> None:
    resolve_config("clean", "sample", 1, NAMES_ON)
    again = resolve_config("clean", "sample", 1)
    assert again.mess.settings["names"].enabled is False


def test_resolve_config_ignores_environment_and_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    reads: list[str] = []

    class SpyEnv(dict[str, str]):
        def get(self, key: str, default: Any = None) -> Any:
            reads.append(key)
            return super().get(key, default)

        def __getitem__(self, key: str) -> str:
            reads.append(key)
            return super().__getitem__(key)

    def tick() -> float:
        raise AssertionError("clock was read")

    monkeypatch.setattr(os, "environ", SpyEnv(os.environ))
    monkeypatch.setattr(time, "time", tick)
    config = resolve_config("clean", "sample", 3, NAMES_ON)
    assert config_hash(config)
    assert reads == []


def test_module_source_does_not_touch_environment_or_clock() -> None:
    source = Path(config_module.__file__).read_text(encoding="utf-8")
    for forbidden in ("os.environ", "getenv", "datetime.now", "date.today", "time.time"):
        assert forbidden not in source


def test_clean_preset_is_available_and_inactive() -> None:
    assert "clean" in available_presets()
    config = _base()
    assert all(not s.enabled for s in config.mess.settings.values())

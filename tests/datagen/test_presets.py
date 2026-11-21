import pytest
from pydantic import ValidationError

from onboardkit.datagen.config import (
    MESS_TYPE_NAMES,
    DatasetConfig,
    available_presets,
    config_hash,
    load_preset,
    resolve_config,
)
from onboardkit.datagen.mess.base import group_by_table
from onboardkit.datagen.mess.registry import DEFAULT_REGISTRY
from onboardkit.datagen.pipeline import build_rows


def test_three_presets_exist_and_validate() -> None:
    assert available_presets() == ["clean", "nightmare", "typical"]
    for name in available_presets():
        config = resolve_config(name, "sample", 42)
        assert isinstance(config, DatasetConfig)
        assert load_preset(name)["name"] == name
        assert load_preset(name)["description"]


def test_unknown_preset_lists_the_valid_ones() -> None:
    with pytest.raises(ValueError, match=r"unknown preset 'messy'.*clean.*nightmare.*typical"):
        resolve_config("messy", "sample", 1)


def test_preset_values_match_the_story() -> None:
    typical = resolve_config("typical", "sample", 1)
    assert typical.coverage.custodian.accounts == 1.0
    assert (typical.coverage.crm.persons, typical.coverage.crm.account_links) == (0.97, 0.90)
    book = typical.coverage.book_of_business
    assert (book.households, book.accounts, book.stale_extra_rate) == (0.85, 0.80, 0.03)
    assert {n: s.intensity for n, s in typical.mess.settings.items()} == {
        "names": 0.5,
        "households": 0.3,
        "formats": 0.5,
        "balances": 0.4,
    }
    nightmare = resolve_config("nightmare", "sample", 1)
    assert nightmare.coverage.custodian.accounts == 0.98
    assert (nightmare.coverage.crm.persons, nightmare.coverage.crm.account_links) == (0.90, 0.75)
    book = nightmare.coverage.book_of_business
    assert (book.households, book.accounts, book.stale_extra_rate) == (0.70, 0.60, 0.08)
    assert {s.intensity for s in nightmare.mess.settings.values()} == {0.9}
    assert resolve_config("clean", "sample", 1).mess.active_names() == []


def test_every_preset_sets_every_mess_type() -> None:
    for name in available_presets():
        assert set(resolve_config(name, "sample", 1).mess.settings) == set(MESS_TYPE_NAMES)


def test_registered_mess_types_match_the_config_names() -> None:
    assert sorted(DEFAULT_REGISTRY.names()) == sorted(MESS_TYPE_NAMES)


def test_invalid_override_of_a_preset_is_rejected() -> None:
    with pytest.raises(ValidationError):
        resolve_config("typical", "sample", 1, {"mess": {"names": {"intensity": 1.5}}})


def test_clean_output_equals_the_projection_exactly() -> None:
    built = build_rows(resolve_config("clean", 60, 42))
    assert built.coverage_events == []
    assert built.mess_events == []
    assert built.data == group_by_table(built.projected)


def test_same_seed_gives_identical_truth_but_different_exports() -> None:
    clean = build_rows(resolve_config("clean", 60, 42))
    nightmare = build_rows(resolve_config("nightmare", 60, 42))
    assert clean.firm.model_dump_json() == nightmare.firm.model_dump_json()
    assert clean.data != nightmare.data
    assert nightmare.mess_events
    assert nightmare.coverage_events
    assert config_hash(clean.config) != config_hash(nightmare.config)


def test_typical_is_messy_but_less_than_nightmare() -> None:
    typical = build_rows(resolve_config("typical", 100, 42))
    nightmare = build_rows(resolve_config("nightmare", 100, 42))
    assert 0 < len(typical.mess_events) < len(nightmare.mess_events)
    assert 0 < len(typical.coverage_events) < len(nightmare.coverage_events)


def test_pipeline_is_deterministic() -> None:
    first = build_rows(resolve_config("typical", 60, 7))
    second = build_rows(resolve_config("typical", 60, 7))
    assert first.data == second.data
    assert first.mess_events == second.mess_events
    assert first.coverage_events == second.coverage_events

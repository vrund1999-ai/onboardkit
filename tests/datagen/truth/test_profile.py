import copy
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from onboardkit.datagen.truth.profile import PROFILE_PATH, FirmProfile, load_profile


def _raw() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8"))
    return copy.deepcopy(data)


def test_shipped_profile_loads() -> None:
    profile = load_profile()
    assert profile.sizes.sample == 15
    assert profile.sizes.default == 300
    assert profile.firm.as_of_date.isoformat() == "2025-12-31"
    assert abs(profile.balances.sigma - 1.398) < 0.001


def test_archetype_shares_must_sum_to_one() -> None:
    data = _raw()
    data["archetypes"]["couple"]["share"] = 0.5
    with pytest.raises(ValidationError, match="archetype shares"):
        FirmProfile.model_validate(data)


def test_account_count_shares_must_sum_to_one() -> None:
    data = _raw()
    data["account_counts"][0]["share"] = 0.5
    with pytest.raises(ValidationError, match="account count shares"):
        FirmProfile.model_validate(data)


def test_every_account_type_needs_a_rule() -> None:
    data = _raw()
    del data["account_types"]["roth_ira"]
    with pytest.raises(ValidationError, match="every account type"):
        FirmProfile.model_validate(data)


def test_ira_cannot_be_joint_owned() -> None:
    data = _raw()
    data["account_types"]["roth_ira"]["owners"] = 2
    with pytest.raises(ValidationError, match="owner"):
        FirmProfile.model_validate(data)


def test_unknown_keys_rejected() -> None:
    data = _raw()
    data["balances"]["mediann"] = 1
    with pytest.raises(ValidationError):
        FirmProfile.model_validate(data)

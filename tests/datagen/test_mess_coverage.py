from collections import Counter

import pytest

from onboardkit.datagen.config import MESS_TYPE_NAMES, resolve_config
from onboardkit.datagen.mess.base import DescribesSubtypes
from onboardkit.datagen.mess.registry import DEFAULT_REGISTRY
from onboardkit.datagen.pipeline import build_rows


@pytest.fixture(scope="module")
def nightmare_counts() -> Counter[tuple[str, str]]:
    built = build_rows(resolve_config("nightmare", "default", 42))
    assert built.config.size.households == 300
    return Counter((e.mess_type, e.subtype) for e in built.mess_events)


@pytest.mark.parametrize("name", MESS_TYPE_NAMES)
def test_every_subtype_of_every_type_appears_at_nightmare(
    name: str, nightmare_counts: Counter[tuple[str, str]]
) -> None:
    mess = DEFAULT_REGISTRY.get(name)
    assert isinstance(mess, DescribesSubtypes)
    assert mess.subtypes
    missing = sorted(s for s in mess.subtypes if nightmare_counts[(name, s)] == 0)
    assert not missing, f"{name}: no events for {missing}"


def test_no_event_uses_an_undeclared_subtype(nightmare_counts: Counter[tuple[str, str]]) -> None:
    for name, subtype in nightmare_counts:
        mess = DEFAULT_REGISTRY.get(name)
        assert isinstance(mess, DescribesSubtypes)
        assert subtype in mess.subtypes, f"{name} emitted undeclared subtype {subtype!r}"

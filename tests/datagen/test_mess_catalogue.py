import importlib.util
from pathlib import Path
from types import ModuleType

from onboardkit.datagen.mess.registry import DEFAULT_REGISTRY

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "mess_catalogue.py"
DOCUMENT = ROOT / "docs" / "mess-catalogue.md"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mess_catalogue", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_catalogue_is_up_to_date() -> None:
    expected = load_script().render()
    committed = DOCUMENT.read_bytes().decode("utf-8").replace("\r\n", "\n")
    assert committed == expected, "run `python scripts/mess_catalogue.py` and commit the result"


def test_catalogue_lists_every_type_and_subtype_with_an_example() -> None:
    text = load_script().render()
    for name in DEFAULT_REGISTRY.names():
        mess = DEFAULT_REGISTRY.get(name)
        assert f"## {name}\n" in text
        for subtype in mess.subtypes:  # type: ignore[attr-defined]
            assert f"| `{subtype}` |" in text
    assert "no example in this dataset" not in text


def test_catalogue_is_reproducible() -> None:
    module = load_script()
    assert module.render() == module.render()

"""Export-writing code must never read the answer keys."""

import ast
from pathlib import Path

import onboardkit.datagen as datagen

PACKAGE = Path(datagen.__file__).parent
# Everything that builds or writes the exports, plus the truth model they are built from.
EXPORT_SIDE = ("sources", "mess", "truth")
FORBIDDEN = "answer_keys"


def forbidden_imports(source: str) -> list[str]:
    """Names imported anywhere in ``source`` (even inside a function) that reach answer keys."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if FORBIDDEN in a.name.split(".")]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if FORBIDDEN in module.split("."):
                found.append(module)
            found += [f"{module}.{a.name}" for a in node.names if a.name == FORBIDDEN]
    return found


def test_the_scanner_catches_every_import_form() -> None:
    assert forbidden_imports("import onboardkit.datagen.answer_keys.provenance") != []
    assert forbidden_imports("from onboardkit.datagen.answer_keys import checks") != []
    assert forbidden_imports("from onboardkit.datagen import answer_keys") != []
    assert forbidden_imports("def f():\n    from onboardkit.datagen.answer_keys.x import y") != []
    assert forbidden_imports("import json\nfrom onboardkit.datagen.sources import base") == []


def test_export_side_modules_do_not_import_answer_keys() -> None:
    checked = 0
    for folder in EXPORT_SIDE:
        for path in sorted((PACKAGE / folder).rglob("*.py")):
            assert forbidden_imports(path.read_text(encoding="utf-8")) == [], path
            checked += 1
    assert checked > 10


def test_answer_keys_are_only_pulled_in_by_the_pipeline_hook_and_the_command_line() -> None:
    importers = {
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*.py")
        if "answer_keys" not in path.parts and forbidden_imports(path.read_text(encoding="utf-8"))
    }
    assert importers == {"pipeline.py", "cli.py"}

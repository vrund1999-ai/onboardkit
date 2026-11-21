"""Guards: the architecture module map and the contributing guide match the repository."""

import re
from pathlib import Path

import onboardkit.datagen as datagen
from tests.guards.markdown import REPO_ROOT

ARCHITECTURE = REPO_ROOT / "docs" / "architecture.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
TEMPLATE = REPO_ROOT / ".github" / "pull_request_template.md"
PACKAGE = Path(datagen.__file__).parent
MODULE_ROW = re.compile(r"^\| `([^`|]+)` \|", re.M)


def module_map(text: str) -> set[str]:
    section = text.split("## Module map", 1)[1].split("\n## ", 1)[0]
    return set(MODULE_ROW.findall(section))


def real_entries() -> set[str]:
    folders = {f"{p.name}/" for p in PACKAGE.iterdir() if p.is_dir() and p.name != "__pycache__"}
    modules = {p.name for p in PACKAGE.glob("*.py") if p.name not in {"__init__.py", "__main__.py"}}
    return folders | modules


def test_the_module_map_lists_exactly_the_real_packages_and_modules() -> None:
    documented = module_map(ARCHITECTURE.read_text(encoding="utf-8"))
    real = real_entries()
    assert documented - real == set(), "documented but not in the repository"
    assert real - documented == set(), "in the repository but missing from the module map"


def test_the_architecture_document_has_the_pipeline_diagram() -> None:
    text = ARCHITECTURE.read_text(encoding="utf-8")
    assert "config -> truth firm -> per-source rows -> coverage -> mess -> exports" in text
    assert "answer keys (truth/)" in text


def test_the_module_map_check_notices_a_new_package(tmp_path: Path) -> None:
    text = "## Module map\n\n| `mess/` | x |\n| `gone/` | y |\n\n## Next\n| `ignored/` | z |\n"
    assert module_map(text) == {"mess/", "gone/"}


def test_contributing_covers_the_nine_sections() -> None:
    headings = re.findall(r"^## (\d+)\. ", CONTRIBUTING.read_text(encoding="utf-8"), re.M)
    assert headings == [str(n) for n in range(1, 10)]


def test_branch_naming_matches_the_project_rules() -> None:
    rules = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    contributing = CONTRIBUTING.read_text(encoding="utf-8")
    for pattern in ("docs/<topic>", "feat/<story-id>-<slug>", "fix/<slug>"):
        assert pattern in rules
        assert pattern in contributing
    assert "CONTRIBUTING.md" in TEMPLATE.read_text(encoding="utf-8")

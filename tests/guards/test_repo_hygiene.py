"""Guard: no generated data, secrets, big files, or spreadsheets are committed by accident."""

import fnmatch
import subprocess
from pathlib import Path

import pytest

from tests.guards.markdown import REPO_ROOT

GENERATED_FOLDERS = ("data/generated/", "output/")
REQUIRED_IGNORES = ("data/generated/", ".env", ".env.*", "output/")
SIZE_LIMIT = 1_000_000  # bytes
# Tracked files allowed to exceed the size limit. Each entry needs a reason.
ALLOW_LARGE: frozenset[str] = frozenset(
    {
        "uv.lock",  # the dependency lock file grows with the dependency tree
    }
)
DATA_EXTENSIONS = (".xlsx", ".xlsm", ".xls", ".csv")
# Folders where small hand-made data files may be tracked. Each pattern needs a reason.
ALLOW_DATA = (
    "tests/**/fixtures/**",  # tiny hand-written inputs for tests
    "tests/**/expected/**",  # recorded expected outputs
)


def tracked_files(root: Path = REPO_ROOT) -> list[str] | None:
    """Tracked paths (forward slashes) from ``git ls-files``, or None outside a git checkout."""
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return [p for p in done.stdout.decode("utf-8").split("\0") if p]


def generated_data_problems(files: list[str]) -> list[str]:
    return [
        f"{f}: generated data must not be tracked" for f in files if f.startswith(GENERATED_FOLDERS)
    ]


def gitignore_problems(text: str) -> list[str]:
    lines = {line.strip() for line in text.splitlines()}
    return [
        f".gitignore no longer contains {entry!r}"
        for entry in REQUIRED_IGNORES
        if entry not in lines
    ]


def size_problems(files: list[str], root: Path = REPO_ROOT) -> list[str]:
    found = []
    for f in files:
        path = root / f
        if f not in ALLOW_LARGE and path.is_file() and path.stat().st_size > SIZE_LIMIT:
            found.append(f"{f}: {path.stat().st_size} bytes is over the {SIZE_LIMIT} byte limit")
    return found


def data_file_problems(files: list[str]) -> list[str]:
    return [
        f"{f}: spreadsheets and CSVs belong only under fixtures or expected folders"
        for f in files
        if f.lower().endswith(DATA_EXTENSIONS)
        and not any(fnmatch.fnmatch(f, pattern) for pattern in ALLOW_DATA)
    ]


def environment_file_problems(files: list[str]) -> list[str]:
    return [
        f"{f}: environment files must not be tracked (use .env.example)"
        for f in files
        if Path(f).name.startswith(".env") and Path(f).name != ".env.example"
    ]


@pytest.fixture(scope="module")
def tracked() -> list[str]:
    files = tracked_files()
    if files is None:
        pytest.skip("not a git checkout")
    return files


def test_no_generated_data_is_tracked(tracked: list[str]) -> None:
    assert generated_data_problems(tracked) == []


def test_gitignore_still_protects_generated_data_and_secrets() -> None:
    assert gitignore_problems((REPO_ROOT / ".gitignore").read_text(encoding="utf-8")) == []


def test_no_large_files_are_tracked(tracked: list[str]) -> None:
    assert size_problems(tracked) == []


def test_no_spreadsheets_or_csvs_outside_fixtures(tracked: list[str]) -> None:
    assert data_file_problems(tracked) == []


def test_no_environment_files_are_tracked(tracked: list[str]) -> None:
    assert environment_file_problems(tracked) == []


def test_allow_lists_name_files_that_exist(tracked: list[str]) -> None:
    assert set(tracked) >= ALLOW_LARGE, "remove allow-list entries for files that are gone"


# The rules themselves, shown failing on made-up input.


def test_generated_data_is_reported() -> None:
    assert generated_data_problems(
        ["src/a.py", "data/generated/x/exports/a.csv", "output/r.xlsx"]
    ) == [
        "data/generated/x/exports/a.csv: generated data must not be tracked",
        "output/r.xlsx: generated data must not be tracked",
    ]


def test_a_gitignore_missing_an_entry_is_reported() -> None:
    assert gitignore_problems(".env\n.env.*\noutput/\n") == [
        ".gitignore no longer contains 'data/generated/'"
    ]


def test_a_two_megabyte_file_is_reported_and_the_allow_list_works(tmp_path: Path) -> None:
    (tmp_path / "big.bin").write_bytes(b"x" * 2_000_000)
    (tmp_path / "uv.lock").write_bytes(b"x" * 2_000_000)
    (tmp_path / "small.txt").write_text("ok", encoding="utf-8")
    problems = size_problems(["big.bin", "uv.lock", "small.txt"], tmp_path)
    assert len(problems) == 1 and problems[0].startswith("big.bin: 2000000 bytes")


def test_data_files_are_reported_outside_the_allowed_folders() -> None:
    files = [
        "export.csv",
        "docs/book.XLSX",
        "tests/datagen/expected/standard.csv",
        "tests/guards/fixtures/tiny.xlsx",
        "tests/datagen/test_x.py",
    ]
    assert [p.split(":")[0] for p in data_file_problems(files)] == ["export.csv", "docs/book.XLSX"]


def test_environment_files_are_reported() -> None:
    assert [
        p.split(":")[0]
        for p in environment_file_problems([".env", ".env.local", ".env.example", "a/.env"])
    ] == [
        ".env",
        ".env.local",
        "a/.env",
    ]


def test_staging_a_generated_file_is_seen_by_the_tracked_file_check(tmp_path: Path) -> None:
    try:
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git is not available")
    target = tmp_path / "data" / "generated" / "x"
    target.mkdir(parents=True)
    (target / "a.csv").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-f", "data"], check=True, timeout=60)
    files = tracked_files(tmp_path)
    assert files == ["data/generated/x/a.csv"]
    assert generated_data_problems(files) != []

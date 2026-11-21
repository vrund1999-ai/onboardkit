import json
import subprocess
import time
from pathlib import Path

import pytest

from onboardkit.datagen import GENERATOR_VERSION
from onboardkit.datagen.manifest import verify_manifest
from onboardkit.datagen.pipeline import generate_dataset
from onboardkit.datagen.standard import (
    GUIDANCE,
    STANDARD_DATASETS,
    compare_checksums,
    file_checksums,
    standard_config,
)

EXPECTED = Path(__file__).parent / "expected" / "standard_datasets.json"
REPO = Path(__file__).resolve().parents[2]
SECONDS = {"sample": 5, "demo": 60}


@pytest.mark.parametrize(
    "name",
    [pytest.param(n, marks=pytest.mark.slow) if n == "demo" else n for n in STANDARD_DATASETS],
)
def test_standard_dataset_matches_the_recorded_checksums(name: str, tmp_path: Path) -> None:
    started = time.perf_counter()
    result = generate_dataset(standard_config(name), tmp_path)
    elapsed = time.perf_counter() - started
    problems = compare_checksums(EXPECTED, name, file_checksums(result.path))
    assert not problems, "\n".join(problems)
    assert verify_manifest(result.path) == []
    assert elapsed < SECONDS[name] * 3  # generous: CI machines are slower than a laptop


def test_standard_definitions_match_the_documented_commands() -> None:
    assert STANDARD_DATASETS == {
        "sample": ("typical", "sample", 42),
        "demo": ("typical", "default", 42),
    }
    assert standard_config("sample").size.households == 15
    assert standard_config("demo").size.households == 300


def test_every_recorded_version_lists_both_standard_datasets() -> None:
    recorded = json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert GENERATOR_VERSION in recorded
    for entry in recorded.values():
        assert set(entry) == set(STANDARD_DATASETS)
        for files in entry.values():
            assert files
            assert all(len(digest) == 64 for digest in files.values())


def test_the_guard_fires_with_guidance_when_output_changes(tmp_path: Path) -> None:
    result = generate_dataset(standard_config("sample"), tmp_path)
    actual = file_checksums(result.path)
    assert compare_checksums(EXPECTED, "sample", actual) == []
    changed = dict(actual)
    victim = "exports/crm/crm_contacts.csv"
    changed[victim] = "0" * 64
    problems = compare_checksums(EXPECTED, "sample", changed)
    assert problems[0].startswith(f"{victim}: expected ")
    assert problems[-1] == GUIDANCE
    assert "bump the generator version" in GUIDANCE
    assert "update_expected_checksums.py" in GUIDANCE


def test_an_added_or_removed_file_also_fires_the_guard() -> None:
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))[GENERATOR_VERSION]["sample"]
    extra = {**expected, "exports/new.csv": "1" * 64}
    assert any("not in the recorded" in p for p in compare_checksums(EXPECTED, "sample", extra))
    fewer = dict(expected)
    fewer.pop("exports/crm/crm_contacts.csv")
    assert any("missing" in p for p in compare_checksums(EXPECTED, "sample", fewer))


def test_an_unrecorded_generator_version_fails_with_guidance() -> None:
    problems = compare_checksums(EXPECTED, "sample", {}, version="99.0.0")
    assert "no checksums recorded" in problems[0]
    assert problems[-1] == GUIDANCE


def test_generated_data_is_not_tracked_by_git(tmp_path: Path) -> None:
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "data/generated/typical-sample-s42-937ab0dd/manifest.json"],
        cwd=REPO, check=False,
    )  # fmt: skip
    assert ignored.returncode == 0
    tracked = subprocess.run(
        ["git", "ls-files", "data"], cwd=REPO, capture_output=True, text=True, check=True
    )
    assert tracked.stdout.strip() == ""

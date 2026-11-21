"""Guards for the generator version, the coverage threshold, and the shared fixtures."""

import json
import re
import tomllib
from pathlib import Path

from onboardkit.datagen import GENERATOR_VERSION
from onboardkit.datagen.manifest import verify_manifest
from onboardkit.datagen.pipeline import DatasetResult
from tests.conftest import GENERATED, snapshot
from tests.guards.markdown import REPO_ROOT

CHANGELOG = REPO_ROOT / "docs" / "datagen-changelog.md"
EXPECTED = REPO_ROOT / "tests" / "datagen" / "expected" / "standard_datasets.json"
PYPROJECT = REPO_ROOT / "pyproject.toml"
TESTING_DOC = REPO_ROOT / "docs" / "testing.md"
MINIMUM_COVERAGE = 85
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def changelog_versions(text: str) -> list[str]:
    return re.findall(r"^## (\d+\.\d+\.\d+)\s*$", text, re.M)


def test_the_generator_version_is_the_latest_changelog_entry() -> None:
    versions = changelog_versions(CHANGELOG.read_text(encoding="utf-8"))
    assert SEMVER.match(GENERATOR_VERSION)
    assert versions, "the changelog has no version entries"
    assert versions[0] == GENERATOR_VERSION, "newest entry must come first and match the code"
    assert len(set(versions)) == len(versions)


def test_checksums_are_recorded_for_the_current_version_and_only_for_logged_versions() -> None:
    recorded = json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert {"sample", "demo"} <= set(recorded[GENERATOR_VERSION])
    logged = set(changelog_versions(CHANGELOG.read_text(encoding="utf-8")))
    assert set(recorded) <= logged, "checksums recorded for a version the changelog does not list"


def test_the_coverage_threshold_is_enforced_and_documented() -> None:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    threshold = config["tool"]["coverage"]["report"]["fail_under"]
    assert threshold >= MINIMUM_COVERAGE, "never lower the coverage threshold silently"
    assert f"{threshold} percent" in TESTING_DOC.read_text(encoding="utf-8")


def test_the_slow_marker_is_declared() -> None:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    markers = config["tool"]["pytest"]["ini_options"]["markers"]
    assert any(m.startswith("slow:") for m in markers)
    assert "--strict-markers" in config["tool"]["pytest"]["ini_options"]["addopts"]


SEEN: list[Path] = []


def test_sample_dataset_is_a_real_dataset_shared_by_the_session(
    sample_dataset: DatasetResult,
) -> None:
    SEEN.append(sample_dataset.path)
    assert sample_dataset.dataset_id.startswith("typical-sample-s42")
    assert verify_manifest(sample_dataset.path) == []


def test_sample_dataset_is_not_generated_again(sample_dataset: DatasetResult) -> None:
    SEEN.append(sample_dataset.path)
    assert len(set(SEEN)) == 1


def test_clean_dataset_fixture(clean_dataset: DatasetResult, tmp_out_root: Path) -> None:
    assert clean_dataset.dataset_id.startswith("clean-sample-s42")
    assert not tmp_out_root.exists()


def test_the_repository_data_guard_notices_changes(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    assert snapshot(root) is None
    root.mkdir()
    assert snapshot(root) == []
    (root / "x").mkdir()
    assert snapshot(root) == ["x"]
    assert GENERATED.parts[-2:] == ("data", "generated")

"""Shared fixtures. See docs/testing.md for the test levels and markers."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from onboardkit.datagen.config import resolve_config
from onboardkit.datagen.pipeline import DatasetResult, generate_dataset

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED = REPO_ROOT / "data" / "generated"


def snapshot(root: Path) -> list[str] | None:
    """The sorted names directly under ``root``, or None when it does not exist."""
    if not root.is_dir():
        return None
    return sorted(p.name for p in root.iterdir())


@pytest.fixture(scope="session")
def sample_dataset(tmp_path_factory: pytest.TempPathFactory) -> DatasetResult:
    """The ``typical`` preset at ``sample`` size, seed 42, generated once per test session."""
    return generate_dataset(
        resolve_config("typical", "sample", 42), tmp_path_factory.mktemp("sample_dataset")
    )


@pytest.fixture(scope="session")
def clean_dataset(tmp_path_factory: pytest.TempPathFactory) -> DatasetResult:
    """The ``clean`` preset at ``sample`` size, seed 42, generated once per test session."""
    return generate_dataset(
        resolve_config("clean", "sample", 42), tmp_path_factory.mktemp("clean_dataset")
    )


@pytest.fixture
def tmp_out_root(tmp_path: Path) -> Path:
    """An empty output root for tests that generate their own datasets."""
    return tmp_path / "out"


@pytest.fixture(autouse=True)
def never_touch_repository_data() -> Iterator[None]:
    """Fail any test that creates or removes anything under the repository's data/generated."""
    before = snapshot(GENERATED)
    yield
    after = snapshot(GENERATED)
    assert after == before, f"a test changed {GENERATED}: {before} -> {after}"

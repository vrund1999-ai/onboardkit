"""The two standard datasets and their recorded checksums.

``sample`` is for fast tests and walkthroughs; ``demo`` is the realistic firm for demonstrations.
Expected checksums live in ``tests/datagen/expected/standard_datasets.json``, keyed by generator
version then dataset name. Regenerate them with ``scripts/update_expected_checksums.py`` when
output changes on purpose (and bump the version first; see docs/datagen-changelog.md).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from onboardkit.datagen import GENERATOR_VERSION
from onboardkit.datagen.config import DatasetConfig, resolve_config

STANDARD_DATASETS: dict[str, tuple[str, str, int]] = {
    "sample": ("typical", "sample", 42),
    "demo": ("typical", "default", 42),
}

GUIDANCE = (
    "Output changed. If intentional, bump the generator version, update the changelog, "
    "and run scripts/update_expected_checksums.py."
)


def standard_config(name: str) -> DatasetConfig:
    preset, size, seed = STANDARD_DATASETS[name]
    return resolve_config(preset, size, seed)


def file_checksums(root: Path) -> dict[str, str]:
    """SHA-256 of every file under ``root`` except the manifest, keyed by forward-slash path."""
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }


def compare_checksums(
    expected_file: Path, name: str, actual: dict[str, str], version: str = GENERATOR_VERSION
) -> list[str]:
    """Differences between the recorded and actual checksums; empty when they match."""
    recorded = json.loads(expected_file.read_text(encoding="utf-8"))
    expected = recorded.get(version, {}).get(name)
    if expected is None:
        return [f"no checksums recorded for {name!r} at generator version {version}", GUIDANCE]
    problems = [
        f"{path}: expected {expected[path][:12]}, got {actual.get(path, 'missing')[:12]}"
        for path in expected
        if actual.get(path) != expected[path]
    ]
    problems += [
        f"{path}: not in the recorded checksums" for path in actual if path not in expected
    ]
    return [*problems, GUIDANCE] if problems else []

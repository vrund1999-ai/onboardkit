"""The dataset manifest: what produced a dataset, and a checksum for every file in it.

The manifest is reproducible on purpose: it records no timestamp, user name, host name, or
absolute path, so generating the same configuration twice gives byte-identical manifests.
``manifest.json`` itself is not listed in ``files`` (it cannot contain its own checksum);
``files_digest`` hashes the listed checksums instead.
"""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Literal

from onboardkit.datagen import GENERATOR_VERSION
from onboardkit.datagen.config import DatasetConfig, config_hash, dataset_id

MANIFEST_VERSION = 1
MANIFEST_NAME = "manifest.json"
DEPENDENCIES = ("faker", "openpyxl", "pydantic")

ProblemKind = Literal["manifest", "missing", "changed", "extra", "locator", "unrecorded", "mapping"]


@dataclass(frozen=True)
class Problem:
    kind: ProblemKind
    path: str
    detail: str

    def __str__(self) -> str:
        return f"{self.kind}: {self.path}: {self.detail}"


def dependency_versions() -> dict[str, str]:
    versions = {"python": platform.python_version()}
    for name in DEPENDENCIES:
        versions[name] = metadata.version(name)
    return versions


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dataset_files(root: Path) -> list[str]:
    """Every file under the dataset except the manifest, as sorted forward-slash paths."""
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).as_posix() != MANIFEST_NAME
    )


def files_digest(files: list[dict[str, Any]]) -> str:
    return hashlib.sha256("".join(str(f["sha256"]) for f in files).encode("ascii")).hexdigest()


def build_manifest(root: Path, config: DatasetConfig, counts: dict[str, int]) -> dict[str, Any]:
    files = [
        {"path": rel, "sha256": _digest(root / rel), "bytes": (root / rel).stat().st_size}
        for rel in _dataset_files(root)
    ]
    return {
        "manifest_version": MANIFEST_VERSION,
        "dataset_id": dataset_id(config),
        "generator_version": GENERATOR_VERSION,
        "config": config.model_dump(mode="json"),
        "config_hash": config_hash(config),
        "dependencies": dependency_versions(),
        "counts": dict(sorted(counts.items())),
        "files": files,
        "files_digest": files_digest(files),
    }


def dumps(manifest: dict[str, Any]) -> str:
    """Sorted keys, two-space indent, trailing newline."""
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def write_manifest(root: Path, config: DatasetConfig, counts: dict[str, int]) -> dict[str, Any]:
    manifest = build_manifest(root, config, counts)
    (root / MANIFEST_NAME).write_text(dumps(manifest), encoding="utf-8", newline="\n")
    return manifest


def verify_manifest(dataset_dir: Path) -> list[Problem]:
    """Recompute sizes and checksums; report missing, changed, and extra files."""
    path = dataset_dir / MANIFEST_NAME
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        listed = {entry["path"]: entry for entry in manifest["files"]}
        recorded_digest = manifest["files_digest"]
        version = manifest["manifest_version"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [Problem("manifest", MANIFEST_NAME, f"cannot read manifest: {exc}")]
    problems: list[Problem] = []
    if version != MANIFEST_VERSION:
        problems.append(
            Problem("manifest", MANIFEST_NAME, f"unsupported manifest_version {version!r}")
        )
    if recorded_digest != files_digest(list(listed.values())):
        problems.append(Problem("manifest", MANIFEST_NAME, "files_digest does not match files"))
    for rel, entry in sorted(listed.items()):
        target = dataset_dir / rel
        if not target.is_file():
            problems.append(Problem("missing", rel, "listed in the manifest but not on disk"))
        elif target.stat().st_size != entry["bytes"]:
            problems.append(
                Problem("changed", rel, f"size {target.stat().st_size}, expected {entry['bytes']}")
            )
        elif _digest(target) != entry["sha256"]:
            problems.append(Problem("changed", rel, "checksum differs from the manifest"))
    for rel in _dataset_files(dataset_dir):
        if rel not in listed:
            problems.append(Problem("extra", rel, "file is not listed in the manifest"))
    return problems

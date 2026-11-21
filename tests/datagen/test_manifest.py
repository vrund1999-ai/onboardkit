import hashlib
import json
import platform
import re
from importlib import metadata
from pathlib import Path

import pytest

from onboardkit.datagen import GENERATOR_VERSION
from onboardkit.datagen.config import config_hash, resolve_config
from onboardkit.datagen.manifest import (
    MANIFEST_VERSION,
    Problem,
    dumps,
    files_digest,
    verify_manifest,
)
from onboardkit.datagen.pipeline import DatasetResult, generate_dataset

CHANGELOG = Path(__file__).resolve().parents[2] / "docs" / "datagen-changelog.md"


@pytest.fixture(scope="module")
def fresh(tmp_path_factory: pytest.TempPathFactory) -> DatasetResult:
    return generate_dataset(
        resolve_config("typical", "sample", 42), tmp_path_factory.mktemp("manifest")
    )


def load(result: DatasetResult) -> dict[str, object]:
    manifest = json.loads((result.path / "manifest.json").read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)
    return manifest


def test_manifest_has_every_field(fresh: DatasetResult) -> None:
    manifest = load(fresh)
    assert set(manifest) == {
        "manifest_version",
        "dataset_id",
        "generator_version",
        "config",
        "config_hash",
        "dependencies",
        "counts",
        "files",
        "files_digest",
    }
    assert manifest["manifest_version"] == MANIFEST_VERSION
    assert manifest["dataset_id"] == fresh.dataset_id
    assert manifest["generator_version"] == GENERATOR_VERSION
    assert manifest["config_hash"] == config_hash(fresh.config)
    assert manifest["config"] == fresh.config.model_dump(mode="json")
    assert manifest["counts"] == fresh.counts
    assert fresh.dataset_id.endswith(str(manifest["config_hash"])[:8])


def test_files_are_sorted_listed_with_checksums_and_exclude_the_manifest(
    fresh: DatasetResult,
) -> None:
    files = load(fresh)["files"]
    assert isinstance(files, list)
    paths = [f["path"] for f in files]
    assert paths == sorted(paths)
    assert "manifest.json" not in paths
    assert [p for p in paths if p.startswith("exports/")] == [
        "exports/book_of_business/book_of_business.xlsx",
        "exports/crm/crm_contacts.csv",
        "exports/crm/crm_linked_accounts.csv",
        "exports/custodian/custodian_accounts.csv",
    ]
    assert "truth/summary.json" in paths and "truth/discrepancies.csv" in paths
    for entry in files:
        data = (fresh.path / entry["path"]).read_bytes()
        assert entry["bytes"] == len(data)
        assert entry["sha256"] == hashlib.sha256(data).hexdigest()
        assert "\\" not in entry["path"]
    assert load(fresh)["files_digest"] == files_digest(files)


def test_dependency_versions_match_the_installed_ones(fresh: DatasetResult) -> None:
    dependencies = load(fresh)["dependencies"]
    assert dependencies == {
        "python": platform.python_version(),
        "faker": metadata.version("faker"),
        "openpyxl": metadata.version("openpyxl"),
        "pydantic": metadata.version("pydantic"),
    }


def test_manifest_has_no_timestamp_user_host_or_absolute_path(fresh: DatasetResult) -> None:
    text = (fresh.path / "manifest.json").read_text(encoding="utf-8")
    for needle in (str(fresh.path.parent), str(Path.cwd()), platform.node()):
        assert needle and needle not in text
    assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", text)  # an ISO timestamp
    assert not re.search(r"[A-Za-z]:\\\\", text)  # a Windows drive path
    assert not re.search(r'"/(home|Users|tmp|var)/', text)
    keys = set(json.loads(text))
    assert not keys & {"created", "created_at", "timestamp", "user", "host", "hostname"}


def test_manifest_is_serialized_stably(fresh: DatasetResult) -> None:
    text = (fresh.path / "manifest.json").read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert text == dumps(json.loads(text))
    assert '\n  "config": {' in text  # two-space indent
    top = [line.split('"')[1] for line in text.splitlines() if re.match(r'^  "', line)]
    assert top == sorted(top)


def test_the_same_config_twice_gives_byte_identical_manifests(tmp_path: Path) -> None:
    config = resolve_config("nightmare", 30, 5)
    first = generate_dataset(config, tmp_path / "a")
    second = generate_dataset(config, tmp_path / "b")
    assert (first.path / "manifest.json").read_bytes() == (
        second.path / "manifest.json"
    ).read_bytes()


def test_verify_passes_on_a_fresh_dataset(fresh: DatasetResult) -> None:
    assert verify_manifest(fresh.path) == []


def copy_of(fresh: DatasetResult, tmp_path: Path) -> Path:
    import shutil

    target = tmp_path / "copy"
    shutil.copytree(fresh.path, target)
    return target


def test_verify_reports_an_edited_file(fresh: DatasetResult, tmp_path: Path) -> None:
    root = copy_of(fresh, tmp_path)
    target = root / "exports" / "crm" / "crm_contacts.csv"
    data = bytearray(target.read_bytes())
    data[len(data) // 2] ^= 0x01  # same size, different bytes
    target.write_bytes(bytes(data))
    assert verify_manifest(root) == [
        Problem("changed", "exports/crm/crm_contacts.csv", "checksum differs from the manifest")
    ]


def test_verify_reports_a_resized_file(fresh: DatasetResult, tmp_path: Path) -> None:
    root = copy_of(fresh, tmp_path)
    target = root / "exports" / "crm" / "crm_contacts.csv"
    target.write_bytes(target.read_bytes() + b"x")
    (problem,) = verify_manifest(root)
    assert (problem.kind, problem.path) == ("changed", "exports/crm/crm_contacts.csv")
    assert problem.detail.startswith("size ")


def test_verify_reports_a_deleted_file(fresh: DatasetResult, tmp_path: Path) -> None:
    root = copy_of(fresh, tmp_path)
    (root / "exports" / "custodian" / "custodian_accounts.csv").unlink()
    assert [(p.kind, p.path) for p in verify_manifest(root)] == [
        ("missing", "exports/custodian/custodian_accounts.csv")
    ]


@pytest.mark.parametrize("folder", ["exports/crm", "truth"])
def test_verify_reports_an_added_file(fresh: DatasetResult, tmp_path: Path, folder: str) -> None:
    root = copy_of(fresh, tmp_path)
    (root / folder / "notes.txt").write_text("hello", encoding="utf-8")
    assert [(p.kind, p.path) for p in verify_manifest(root)] == [("extra", f"{folder}/notes.txt")]


def test_verify_reports_a_damaged_or_missing_manifest(fresh: DatasetResult, tmp_path: Path) -> None:
    root = copy_of(fresh, tmp_path)
    manifest = root / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["files_digest"] = "0" * 64
    manifest.write_text(json.dumps(data), encoding="utf-8")
    (problem,) = verify_manifest(root)
    assert problem.kind == "manifest"
    assert "files_digest" in problem.detail
    manifest.write_text("{not json", encoding="utf-8")
    assert verify_manifest(root)[0].kind == "manifest"
    manifest.unlink()
    assert verify_manifest(root)[0].kind == "manifest"


def test_verify_rejects_an_unknown_manifest_version(fresh: DatasetResult, tmp_path: Path) -> None:
    root = copy_of(fresh, tmp_path)
    manifest = root / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["manifest_version"] = 99
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert any("unsupported manifest_version" in p.detail for p in verify_manifest(root))


def test_truth_files_are_listed_when_a_writer_creates_them(tmp_path: Path) -> None:
    result = generate_dataset(
        resolve_config("clean", "sample", 1),
        tmp_path,
        answer_key_writers=[
            lambda c: (c.truth_dir / "key.json").write_text("{}", encoding="utf-8")
        ],
    )
    paths = [f["path"] for f in load(result)["files"]]  # type: ignore[attr-defined]
    assert "truth/key.json" in paths
    assert verify_manifest(result.path) == []


def test_changelog_exists_and_explains_the_version_rules() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    for word in ("Patch", "Minor", "Major", "GENERATOR_VERSION", f"## {GENERATOR_VERSION}"):
        assert word in text

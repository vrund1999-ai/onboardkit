import os
import subprocess
import sys
from pathlib import Path

import pytest

from onboardkit.datagen.config import apply_overrides, resolve_config
from onboardkit.datagen.mess.base import MessEvent
from onboardkit.datagen.pipeline import build_rows, generate_dataset
from onboardkit.datagen.standard import file_checksums


def tree(root: Path) -> dict[str, bytes]:
    """Every file under root, manifest included, with its bytes."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_two_runs_in_one_process_are_byte_identical(tmp_path: Path) -> None:
    config = resolve_config("nightmare", 40, 11)
    first = generate_dataset(config, tmp_path / "a")
    second = generate_dataset(config, tmp_path / "b")
    assert first.path.name == second.path.name
    assert tree(first.path) == tree(second.path)


def run_cli(out: Path, hashseed: str, cwd: Path) -> Path:
    env = {**os.environ, "PYTHONHASHSEED": hashseed}
    completed = subprocess.run(
        [sys.executable, "-m", "onboardkit.datagen", "generate", "--preset", "nightmare",
         "--size", "40", "--seed", "11", "--out", str(out), "--quiet"],
        cwd=cwd, env=env, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert completed.returncode == 0, completed.stderr
    return Path(completed.stdout.strip())


def test_separate_processes_with_different_hash_seeds_agree(tmp_path: Path) -> None:
    (tmp_path / "cwd1").mkdir()
    (tmp_path / "cwd2").mkdir()
    one = run_cli(tmp_path / "out one", "0", tmp_path / "cwd1")
    two = run_cli(tmp_path / "out two", "12345", tmp_path / "cwd2")
    assert one.parent != two.parent
    assert tree(one) == tree(two)


def test_output_does_not_depend_on_working_directory_or_output_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = resolve_config("typical", "sample", 3)
    here = generate_dataset(config, tmp_path / "root a")
    elsewhere = tmp_path / "other cwd"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    there = generate_dataset(config, Path("relative") / "root b")
    assert tree(here.path) == tree(there.path)


def test_a_third_run_after_overwrite_is_still_identical(tmp_path: Path) -> None:
    config = resolve_config("typical", "sample", 4)
    first = generate_dataset(config, tmp_path)
    before = tree(first.path)
    again = generate_dataset(config, tmp_path, overwrite=True)
    assert tree(again.path) == before


def test_xlsx_has_no_timestamp_dependence(tmp_path: Path) -> None:
    config = resolve_config("typical", "sample", 5)
    first = generate_dataset(config, tmp_path / "a")
    os.utime(first.path, (0, 0))
    second = generate_dataset(config, tmp_path / "b")
    book = "exports/book_of_business/book_of_business.xlsx"
    assert file_checksums(first.path)[book] == file_checksums(second.path)[book]


def test_csv_line_endings_are_pinned_per_source(tmp_path: Path) -> None:
    """Each export uses one fixed line ending, so Windows and Linux write the same bytes."""
    result = generate_dataset(resolve_config("typical", "sample", 6), tmp_path)
    crlf, lf = bytes([13, 10]), bytes([10])
    expected = {"custodian": crlf, "crm": lf}
    for source, ending in expected.items():
        files = list((result.path / "exports" / source).glob("*.csv"))
        assert files
        for path in files:
            data = path.read_bytes()
            assert data.endswith(ending)
            assert data.count(lf) == data.count(ending)  # no mixed endings
            assert bytes([13, 13]) not in data


def test_disabling_one_mess_type_leaves_the_other_types_events_unchanged() -> None:
    base = resolve_config("nightmare", 60, 8)
    muted = base.model_copy(update={"mess": apply_overrides(base.mess, ["balances=off"])})
    with_all = build_rows(base).mess_events
    without = build_rows(muted).mess_events

    def of(events: list[MessEvent], kind: str) -> list[MessEvent]:
        return [e for e in events if e.mess_type == kind]

    assert of(with_all, "balances")
    assert not of(without, "balances")
    for kind in ("names", "households", "formats"):
        assert of(with_all, kind)
        assert of(with_all, kind) == of(without, kind)

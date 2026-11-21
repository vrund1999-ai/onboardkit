import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from onboardkit.datagen import GENERATOR_VERSION
from onboardkit.datagen.cli import app
from onboardkit.datagen.config import dataset_id, resolve_config
from onboardkit.datagen.pipeline import generate_dataset

runner = CliRunner()
ANSI = re.compile(chr(27) + r"\[[0-9;]*m")  # CI may force colored help output


def invoke(*args: str) -> object:
    return runner.invoke(app, list(args))


def dataset_dirs(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir())


def test_generate_with_no_arguments_makes_the_default_typical_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["generate", "--quiet"])
    expected = dataset_id(resolve_config("typical", "default", 42))
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == str(Path("data") / "generated" / expected)
    assert (tmp_path / "data" / "generated" / expected / "manifest.json").is_file()


def test_small_clean_dataset_with_flags(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "generate",
            "--size",
            "sample",
            "--preset",
            "clean",
            "--seed",
            "7",
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    lines = dict(line.split(": ", 1) for line in result.stdout.splitlines())
    assert lines["dataset"] == dataset_id(resolve_config("clean", "sample", 7))
    assert lines["households"] == "15"
    assert lines["events.mess"] == "0"
    assert lines["events.coverage"] == "0"
    assert lines["path"] == str(tmp_path / lines["dataset"])


def test_mess_overrides_are_applied_and_repeatable(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["generate", "--size", "sample", "--preset", "clean", "--out", str(tmp_path),
         "--mess", "names=heavy", "--mess", "balances=0.2", "--quiet"],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    manifest = json.loads((Path(result.stdout.strip()) / "manifest.json").read_text("utf-8"))
    mess = manifest["config"]["mess"]
    assert mess["names"] == {"enabled": True, "intensity": 0.8}
    assert mess["balances"] == {"enabled": True, "intensity": 0.2}
    assert mess["formats"]["enabled"] is False
    assert manifest["counts"]["events.mess"] > 0


@pytest.mark.parametrize(
    ("args", "needles"),
    [
        (["--preset", "messy"], ["unknown preset 'messy'", "clean", "nightmare", "typical"]),
        (["--mess", "nmes=heavy"], ["unknown mess type 'nmes'", "names", "balances"]),
        (["--mess", "names=loud"], ["invalid level", "heavy"]),
        (["--mess", "names"], ["invalid override"]),
        (["--size", "huge"], ["unknown size 'huge'", "sample", "default"]),
        (["--size", "0"], ["greater than or equal to 1"]),
        (["--as-of", "yesterday"], ["Invalid isoformat"]),
        (["--config", "no-such-file.yaml"], ["config file not found"]),
    ],
)
def test_invalid_input_exits_2_and_lists_valid_values(
    tmp_path: Path, args: list[str], needles: list[str]
) -> None:
    result = runner.invoke(app, ["generate", "--out", str(tmp_path), *args])
    assert result.exit_code == 2, result.output
    for needle in needles:
        assert needle in result.output
    assert dataset_dirs(tmp_path) == []


def test_unknown_option_is_a_usage_error(tmp_path: Path) -> None:
    assert runner.invoke(app, ["generate", "--nope"]).exit_code == 2


def test_rerun_without_overwrite_exits_3_and_changes_nothing(tmp_path: Path) -> None:
    args = ["generate", "--size", "sample", "--preset", "clean", "--out", str(tmp_path), "--quiet"]
    first = runner.invoke(app, args)
    assert first.exit_code == 0
    manifest = Path(first.stdout.strip()) / "manifest.json"
    before = manifest.read_bytes()
    marker = manifest.parent / "marker.txt"
    marker.write_text("keep", encoding="utf-8")
    again = runner.invoke(app, args)
    assert again.exit_code == 3
    assert "--overwrite" in again.output
    assert marker.exists()
    assert manifest.read_bytes() == before
    assert len(dataset_dirs(tmp_path)) == 1
    replaced = runner.invoke(app, [*args, "--overwrite"])
    assert replaced.exit_code == 0
    assert not marker.exists()


def test_verify_exits_0_on_a_fresh_dataset_and_1_after_tampering(tmp_path: Path) -> None:
    result = generate_dataset(resolve_config("typical", "sample", 3), tmp_path)
    ok = runner.invoke(app, ["verify", str(result.path)])
    assert ok.exit_code == 0
    assert "ok" in ok.stdout
    target = result.path / "exports" / "crm" / "crm_contacts.csv"
    target.write_bytes(target.read_bytes() + b"tampered")
    (result.path / "truth" / "stray.txt").write_text("x", encoding="utf-8")
    bad = runner.invoke(app, ["verify", str(result.path)])
    assert bad.exit_code == 1
    assert "changed: exports/crm/crm_contacts.csv" in bad.stdout
    assert "extra: truth/stray.txt" in bad.stdout
    assert "2 problem(s) found" in bad.stdout


def test_verify_and_show_on_a_missing_directory_exit_2(tmp_path: Path) -> None:
    for command in ("verify", "show"):
        result = runner.invoke(app, [command, str(tmp_path / "nothing")])
        assert result.exit_code == 2
        assert "not a dataset directory" in result.output
    empty = tmp_path / "empty"
    empty.mkdir()
    assert runner.invoke(app, ["show", str(empty)]).exit_code == 2
    assert runner.invoke(app, ["verify", str(empty)]).exit_code == 1


def test_show_prints_the_manifest_summary(tmp_path: Path) -> None:
    result = generate_dataset(resolve_config("nightmare", "sample", 9), tmp_path)
    shown = runner.invoke(app, ["show", str(result.path)])
    assert shown.exit_code == 0
    lines = dict(line.split(": ", 1) for line in shown.stdout.splitlines())
    assert lines["dataset"] == result.dataset_id
    assert lines["preset"] == "nightmare"
    assert lines["seed"] == "9"
    assert lines["generator version"] == GENERATOR_VERSION
    assert lines["events.mess"] == str(result.mess_events)
    assert lines["events.coverage"] == str(result.coverage_events)
    assert lines["files"] == "16"
    assert lines["exports (what a firm delivers)"] == "4 files"
    assert lines["truth (INTERNAL, never part of a delivery)"] == "12 files"


def test_presets_lists_each_preset_with_its_mess_summary() -> None:
    result = runner.invoke(app, ["presets"])
    assert result.exit_code == 0
    text = result.stdout
    for name in ("clean", "typical", "nightmare"):
        assert f"{name}: " in text
    assert "mess: none" in text
    assert "names=0.5" in text
    assert "balances=0.9" in text


def test_config_file_values_are_overridden_by_flags(tmp_path: Path) -> None:
    config = tmp_path / "my config.yaml"
    config.write_text(
        "preset: clean\nsize: {households: 20}\nseed: 5\n"
        "mess:\n  names: {enabled: true, intensity: 0.4}\n",
        encoding="utf-8",
    )
    out = tmp_path / "out dir"
    base = runner.invoke(app, ["generate", "--config", str(config), "--out", str(out), "--quiet"])
    assert base.exit_code == 0, base.output
    manifest = json.loads((Path(base.stdout.strip()) / "manifest.json").read_text("utf-8"))
    assert manifest["config"]["size"]["households"] == 20
    assert manifest["config"]["seed"] == 5
    assert manifest["config"]["preset"] == "clean"
    assert manifest["config"]["mess"]["names"]["intensity"] == 0.4

    flags = [
        "generate", "--config", str(config), "--out", str(out), "--quiet",
        "--seed", "6", "--size", "sample", "--preset", "typical", "--mess", "names=0.1",
    ]  # fmt: skip
    over = runner.invoke(app, flags)
    assert over.exit_code == 0, over.output
    manifest = json.loads((Path(over.stdout.strip()) / "manifest.json").read_text("utf-8"))
    assert manifest["config"]["size"]["households"] == 15
    assert manifest["config"]["seed"] == 6
    assert manifest["config"]["preset"] == "typical"
    assert manifest["config"]["mess"]["names"]["intensity"] == 0.1


def test_config_file_with_unknown_keys_or_bad_values_exits_2(tmp_path: Path) -> None:
    bad_key = tmp_path / "a.yaml"
    bad_key.write_text("sized: 3\n", encoding="utf-8")
    result = runner.invoke(app, ["generate", "--config", str(bad_key), "--out", str(tmp_path)])
    assert result.exit_code == 2
    assert "unknown keys in config file: ['sized']" in result.output
    bad_value = tmp_path / "b.yaml"
    bad_value.write_text("mess: {names: {enabled: true, intensity: 3}}\n", encoding="utf-8")
    result = runner.invoke(app, ["generate", "--config", str(bad_value), "--out", str(tmp_path)])
    assert result.exit_code == 2
    not_mapping = tmp_path / "c.yaml"
    not_mapping.write_text("- 1\n- 2\n", encoding="utf-8")
    result = runner.invoke(app, ["generate", "--config", str(not_mapping)])
    assert result.exit_code == 2
    assert "must contain a mapping" in result.output


def test_paths_with_spaces_and_drive_letters_work(tmp_path: Path) -> None:
    out = tmp_path / "my data" / "out put"
    result = runner.invoke(
        app, ["generate", "--size", "sample", "--preset", "clean", "--out", str(out), "--quiet"]
    )
    assert result.exit_code == 0, result.output
    path = Path(result.stdout.strip())
    assert path.is_absolute() == out.is_absolute()
    assert (path / "manifest.json").is_file()
    assert runner.invoke(app, ["verify", str(path)]).exit_code == 0


def test_unexpected_errors_exit_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise ZeroDivisionError("kaput")

    monkeypatch.setattr("onboardkit.datagen.cli.generate_dataset", boom)
    result = runner.invoke(app, ["generate", "--size", "sample", "--out", str(tmp_path)])
    assert result.exit_code == 4
    assert "unexpected error: ZeroDivisionError: kaput" in result.output


@pytest.mark.parametrize("command", [None, "generate", "presets", "verify", "show"])
def test_help_documents_every_command_and_option(command: str | None) -> None:
    args = [command, "--help"] if command else ["--help"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    text = " ".join(ANSI.sub("", result.stdout).split())
    if command is None:
        for name in ("generate", "presets", "verify", "show"):
            assert name in text
    if command == "generate":
        for option in (
            "--preset", "--size", "--seed", "--mess", "--as-of",
            "--config", "--out", "--overwrite", "--quiet",
        ):  # fmt: skip
            assert option in text


def test_no_arguments_prints_help() -> None:
    result = runner.invoke(app, [])
    assert "generate" in result.output


def test_runs_as_a_module_from_any_directory(tmp_path: Path) -> None:
    out = tmp_path / "o"
    completed = subprocess.run(
        [sys.executable, "-m", "onboardkit.datagen", "generate", "--size", "sample",
         "--preset", "clean", "--out", str(out), "--quiet"],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert completed.returncode == 0, completed.stderr
    assert Path(completed.stdout.strip()).parent == out

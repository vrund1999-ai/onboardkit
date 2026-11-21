import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from onboardkit.datagen.answer_keys.checks import TRUTH_ID, check_truth
from onboardkit.datagen.answer_keys.summary import build_summary
from onboardkit.datagen.answer_keys.writer import read_table, write_table
from onboardkit.datagen.cli import app
from onboardkit.datagen.config import resolve_config
from onboardkit.datagen.manifest import Problem, verify_manifest
from onboardkit.datagen.pipeline import DatasetResult, generate_dataset

runner = CliRunner()
TRUTH_FILES = {
    "README.txt",
    "column_mappings.csv",
    "coverage_events.jsonl",
    "discrepancies.csv",
    "entities_not_exported.csv",
    "entity_groups.csv",
    "entity_matches.csv",
    "firm.json",
    "mess_events.jsonl",
    "provenance.csv",
    "source_id_map.csv",
    "summary.json",
}


@pytest.fixture(scope="module")
def base(tmp_path_factory: pytest.TempPathFactory) -> DatasetResult:
    return generate_dataset(resolve_config("typical", "sample", 42), tmp_path_factory.mktemp("t"))


@pytest.fixture
def copy(base: DatasetResult, tmp_path: Path) -> Path:
    target = tmp_path / "copy"
    shutil.copytree(base.path, target)
    return target


def details(problems: list[Problem]) -> str:
    return "\n".join(str(p) for p in problems)


def rewrite(path: Path, rows: list[dict[str, str]], header: list[str]) -> None:
    write_table(path, header, [[r[h] for h in header] for r in rows])


@pytest.mark.parametrize(
    ("preset", "size", "seed"),
    [
        ("clean", "sample", 1),
        ("typical", "sample", 7),
        ("nightmare", 60, 5),
        ("nightmare", "sample", 2),
    ],
)
def test_every_preset_dataset_has_the_full_truth_folder_and_passes(
    tmp_path: Path, preset: str, size: str | int, seed: int
) -> None:
    result = generate_dataset(resolve_config(preset, size, seed), tmp_path)
    assert {p.name for p in (result.path / "truth").iterdir()} == TRUTH_FILES
    assert check_truth(result.path) == []


def test_readme_carries_the_notice(base: DatasetResult) -> None:
    text = (base.path / "truth" / "README.txt").read_text(encoding="utf-8")
    assert text.startswith("INTERNAL ANSWER MATERIAL")
    lowered = text.lower()
    assert "synthetic" in lowered and "firm delivery" in lowered and "product pipeline" in lowered


def test_summary_counts_equal_independent_counts_from_the_files(base: DatasetResult) -> None:
    truth = base.path / "truth"
    summary = json.loads((truth / "summary.json").read_text(encoding="utf-8"))
    firm = json.loads((truth / "firm.json").read_text(encoding="utf-8"))
    assert summary["truth"] == {
        "persons": len(firm["people"]),
        "households": len(firm["households"]),
        "accounts": len(firm["accounts"]),
    }
    provenance = read_table(truth / "provenance.csv")
    for source, count in summary["rows"].items():
        assert count == sum(1 for r in provenance if r["source"] == source)
    discrepancies = read_table(truth / "discrepancies.csv")
    assert summary["discrepancies"]["total"] == len(discrepancies)
    for kind, by_severity in summary["discrepancies"]["by_kind_and_severity"].items():
        for severity, count in by_severity.items():
            assert count == sum(
                1 for r in discrepancies if (r["kind"], r["severity"]) == (kind, severity)
            )
    mess = (truth / "mess_events.jsonl").read_text(encoding="utf-8").splitlines()
    assert summary["mess_events"]["total"] == len(mess)
    for mess_type, count in summary["mess_events"]["by_type"].items():
        assert count == sum(1 for line in mess if json.loads(line)["mess_type"] == mess_type)
    groups = read_table(truth / "entity_groups.csv")
    for entity_type, by_level in summary["entity_groups"].items():
        for level, count in by_level.items():
            assert count == sum(
                1 for g in groups if (g["entity_type"], g["max_difficulty"]) == (entity_type, level)
            )
    assert summary["truth"]["persons"] == base.counts["persons"]
    assert summary["coverage_events"]["total"] == base.coverage_events
    assert summary["mess_events"]["total"] == base.mess_events


def test_summary_json_is_sorted_with_no_carriage_returns(base: DatasetResult) -> None:
    text = (base.path / "truth" / "summary.json").read_text(encoding="utf-8")
    assert text.endswith("\n") and "\r" not in text
    assert json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n" == text
    assert callable(build_summary)


def test_firm_json_is_the_complete_truth_and_never_in_exports(base: DatasetResult) -> None:
    firm = json.loads((base.path / "truth" / "firm.json").read_text(encoding="utf-8"))
    assert {"people", "households", "accounts"} <= set(firm)
    assert not list((base.path / "exports").rglob("firm.json"))


def test_exports_contain_no_truth_identifier(base: DatasetResult) -> None:
    for path in (base.path / "exports").rglob("*.csv"):
        assert not TRUTH_ID.search(path.read_text(encoding="utf-8-sig")), path


def test_a_truth_id_in_an_export_is_a_leak(copy: Path) -> None:
    target = copy / "exports" / "crm" / "crm_contacts.csv"
    target.write_text(target.read_text(encoding="utf-8") + "x,ACCT-000001\n", encoding="utf-8")
    problems = check_truth(copy)
    assert any(p.kind == "leak" and "ACCT-000001" in p.detail for p in problems)


def test_a_source_id_that_embeds_a_truth_id_is_a_leak(copy: Path) -> None:
    path = copy / "truth" / "source_id_map.csv"
    rows = read_table(path)
    rows[0]["source_id"] = f"X{rows[0]['truth_id']}"
    rewrite(path, rows, list(rows[0]))
    assert any(p.kind == "leak" for p in check_truth(copy))


def test_missing_files_and_unparsable_files_are_reported(copy: Path) -> None:
    (copy / "truth" / "discrepancies.csv").unlink()
    (copy / "truth" / "firm.json").write_text("{", encoding="utf-8")
    text = details(check_truth(copy))
    assert "discrepancies.csv: required file is missing" in text
    assert "firm.json: cannot parse" in text


def test_removing_a_provenance_row_is_detected(copy: Path) -> None:
    path = copy / "truth" / "provenance.csv"
    rows = read_table(path)
    gone = rows.pop(0)
    rewrite(path, rows, list(gone))
    assert gone["row_uid"] in details(check_truth(copy))


def test_altering_a_truth_id_is_detected(copy: Path) -> None:
    path = copy / "truth" / "entity_matches.csv"
    rows = read_table(path)
    rows[0]["truth_id"] = "P-99999" if rows[0]["entity_type"] == "person" else "ZZ-0"
    rewrite(path, rows, list(rows[0]))
    assert "unknown" in details(check_truth(copy))


def test_a_changed_summary_count_is_detected(copy: Path) -> None:
    path = copy / "truth" / "summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["truth"]["accounts"] += 1
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert "truth counts differ" in details(check_truth(copy))


def test_an_entity_in_no_group_is_detected(copy: Path) -> None:
    path = copy / "truth" / "entity_groups.csv"
    rows = read_table(path)
    gone = next(r for r in rows if r["entity_type"] == "household")
    rows.remove(gone)
    rewrite(path, rows, list(gone))
    assert f"{gone['truth_id']} is in no group" in details(check_truth(copy))


def test_unsorted_rows_are_detected(copy: Path) -> None:
    path = copy / "truth" / "provenance.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[1], lines[2] = lines[2], lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert "not in the expected sorted order" in details(check_truth(copy))


def test_a_dropped_discrepancy_that_events_explain_is_detected(copy: Path) -> None:
    path = copy / "truth" / "discrepancies.csv"
    rows = read_table(path)
    gone = next(r for r in rows if r["kind"] == "missing_in_source")
    rows.remove(gone)
    rewrite(path, rows, list(gone))
    assert "is not listed" in details(check_truth(copy))


def test_a_discrepancy_citing_an_unknown_event_is_detected(copy: Path) -> None:
    path = copy / "truth" / "discrepancies.csv"
    rows = read_table(path)
    rows[0]["origin_events"] = "cov:omitted:nowhere"
    rewrite(path, rows, list(rows[0]))
    assert "cites unknown event" in details(check_truth(copy))


def test_a_wrong_column_mapping_is_detected(copy: Path) -> None:
    path = copy / "truth" / "column_mappings.csv"
    rows = read_table(path)
    next(r for r in rows if r["header"] == "zip")["header"] = "postcode"
    header = list(rows[0])
    write_table(
        path,
        header,
        [[r[h] for h in header] for r in rows],
        key=lambda row: (row[0], row[1], row[2], int(row[3])),
    )
    assert any(p.kind == "mapping" for p in check_truth(copy))


def test_a_missing_notice_is_detected(copy: Path) -> None:
    (copy / "truth" / "README.txt").write_text("hello\n", encoding="utf-8")
    assert "notice is missing" in details(check_truth(copy))


def test_verify_detects_changes_to_truth_files(copy: Path) -> None:
    assert verify_manifest(copy) == []
    path = copy / "truth" / "summary.json"
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    problems = verify_manifest(copy)
    assert [(p.kind, p.path) for p in problems] == [("changed", "truth/summary.json")]


def test_cli_check_passes_and_fails_with_exit_one(base: DatasetResult, copy: Path) -> None:
    ok = runner.invoke(app, ["check", str(base.path)])
    assert ok.exit_code == 0 and "ok:" in ok.stdout
    (copy / "truth" / "README.txt").write_text("hello\n", encoding="utf-8")
    bad = runner.invoke(app, ["check", str(copy)])
    assert bad.exit_code == 1
    assert "truth: truth/README.txt" in bad.stdout and "problem(s) found" in bad.stdout
    missing = runner.invoke(app, ["check", str(copy / "nope")])
    assert missing.exit_code == 2


def test_cli_show_labels_truth_as_internal(base: DatasetResult) -> None:
    shown = runner.invoke(app, ["show", str(base.path)])
    assert "truth (INTERNAL, never part of a delivery): 12 files" in shown.stdout
    helped = runner.invoke(app, ["generate", "--help"])
    assert "internal" in helped.stdout.lower()

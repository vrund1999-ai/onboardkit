import csv
import hashlib
import json
import re
from pathlib import Path

import openpyxl
import pytest

from onboardkit.datagen import pipeline
from onboardkit.datagen.config import available_presets, dataset_id, resolve_config
from onboardkit.datagen.pipeline import (
    AnswerKeyContext,
    DatasetExistsError,
    DatasetResult,
    generate_dataset,
)
from onboardkit.datagen.sources.book_of_business import BookOfBusinessExporter

TRUTH_ID = re.compile(r"(?<![A-Za-z0-9])(?:P-\d{5}|HH-\d{4}|ACCT-\d{6}|HOLD-\d{6}|SEC-\d{3})")
EXPECTED_FILES = [
    "exports/custodian/custodian_accounts.csv",
    "exports/custodian/custodian_positions.csv",
    "exports/crm/crm_contacts.csv",
    "exports/crm/crm_linked_accounts.csv",
    "exports/book_of_business/book_of_business.xlsx",
    "manifest.json",
    "truth/README.txt",
    "truth/column_mappings.csv",
    "truth/coverage_events.jsonl",
    "truth/discrepancies.csv",
    "truth/entities_not_exported.csv",
    "truth/entity_groups.csv",
    "truth/entity_matches.csv",
    "truth/firm.json",
    "truth/mess_events.jsonl",
    "truth/provenance.csv",
    "truth/source_id_map.csv",
    "truth/summary.json",
]


def files_under(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def csv_data_rows(path: Path, first_header: str) -> int:
    """Rows between the header line and the end, ignoring titles and trailers."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    start = next(i for i, row in enumerate(rows) if row and row[0] == first_header)
    width = len(rows[start])
    return sum(1 for row in rows[start + 1 :] if len(row) == width)


def book_rows(path: Path) -> int:
    workbook = openpyxl.load_workbook(path)
    total = 0
    for sheet in workbook.worksheets:
        if sheet.title == "Summary":
            continue
        total += sum(1 for row in sheet.iter_rows(min_row=6) if row[2].value not in (None, ""))
    return total


def disk_counts(result: DatasetResult) -> dict[str, int]:
    exports = result.path / "exports"
    return {
        "rows.custodian": csv_data_rows(exports / "custodian" / "custodian_accounts.csv", "Acct #")
        + csv_data_rows(exports / "custodian" / "custodian_positions.csv", "Acct #"),
        "rows.crm": csv_data_rows(exports / "crm" / "crm_contacts.csv", "contact_id")
        + csv_data_rows(exports / "crm" / "crm_linked_accounts.csv", "contact_id"),
        "rows.book_of_business": book_rows(exports / "book_of_business" / "book_of_business.xlsx"),
    }


@pytest.mark.parametrize("preset", ["clean", "typical", "nightmare"])
def test_layout_for_the_sample_size_of_every_preset(preset: str, tmp_path: Path) -> None:
    config = resolve_config(preset, "sample", 42)
    result = generate_dataset(config, tmp_path)
    assert result.dataset_id == dataset_id(config)
    assert result.path == tmp_path / result.dataset_id
    assert files_under(result.path) == sorted(EXPECTED_FILES)
    assert (result.path / "truth").is_dir()
    assert [p.name for p in tmp_path.iterdir()] == [result.dataset_id]  # no staging leftovers
    manifest = json.loads((result.path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dataset_id"] == result.dataset_id


@pytest.mark.slow
def test_layout_for_the_default_size(tmp_path: Path) -> None:
    result = generate_dataset(resolve_config("typical", "default", 42), tmp_path)
    assert files_under(result.path) == sorted(EXPECTED_FILES)
    assert result.counts["households"] == 300


@pytest.mark.parametrize("preset", available_presets())
def test_result_counts_equal_what_is_on_disk(preset: str, tmp_path: Path) -> None:
    result = generate_dataset(resolve_config(preset, 40, 42), tmp_path)
    on_disk = disk_counts(result)
    assert {k: result.counts[k] for k in on_disk} == on_disk
    assert result.counts["households"] == 40
    assert result.counts["persons"] > 40
    assert result.counts["accounts"] > 40
    assert (result.coverage_events == 0) == (preset == "clean")
    assert (result.mess_events == 0) == (preset == "clean")


@pytest.mark.parametrize("preset", ["clean", "nightmare"])
def test_no_export_contains_a_truth_identifier(preset: str, tmp_path: Path) -> None:
    result = generate_dataset(resolve_config(preset, 60, 42), tmp_path)
    exports = result.path / "exports"
    scanned = 0
    for path in sorted(exports.rglob("*.csv")):
        assert not TRUTH_ID.search(path.read_bytes().decode("utf-8")), path.name
        scanned += 1
    workbook = openpyxl.load_workbook(exports / "book_of_business" / "book_of_business.xlsx")
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows(values_only=True):
            for value in row:
                assert not (isinstance(value, str) and TRUTH_ID.search(value))
    assert scanned == 4


def test_a_failure_mid_run_leaves_no_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self: BookOfBusinessExporter, rows: object, out_dir: Path) -> None:
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(BookOfBusinessExporter, "write", boom)
    config = resolve_config("typical", "sample", 42)
    with pytest.raises(RuntimeError, match="disk on fire"):
        generate_dataset(config, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_a_failing_answer_key_writer_also_leaves_nothing(tmp_path: Path) -> None:
    def broken(context: AnswerKeyContext) -> None:
        (context.truth_dir / "partial.json").write_text("{", encoding="utf-8")
        raise ValueError("bad key")

    with pytest.raises(ValueError, match="bad key"):
        generate_dataset(
            resolve_config("clean", "sample", 1), tmp_path, answer_key_writers=[broken]
        )
    assert list(tmp_path.iterdir()) == []


def test_a_failed_overwrite_keeps_the_existing_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = resolve_config("clean", "sample", 3)
    first = generate_dataset(config, tmp_path)
    before = files_under(first.path)

    def boom(self: BookOfBusinessExporter, rows: object, out_dir: Path) -> None:
        raise RuntimeError("late failure")

    monkeypatch.setattr(BookOfBusinessExporter, "write", boom)
    with pytest.raises(RuntimeError):
        generate_dataset(config, tmp_path, overwrite=True)
    assert files_under(first.path) == before
    assert [p.name for p in tmp_path.iterdir()] == [first.dataset_id]


def test_rerun_without_overwrite_raises_and_with_overwrite_replaces(tmp_path: Path) -> None:
    config = resolve_config("clean", "sample", 5)
    first = generate_dataset(config, tmp_path)
    marker = first.path / "stale.txt"
    marker.write_text("old", encoding="utf-8")
    with pytest.raises(DatasetExistsError, match=first.dataset_id):
        generate_dataset(config, tmp_path)
    assert marker.exists()

    again = generate_dataset(config, tmp_path, overwrite=True)
    assert again.path == first.path
    assert not marker.exists()
    assert files_under(again.path) == sorted(EXPECTED_FILES)
    assert [p.name for p in tmp_path.iterdir()] == [first.dataset_id]


def hash_tree(root: Path) -> dict[str, str]:
    return {rel: hashlib.sha256((root / rel).read_bytes()).hexdigest() for rel in files_under(root)}


def test_the_same_config_gives_byte_identical_files_regardless_of_cwd_and_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = resolve_config("typical", "sample", 11)
    first = generate_dataset(config, tmp_path / "a")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    second = generate_dataset(config, tmp_path / "b")
    assert hash_tree(first.path) == hash_tree(second.path)
    assert list(elsewhere.iterdir()) == []  # nothing written relative to the cwd


def test_default_output_root_is_data_generated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = generate_dataset(resolve_config("clean", "sample", 2))
    assert result.path == Path("data") / "generated" / result.dataset_id
    assert (tmp_path / result.path / "manifest.json").is_file()


def test_answer_key_writers_receive_the_truth_locators_and_events(tmp_path: Path) -> None:
    seen: list[AnswerKeyContext] = []

    def writer(context: AnswerKeyContext) -> None:
        seen.append(context)
        (context.truth_dir / "events.json").write_text(
            json.dumps(
                {"mess": len(context.mess_events), "coverage": len(context.coverage_events)}
            ),
            encoding="utf-8",
        )

    result = generate_dataset(
        resolve_config("nightmare", 30, 42), tmp_path, answer_key_writers=[writer]
    )
    (context,) = seen
    assert context.firm.households
    assert set(context.locators) == {"custodian", "crm", "book_of_business"}
    assert all(context.locators[s] for s in context.locators)
    assert context.source_id_maps["crm"] is not None
    written = json.loads((result.path / "truth" / "events.json").read_text(encoding="utf-8"))
    assert written == {"mess": result.mess_events, "coverage": result.coverage_events}
    assert pipeline.TRUTH == "truth"


def test_locators_point_at_real_rows(tmp_path: Path) -> None:
    seen: list[AnswerKeyContext] = []
    result = generate_dataset(
        resolve_config("typical", 30, 42), tmp_path, answer_key_writers=[seen.append]
    )
    locators = seen[0].locators["custodian"]
    path = result.path / "exports" / "custodian" / "custodian_accounts.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        lines = list(csv.reader(handle))
    for locator in list(locators.values())[:10]:
        assert locator.file == "custodian_accounts.csv"
        assert lines[locator.row_number - 1][0].startswith("MC")

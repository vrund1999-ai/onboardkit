import csv
import shutil
from pathlib import Path

import pytest

from onboardkit.datagen.answer_keys.provenance import (
    ORIGINS,
    PROVENANCE_FILE,
    PROVENANCE_HEADER,
    SOURCE_ID_HEADER,
    SOURCE_ID_MAP_FILE,
    verify_provenance,
    write_provenance,
)
from onboardkit.datagen.answer_keys.writer import read_table, write_table
from onboardkit.datagen.config import resolve_config
from onboardkit.datagen.pipeline import DatasetResult, generate_dataset

PRESETS = ["clean", "typical", "nightmare"]
WRITERS = [write_provenance]


def make(tmp_path: Path, preset: str, size: str | int = "sample", seed: int = 42) -> DatasetResult:
    return generate_dataset(
        resolve_config(preset, size, seed), tmp_path, answer_key_writers=WRITERS
    )


def provenance(result: DatasetResult) -> list[dict[str, str]]:
    return read_table(result.path / "truth" / PROVENANCE_FILE)


def exported_rows(result: DatasetResult, relative: str) -> list[dict[str, str]]:
    path = result.path / "exports" / relative
    with path.open(encoding="utf-8-sig", newline="") as handle:
        text = handle.read()
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("contact_id"))
    return list(csv.DictReader(lines[start:]))


@pytest.fixture(scope="module")
def nightmare(tmp_path_factory: pytest.TempPathFactory) -> DatasetResult:
    return make(tmp_path_factory.mktemp("prov"), "nightmare", 120, 3)


@pytest.mark.parametrize("preset", PRESETS)
def test_locators_verify_and_counts_match_for_every_preset(tmp_path: Path, preset: str) -> None:
    result = make(tmp_path, preset)
    assert verify_provenance(result.path) == []
    records = provenance(result)
    assert tuple(records[0]) == PROVENANCE_HEADER
    by_source = {s: sum(r["source"] == s for r in records) for s in ("custodian", "crm")}
    assert by_source["custodian"] == result.counts["rows.custodian"]
    assert by_source["crm"] == result.counts["rows.crm"]
    book = sum(r["source"] == "book_of_business" for r in records)
    assert book == result.counts["rows.book_of_business"]
    assert len(records) == sum(v for k, v in result.counts.items() if k.startswith("rows."))
    assert len({r["row_uid"] for r in records}) == len(records)
    assert {r["origin"] for r in records} <= set(ORIGINS)


def test_records_are_sorted_and_one_per_row_in_every_file(nightmare: DatasetResult) -> None:
    records = provenance(nightmare)
    assert [r["row_uid"] for r in records] == sorted(r["row_uid"] for r in records)
    assert verify_provenance(nightmare.path) == []  # also proves no unrecorded rows remain
    files = {r["file"] for r in records}
    assert files == {
        "custodian/custodian_accounts.csv",
        "crm/crm_contacts.csv",
        "crm/crm_linked_accounts.csv",
        "book_of_business/book_of_business.xlsx",
    }


def test_workbook_records_name_advisor_sheets_and_the_archive(nightmare: DatasetResult) -> None:
    sheets = {r["sheet"] for r in provenance(nightmare) if r["source"] == "book_of_business"}
    assert "" not in sheets
    assert any(s.startswith("Advisor") or s != "Archive" for s in sheets)
    assert len(sheets) >= 2
    assert all(r["sheet"] == "" for r in provenance(nightmare) if r["source"] != "book_of_business")


def test_household_mess_rows_and_stale_extras_carry_their_origin() -> None:
    import tempfile

    found: dict[str, dict[str, str]] = {}
    for seed in range(1, 6):
        with tempfile.TemporaryDirectory() as tmp:
            result = make(Path(tmp), "nightmare", 150, seed)
            for record in provenance(result):
                found.setdefault(record["origin"], record)
            assert verify_provenance(result.path) == []
        if {"duplicate", "split", "stale_extra"} <= set(found):
            break
    assert {"duplicate", "split", "stale_extra"} <= set(found)
    assert found["duplicate"]["row_uid"].endswith("-dup")
    assert found["duplicate"]["table"] == "contacts"
    assert found["split"]["source"] == "crm"
    assert found["stale_extra"]["account_id"] == ""
    assert found["stale_extra"]["source"] == "book_of_business"
    assert found["duplicate"]["person_ids"] and found["duplicate"]["household_id"]


def test_projected_account_rows_carry_truth_refs(tmp_path: Path) -> None:
    records = provenance(make(tmp_path, "clean"))
    custodian = [r for r in records if r["source"] == "custodian"]
    assert all(r["account_id"].startswith("ACCT-") for r in custodian)
    assert all(r["origin"] == "projected" for r in records)
    assert all(r["source_keys"].startswith("Acct #=") for r in custodian)
    contact = next(r for r in records if r["table"] == "contacts")
    assert contact["source_keys"].startswith("contact_id=C")
    assert "|household_id=H" in contact["source_keys"]


def test_source_id_map_has_every_crm_id_including_duplicates(nightmare: DatasetResult) -> None:
    mapping = read_table(nightmare.path / "truth" / SOURCE_ID_MAP_FILE)
    assert tuple(mapping[0]) == SOURCE_ID_HEADER
    crm = {
        (m["entity_type"], m["source_id"]): m["truth_id"] for m in mapping if m["source"] == "crm"
    }
    contacts = exported_rows(nightmare, "crm/crm_contacts.csv")
    for row in contacts:
        assert ("person", row["contact_id"]) in crm
        if row["household_id"]:
            assert ("household", row["household_id"]) in crm
    duplicates = [r for r in provenance(nightmare) if r["origin"] == "duplicate"]
    assert duplicates
    truth_households: dict[str, set[str]] = {}
    for (entity, source_id), truth_id in crm.items():
        if entity == "household":
            truth_households.setdefault(truth_id, set()).add(source_id)
    assert any(len(ids) > 1 for ids in truth_households.values())  # several ids, one truth id
    assert len({tuple(r.values()) for r in mapping}) == len(mapping)
    assert [tuple(m.values()) for m in mapping] == sorted(tuple(m.values()) for m in mapping)


def test_account_numbers_map_back_to_truth_accounts(tmp_path: Path) -> None:
    result = make(tmp_path, "clean")
    mapping = read_table(result.path / "truth" / SOURCE_ID_MAP_FILE)
    accounts = [m for m in mapping if m["entity_type"] == "account"]
    assert {m["source"] for m in accounts} == {"custodian", "crm", "book_of_business"}
    assert all(m["truth_id"].startswith("ACCT-") for m in accounts)


def test_output_is_byte_identical_across_runs(tmp_path: Path) -> None:
    first = make(tmp_path / "a", "nightmare", 60, 9)
    second = make(tmp_path / "b", "nightmare", 60, 9)
    for name in (PROVENANCE_FILE, SOURCE_ID_MAP_FILE):
        one = (first.path / "truth" / name).read_bytes()
        assert one == (second.path / "truth" / name).read_bytes()
        assert b"\r" not in one


def test_provenance_exists_only_under_truth_and_exports_are_unchanged(tmp_path: Path) -> None:
    config = resolve_config("typical", "sample", 42)
    with_keys = generate_dataset(config, tmp_path / "a", answer_key_writers=WRITERS)
    without = generate_dataset(config, tmp_path / "b")
    new = {
        p.relative_to(with_keys.path).as_posix() for p in with_keys.path.rglob("*") if p.is_file()
    } - {p.relative_to(without.path).as_posix() for p in without.path.rglob("*") if p.is_file()}
    assert new == {f"truth/{PROVENANCE_FILE}", f"truth/{SOURCE_ID_MAP_FILE}"}
    for rel in (p for p in without.path.rglob("*") if p.is_file() and "exports" in p.parts):
        twin = with_keys.path / rel.relative_to(without.path)
        assert rel.read_bytes() == twin.read_bytes()
    exports_text = " ".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in (with_keys.path / "exports").rglob("*.csv")
    )
    assert "row_uid" not in exports_text
    assert "origin" not in exports_text


def copy_dataset(result: DatasetResult, tmp_path: Path) -> Path:
    target = tmp_path / "copy"
    shutil.copytree(result.path, target)
    return target


def rewrite(root: Path, edit: object) -> None:
    path = root / "truth" / PROVENANCE_FILE
    records = read_table(path)
    assert callable(edit)
    edit(records)
    write_table(path, PROVENANCE_HEADER, [[r[h] for h in PROVENANCE_HEADER] for r in records])


@pytest.mark.parametrize("source", ["custodian", "crm", "book_of_business"])
def test_shifting_a_locator_by_one_is_reported(
    nightmare: DatasetResult, tmp_path: Path, source: str
) -> None:
    root = copy_dataset(nightmare, tmp_path)
    victim: dict[str, str] = {}

    def shift(records: list[dict[str, str]]) -> None:
        record = next(r for r in records if r["source"] == source)
        record["row_number"] = str(int(record["row_number"]) + 1)
        victim.update(record)

    rewrite(root, shift)
    problems = verify_provenance(root)
    assert any(p.kind == "locator" and p.path == victim["row_uid"] for p in problems), problems


def test_a_dropped_record_leaves_an_unrecorded_row(
    nightmare: DatasetResult, tmp_path: Path
) -> None:
    root = copy_dataset(nightmare, tmp_path)
    rewrite(root, lambda records: records.pop(len(records) // 2))
    problems = verify_provenance(root)
    assert [p.kind for p in problems] == ["unrecorded"]


def test_an_edited_cell_is_reported(nightmare: DatasetResult, tmp_path: Path) -> None:
    root = copy_dataset(nightmare, tmp_path)
    target = root / "exports" / "crm" / "crm_contacts.csv"
    first_id = exported_rows(nightmare, "crm/crm_contacts.csv")[0]["contact_id"]
    target.write_text(
        target.read_text(encoding="utf-8").replace(first_id, "C000000", 1), encoding="utf-8"
    )
    problems = verify_provenance(root)
    assert any(p.kind == "locator" for p in problems)
    assert any("found 'C000000'" in p.detail for p in problems)


def test_missing_provenance_or_export_file_is_reported(
    nightmare: DatasetResult, tmp_path: Path
) -> None:
    root = copy_dataset(nightmare, tmp_path)
    (root / "exports" / "custodian" / "custodian_accounts.csv").unlink()
    assert any(p.kind == "missing" for p in verify_provenance(root))
    (root / "truth" / PROVENANCE_FILE).unlink()
    (problem,) = verify_provenance(root)
    assert (problem.kind, problem.path) == ("missing", f"truth/{PROVENANCE_FILE}")


def test_two_records_at_one_location_are_reported(nightmare: DatasetResult, tmp_path: Path) -> None:
    root = copy_dataset(nightmare, tmp_path)

    def collide(records: list[dict[str, str]]) -> None:
        same = [r for r in records if r["file"] == "custodian/custodian_accounts.csv"]
        same[1]["row_number"] = same[0]["row_number"]

    rewrite(root, collide)
    assert any("also used by" in p.detail for p in verify_provenance(root))


def test_write_table_sorts_rows_and_uses_unix_line_endings(tmp_path: Path) -> None:
    path = tmp_path / "t.csv"
    assert write_table(path, ["a", "b"], [["z", "é"], ["a", "1,2"]]) == 2
    data = path.read_bytes()
    assert data == 'a,b\na,"1,2"\nz,é\n'.encode()

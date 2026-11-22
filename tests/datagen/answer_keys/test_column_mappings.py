import shutil
from pathlib import Path

import pytest
from openpyxl import load_workbook

from onboardkit.datagen.answer_keys.column_mappings import (
    COLUMN_MAPPINGS_FILE,
    HEADER,
    NO_CONCEPT,
    describe_format,
    verify_column_mappings,
    write_column_mappings,
)
from onboardkit.datagen.answer_keys.writer import read_table, write_table
from onboardkit.datagen.config import resolve_config
from onboardkit.datagen.pipeline import DatasetResult, build_rows, generate_dataset
from onboardkit.datagen.sources.base import ColumnSpec, known_concepts

WRITERS = [write_column_mappings]


def make(
    tmp_path: Path, preset: str = "typical", size: str | int = "sample", seed: int = 42
) -> DatasetResult:
    return generate_dataset(
        resolve_config(preset, size, seed), tmp_path, answer_key_writers=WRITERS
    )


def key(result: DatasetResult) -> list[dict[str, str]]:
    return read_table(result.path / "truth" / COLUMN_MAPPINGS_FILE)


@pytest.fixture(scope="module")
def sample(tmp_path_factory: pytest.TempPathFactory) -> DatasetResult:
    return make(tmp_path_factory.mktemp("cm"))


def actual_columns(result: DatasetResult) -> dict[tuple[str, str], list[str]]:
    """Header cells of every file and sheet, read straight from the exported files."""
    found: dict[tuple[str, str], list[str]] = {}
    exports = result.path / "exports"
    for path in sorted(exports.rglob("*.csv")):
        text = path.read_text(encoding="utf-8-sig").splitlines()
        header = {
            "custodian_accounts.csv": 2,  # two preamble lines
            "custodian_positions.csv": 2,
            "crm_contacts.csv": 0,
            "crm_linked_accounts.csv": 0,
        }[path.name]
        found[(path.relative_to(exports).as_posix(), "")] = text[header].replace('"', "").split(",")
    workbook = load_workbook(exports / "book_of_business" / "book_of_business.xlsx", read_only=True)
    for sheet in workbook.sheetnames:
        cells = next(iter(workbook[sheet].iter_rows(min_row=5, max_row=5, values_only=True)))
        found[("book_of_business/book_of_business.xlsx", sheet)] = [
            str(c) for c in cells if c is not None
        ]
    workbook.close()
    return found


def test_every_column_of_every_file_and_sheet_has_exactly_one_row(sample: DatasetResult) -> None:
    rows = key(sample)
    assert tuple(rows[0]) == HEADER
    expected = actual_columns(sample)
    assert len(rows) == sum(len(headers) for headers in expected.values())
    for (file, sheet), headers in expected.items():
        mine = sorted(
            (r for r in rows if (r["file"], r["sheet"]) == (file, sheet)),
            key=lambda r: int(r["column_position"]),
        )
        assert [r["header"] for r in mine] == headers
        assert [int(r["column_position"]) for r in mine] == list(range(1, len(headers) + 1))
    assert len({(r["file"], r["sheet"], r["column_position"]) for r in rows}) == len(rows)


def test_files_and_sheets_covered(sample: DatasetResult) -> None:
    pairs = {(r["file"], r["sheet"]) for r in key(sample)}
    assert pairs >= {
        ("custodian/custodian_accounts.csv", ""),
        ("crm/crm_contacts.csv", ""),
        ("crm/crm_linked_accounts.csv", ""),
        ("book_of_business/book_of_business.xlsx", "Summary"),
        ("book_of_business/book_of_business.xlsx", "Archive"),
    }
    advisors = {s for _, s in pairs if s.startswith("Advisor - ")}
    built = build_rows(sample.config)
    assert advisors == {f"Advisor - {a.name}" for a in built.firm.profile.advisors}


def test_every_concept_exists_in_the_catalogue_or_is_none(sample: DatasetResult) -> None:
    known = known_concepts()
    for row in key(sample):
        assert row["concept"] == NO_CONCEPT or row["concept"] in known


def test_account_number_columns_all_map_to_account_number(sample: DatasetResult) -> None:
    by_header = {
        r["header"]: r["concept"]
        for r in key(sample)
        if r["file"] != "custodian/custodian_positions.csv"
    }
    assert by_header["Acct #"] == "account.number"
    assert by_header["account_number"] == "account.number"
    assert by_header["AcctNo"] == "account.number"


def test_owner_columns_are_slices_of_owner_names(sample: DatasetResult) -> None:
    owners = [r for r in key(sample) if r["concept"] == "account.owner_names"]
    assert [(r["header"], r["slice"]) for r in owners] == [("Owner 1", "0"), ("Owner 2", "1")]
    assert all(r["slice"] == "" for r in key(sample) if r["concept"] != "account.owner_names")


def test_summary_columns_are_unmapped_with_a_note(sample: DatasetResult) -> None:
    summary = [r for r in key(sample) if r["sheet"] == "Summary"]
    assert [r["header"] for r in summary] == ["Advisor", "Households", "Total Balance"]
    assert {r["concept"] for r in summary} == {NO_CONCEPT}
    assert all("summary sheet" in r["notes"] for r in summary)


def test_notes_flag_header_rows_and_continuation_blanks(sample: DatasetResult) -> None:
    rows = key(sample)
    custodian = [r for r in rows if r["source"] == "custodian"]
    assert all(r["notes"] == "header on row 3" for r in custodian)
    assert all(r["notes"] == "" for r in rows if r["source"] == "crm")
    household = next(
        r for r in rows if r["sheet"].startswith("Advisor") and r["header"] == "Household"
    )
    assert household["notes"] == "header on row 5; blank on continuation rows of a household block"


def test_value_formats_name_the_formatter(sample: DatasetResult) -> None:
    formats = {(r["source"], r["header"]): r["value_format"] for r in key(sample)}
    assert formats[("custodian", "Open Date")] == "date:%m/%d/%Y"
    assert formats[("custodian", "Value As Of")] == "date:%Y%m%d"
    assert formats[("custodian", "Market Value")] == "money:commas"
    assert formats[("crm", "date_of_birth")] == "date"
    assert formats[("crm", "phone")] == "phone"
    assert formats[("custodian", "Owner 1")] == "name_last_first:index=0,upper=True"
    assert formats[("custodian", "Acct Type")] == "map:codes=6"


def test_describe_format_cases() -> None:
    def column(formatter: str, **options: object) -> ColumnSpec:
        return ColumnSpec(
            concept="account.number", header="h", formatter=formatter, options=options
        )

    assert describe_format(column("passthrough")) == "passthrough"
    assert describe_format(column("date", pattern="%d")) == "date:%d"
    assert describe_format(column("money", style="number")) == "money:number"
    assert describe_format(column("map", mapping={"a": "b"})) == "map:codes=1"
    assert describe_format(column("x", b=2, a=1)) == "x:a=1,b=2"


def test_the_key_is_the_same_for_any_seed_and_byte_identical_across_runs(tmp_path: Path) -> None:
    one = make(tmp_path / "a", "typical", "sample", 1)
    two = make(tmp_path / "b", "typical", "sample", 2)
    again = make(tmp_path / "c", "typical", "sample", 1)
    first = (one.path / "truth" / COLUMN_MAPPINGS_FILE).read_bytes()
    assert first == (two.path / "truth" / COLUMN_MAPPINGS_FILE).read_bytes()
    assert first == (again.path / "truth" / COLUMN_MAPPINGS_FILE).read_bytes()
    assert b"\r" not in first


def test_the_key_is_the_same_for_every_preset(tmp_path: Path) -> None:
    clean = make(tmp_path / "a", "clean", 30, 7)
    nightmare = make(tmp_path / "b", "nightmare", 30, 7)
    assert (clean.path / "truth" / COLUMN_MAPPINGS_FILE).read_bytes() == (
        nightmare.path / "truth" / COLUMN_MAPPINGS_FILE
    ).read_bytes()


def test_rows_are_ordered_by_numeric_position(sample: DatasetResult) -> None:
    for name in ("custodian/custodian_accounts.csv", "custodian/custodian_positions.csv"):
        positions = [int(r["column_position"]) for r in key(sample) if r["file"] == name]
        assert positions == sorted(positions)


def test_re_reading_the_files_confirms_the_key(sample: DatasetResult) -> None:
    assert verify_column_mappings(sample.path) == []


def copy_of(result: DatasetResult, tmp_path: Path) -> Path:
    target = tmp_path / "copy"
    shutil.copytree(result.path, target)
    return target


def edit_key(root: Path, edit: object) -> None:
    path = root / "truth" / COLUMN_MAPPINGS_FILE
    rows = read_table(path)
    assert callable(edit)
    edit(rows)
    write_table(path, HEADER, [[r[h] for h in HEADER] for r in rows])


def test_a_wrong_header_or_position_is_reported(sample: DatasetResult, tmp_path: Path) -> None:
    root = copy_of(sample, tmp_path)

    def rename(rows: list[dict[str, str]]) -> None:
        next(r for r in rows if r["header"] == "contact_id")["header"] = "contactid"

    edit_key(root, rename)
    problems = verify_column_mappings(root)
    assert [p.kind for p in problems] == ["mapping"]
    assert "contactid" in problems[0].detail


def test_swapped_positions_are_reported(sample: DatasetResult, tmp_path: Path) -> None:
    root = copy_of(sample, tmp_path)

    def swap(rows: list[dict[str, str]]) -> None:
        pair = [r for r in rows if r["file"] == "crm/crm_contacts.csv"][:2]
        pair[0]["column_position"], pair[1]["column_position"] = "2", "1"

    edit_key(root, swap)
    assert any("no row matches" in p.detail for p in verify_column_mappings(root))


def test_a_missing_column_in_the_key_is_reported(sample: DatasetResult, tmp_path: Path) -> None:
    root = copy_of(sample, tmp_path)
    edit_key(root, lambda rows: rows.remove(next(r for r in rows if r["header"] == "zip")))
    assert any(p.kind == "mapping" for p in verify_column_mappings(root))


def test_an_unknown_concept_and_an_unlisted_sheet_are_reported(
    sample: DatasetResult, tmp_path: Path
) -> None:
    root = copy_of(sample, tmp_path)

    def damage(rows: list[dict[str, str]]) -> None:
        next(r for r in rows if r["header"] == "zip")["concept"] = "person.nope"
        rows[:] = [r for r in rows if r["sheet"] != "Archive"]

    edit_key(root, damage)
    problems = verify_column_mappings(root)
    assert any("unknown concept" in p.detail for p in problems)
    assert any(p.kind == "unrecorded" and "Archive" in p.path for p in problems)


def test_a_file_missing_from_the_key_or_the_exports_is_reported(
    sample: DatasetResult, tmp_path: Path
) -> None:
    root = copy_of(sample, tmp_path)
    edit_key(
        root, lambda rows: rows.__setitem__(slice(None), [r for r in rows if r["source"] != "crm"])
    )
    problems = verify_column_mappings(root)
    assert {p.path for p in problems if p.kind == "unrecorded"} == {
        "crm/crm_contacts.csv",
        "crm/crm_linked_accounts.csv",
    }
    root2 = copy_of(sample, tmp_path / "second")
    (root2 / "exports" / "crm" / "crm_contacts.csv").unlink()
    assert any(p.kind == "missing" for p in verify_column_mappings(root2))
    (root2 / "truth" / COLUMN_MAPPINGS_FILE).unlink()
    (problem,) = verify_column_mappings(root2)
    assert problem.kind == "missing"


def test_gaps_in_positions_are_reported(sample: DatasetResult, tmp_path: Path) -> None:
    root = copy_of(sample, tmp_path)

    def gap(rows: list[dict[str, str]]) -> None:
        next(r for r in rows if r["header"] == "zip")["column_position"] = "40"

    edit_key(root, gap)
    assert any("positions are not" in p.detail for p in verify_column_mappings(root))

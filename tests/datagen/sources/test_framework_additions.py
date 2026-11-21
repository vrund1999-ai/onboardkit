from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from onboardkit.datagen.sources.base import ColumnSpec, SourceProfile, SourceRow, TableSpec
from onboardkit.datagen.sources.formatters import NameParts, apply_formatter
from onboardkit.datagen.sources.writers import write_csv


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("1234567.5"), "1,234,567.50"),
        (Decimal("-1234.5"), "-1,234.50"),
        (Decimal("0"), "0.00"),
        (Decimal("999.994"), "999.99"),
    ],
)
def test_money_commas_style(value: Decimal, expected: str) -> None:
    assert apply_formatter("money", value, {"style": "commas"}) == expected


def test_map_formatter() -> None:
    options = {"mapping": {"a": "X", "b": "Y"}}
    assert apply_formatter("map", "a", options) == "X"
    assert apply_formatter("map", None, options) == ""
    with pytest.raises(ValueError, match="not in the mapping"):
        apply_formatter("map", "c", options)


def test_name_index_selection() -> None:
    people = [NameParts("John", "Smith"), NameParts("Jane", "Smith")]
    assert apply_formatter("name_last_first", people, {"index": 0}) == "Smith, John"
    assert apply_formatter("name_last_first", people, {"index": 1}) == "Smith, Jane"
    assert apply_formatter("name_last_first", people, {"index": 2}) == ""
    assert apply_formatter("name_last_first", [], {"index": 0}) == ""


def test_same_concept_twice_needs_different_options() -> None:
    def table(second_index: int) -> TableSpec:
        return TableSpec(
            name="t",
            file_name="t.csv",
            columns=[
                ColumnSpec(concept="account.owner_names", header="A", options={"index": 0}),
                ColumnSpec(
                    concept="account.owner_names", header="B", options={"index": second_index}
                ),
            ],
        )

    assert table(1)
    with pytest.raises(ValidationError, match="same options"):
        table(0)


def test_quote_all_and_notes_with_commas(tmp_path: Path) -> None:
    table = TableSpec(
        name="t",
        file_name="t.csv",
        columns=[ColumnSpec(concept="account.number", header="Acct #")],
        preamble=["Report, run 12/31/2025", ""],
        trailer=["Total, 1"],
    )
    profile = SourceProfile(source="x", file_type="csv", quoting="all", tables=[table])
    row = SourceRow(row_uid="x:t:1", source="x", table="t", values={"account.number": "MC1"})
    path = tmp_path / "t.csv"
    locators = write_csv(profile, table, [row], path)
    assert path.read_text(encoding="utf-8").splitlines() == [
        '"Report, run 12/31/2025"',
        "",
        '"Acct #"',
        '"MC1"',
        '"Total, 1"',
    ]
    assert locators["x:t:1"].row_number == 4

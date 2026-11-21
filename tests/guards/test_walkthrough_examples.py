"""Guard: lines quoted in docs/demo-walkthrough.md still exist in a freshly generated sample."""

import re
from pathlib import Path

import pytest
from openpyxl import load_workbook

from onboardkit.datagen.pipeline import DatasetResult
from tests.guards.markdown import REPO_ROOT

WALKTHROUGH = REPO_ROOT / "docs" / "demo-walkthrough.md"
QUOTE = re.compile(r"^```quote (\S+)\n(.*?)^```", re.M | re.S)


def quotes(text: str) -> list[tuple[str, list[str]]]:
    """(file, lines) for every ```quote <file> block: lines the file must contain."""
    return [
        (match.group(1), [line for line in match.group(2).splitlines() if line.strip()])
        for match in QUOTE.finditer(text)
    ]


def file_lines(dataset: Path, name: str) -> list[str]:
    """The lines of a dataset file; workbook rows are shown as cells joined by ' | '."""
    path = dataset / name
    if path.suffix == ".xlsx":
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            return [
                " | ".join("" if cell is None else str(cell) for cell in row)
                for sheet in workbook.worksheets
                for row in sheet.iter_rows(values_only=True)
            ]
        finally:
            workbook.close()
    return path.read_text(encoding="utf-8-sig").splitlines()


def missing(dataset: Path, text: str) -> list[str]:
    found = []
    for name, wanted in quotes(text):
        lines = file_lines(dataset, name)
        found += [
            f"{name}: {line!r} is quoted in the walkthrough but not in the file"
            for line in wanted
            if not any(line.strip() in actual for actual in lines)
        ]
    return found


def test_the_walkthrough_quotes_something() -> None:
    assert len(quotes(WALKTHROUGH.read_text(encoding="utf-8"))) >= 8


def test_quoted_lines_exist_in_a_fresh_sample_dataset(sample_dataset: DatasetResult) -> None:
    text = WALKTHROUGH.read_text(encoding="utf-8")
    assert missing(sample_dataset.path, text) == [], "update docs/demo-walkthrough.md"


def test_the_documented_dataset_id_is_the_current_one(sample_dataset: DatasetResult) -> None:
    text = WALKTHROUGH.read_text(encoding="utf-8")
    assert sample_dataset.dataset_id in text, "the walkthrough names a stale dataset id"


def test_a_stale_quote_is_reported(sample_dataset: DatasetResult) -> None:
    text = (
        "```quote exports/crm/crm_linked_accounts.csv\ncontact_id,account_number\nZ999,NOPE\n```\n"
    )
    (problem,) = missing(sample_dataset.path, text)
    assert problem.startswith("exports/crm/crm_linked_accounts.csv: 'Z999,NOPE' is quoted")


def test_workbook_rows_can_be_quoted(sample_dataset: DatasetResult) -> None:
    name = "exports/book_of_business/book_of_business.xlsx"
    text = f"```quote {name}\nHousehold | Advisor | AcctNo\n```\n"
    assert missing(sample_dataset.path, text) == []


@pytest.mark.parametrize("name", ["truth/entity_matches.csv", "truth/discrepancies.csv"])
def test_truth_files_can_be_quoted(sample_dataset: DatasetResult, name: str) -> None:
    assert file_lines(sample_dataset.path, name)

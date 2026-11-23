"""Guard: generated data only contains obviously fictional personal values."""

import csv
import re
from pathlib import Path

import pytest
from openpyxl import load_workbook

from onboardkit.datagen.pipeline import DatasetResult

DENYLIST = Path(__file__).parent / "data" / "real_firm_denylist.txt"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
PHONE = re.compile(r"(?<![\w])(?:\+?1[ .-]?)?\(?(\d{3})\)?[ .-]?(\d{3})[ .-]?(\d{4})(?![\w])")
TAX_ID = re.compile(r"(?<![\w])\d{3}-?\d{2}-?\d{4}(?![\w])")
FICTIONAL_DOMAINS = {"example.com", "example.test"}
# The exchange 555 with a line number 0100-0199 is reserved for fiction.
QUANTITY = re.compile(r"\d{6}\.\d{4}")
FICTIONAL_PHONE = re.compile(r"^555$"), re.compile(r"^01\d\d$")
ACCOUNT_PREFIX = "MC"  # firm_profile.yaml: account_number.prefix


def texts_in(dataset: Path) -> list[tuple[str, str]]:
    """(file, text) for every file of a dataset; workbooks are read cell by cell."""
    found = []
    for path in sorted(p for p in dataset.rglob("*") if p.is_file()):
        rel = path.relative_to(dataset).as_posix()
        if path.suffix == ".xlsx":
            workbook = load_workbook(path, read_only=True, data_only=True)
            try:
                for sheet in workbook.worksheets:
                    for cells in sheet.iter_rows(values_only=True):
                        found.append((rel, "\n".join(str(c) for c in cells if c is not None)))
            finally:
                workbook.close()
        else:
            found.append((rel, path.read_text(encoding="utf-8-sig", errors="replace")))
    return found


def denied_names() -> list[str]:
    lines = DENYLIST.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def synthetic_problems(texts: list[tuple[str, str]], denylist: list[str]) -> list[str]:
    found = []
    deny = [re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.I) for name in denylist]
    for file, text in texts:
        for domain in sorted({m.group(1).lower() for m in EMAIL.finditer(text)}):
            if domain not in FICTIONAL_DOMAINS:
                found.append(f"{file}: email domain {domain!r} is not example.com or example.test")
        for m in PHONE.finditer(text):
            if QUANTITY.fullmatch(m.group(0)):
                continue  # a holding's quantity or price, such as 676445.7700, is not a phone
            exchange, line = m.group(2), m.group(3)
            if not (FICTIONAL_PHONE[0].match(exchange) and FICTIONAL_PHONE[1].match(line)):
                found.append(
                    f"{file}: phone number {m.group(0)!r} is not in the fictional 555-01XX range"
                )
        found += [
            f"{file}: looks like a nine-digit tax id {m.group(0)!r}" for m in TAX_ID.finditer(text)
        ]
        found += [
            f"{file}: contains the real firm name {r.pattern!r}" for r in deny if r.search(text)
        ]
    return found


def account_number_problems(dataset: Path) -> list[str]:
    """Every account number as exported starts with the fictional prefix (formatting aside)."""
    mappings = _read(dataset / "truth" / "column_mappings.csv")
    headers = {m["header"] for m in mappings if m["concept"] == "account.number"}
    found = []
    for row in _read(dataset / "truth" / "provenance.csv"):
        for pair in filter(None, row["source_keys"].split("|")):
            name, _, value = pair.partition("=")
            if name in headers:
                squeezed = re.sub(r"[^A-Za-z0-9]", "", value).upper()
                if not squeezed.startswith(ACCOUNT_PREFIX):
                    found.append(
                        f"{row['row_uid']}: account number {value!r} lacks prefix {ACCOUNT_PREFIX}"
                    )
    return found


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_sample_dataset_contains_only_fictional_values(sample_dataset: DatasetResult) -> None:
    texts = texts_in(sample_dataset.path)
    assert len(texts) > 50  # sanity: the scan really read the dataset
    assert synthetic_problems(texts, denied_names()) == []


def test_sample_dataset_account_numbers_use_the_fictional_prefix(
    sample_dataset: DatasetResult,
) -> None:
    assert account_number_problems(sample_dataset.path) == []


def test_the_scan_actually_sees_emails_phones_and_workbook_cells(
    sample_dataset: DatasetResult,
) -> None:
    joined = "\n".join(text for _, text in texts_in(sample_dataset.path))
    assert "@example.com" in joined
    assert PHONE.search(joined)
    assert "Summary" in joined or "Advisor" in joined  # workbook cells were read


@pytest.mark.parametrize(
    ("text", "expect"),
    [
        ("mail jane.doe@gmail.com", "email domain 'gmail.com'"),
        ("call (212) 555-0100 or 415-867-5309", "phone number '415-867-5309'"),
        ("call 212-555-0200", "phone number '212-555-0200'"),
        ("ssn 123-45-6789", "nine-digit tax id '123-45-6789'"),
        ("ssn 123456789", "nine-digit tax id '123456789'"),
        ("client of Edward Jones", "real firm name"),
    ],
)
def test_real_looking_values_fail_the_guard(text: str, expect: str) -> None:
    problems = synthetic_problems([("x.csv", text)], denied_names())
    assert any(expect in p for p in problems), problems


@pytest.mark.parametrize(
    "text",
    [
        "jane@example.com and bob@example.test",
        "(212) 555-0142, 212-555-0199, 2125550101, +1 212 555 0150",
        "last four 1234 and balance 152,340.55 on 20250331",
        "Vanguardia is not Vanguard",  # whole words only: 'Vanguardia' alone must not trip
    ],
)
def test_fictional_values_pass(text: str) -> None:
    problems = synthetic_problems([("x.csv", text)], ["Fidelity"])
    assert problems == []


def test_a_real_looking_value_planted_in_a_generated_file_fails(
    sample_dataset: DatasetResult, tmp_path: Path
) -> None:
    import shutil

    copy = tmp_path / "copy"
    shutil.copytree(sample_dataset.path, copy)
    target = copy / "exports" / "crm" / "crm_contacts.csv"
    target.write_text(
        target.read_text(encoding="utf-8") + "x,real.person@gmail.com,415-867-5309,123-45-6789\n",
        encoding="utf-8",
    )
    problems = synthetic_problems(texts_in(copy), denied_names())
    assert len(problems) == 3
    assert all(p.startswith("exports/crm/crm_contacts.csv") for p in problems)


def test_an_account_number_without_the_prefix_fails(
    sample_dataset: DatasetResult, tmp_path: Path
) -> None:
    import shutil

    copy = tmp_path / "copy"
    shutil.copytree(sample_dataset.path, copy)
    path = copy / "truth" / "provenance.csv"
    path.write_text(
        path.read_text(encoding="utf-8").replace("Acct #=MC", "Acct #=ZZ", 1), encoding="utf-8"
    )
    assert len(account_number_problems(copy)) == 1

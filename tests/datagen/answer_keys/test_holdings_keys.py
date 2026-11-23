import json
from pathlib import Path

import pytest

from onboardkit.datagen.answer_keys.checks import TRUTH_ID, check_truth
from onboardkit.datagen.answer_keys.writer import read_table
from onboardkit.datagen.config import resolve_config
from onboardkit.datagen.pipeline import DatasetResult, generate_dataset

POSITIONS_FILE = "custodian/custodian_positions.csv"
HOLDING_CONCEPTS = {
    "holding.account_number",
    "holding.security_symbol",
    "holding.security_name",
    "holding.asset_class",
    "holding.quantity",
    "holding.price",
    "holding.value",
    "holding.as_of",
}


@pytest.fixture(scope="module")
def nightmare(tmp_path_factory: pytest.TempPathFactory) -> DatasetResult:
    return generate_dataset(
        resolve_config("nightmare", "sample", 42), tmp_path_factory.mktemp("nightmare")
    )


@pytest.fixture(scope="module")
def clean(tmp_path_factory: pytest.TempPathFactory) -> DatasetResult:
    return generate_dataset(resolve_config("clean", "sample", 42), tmp_path_factory.mktemp("clean"))


def truth(result: DatasetResult, name: str) -> list[dict[str, str]]:
    return read_table(result.path / "truth" / name)


def test_every_position_row_has_provenance_and_a_holding_and_security(
    nightmare: DatasetResult,
) -> None:
    firm = json.loads((nightmare.path / "truth" / "firm.json").read_text(encoding="utf-8"))
    security_of = {h["holding_id"]: h["security_id"] for h in firm["holdings"]}
    positions = [r for r in truth(nightmare, "provenance.csv") if r["file"] == POSITIONS_FILE]
    assert positions
    for record in positions:
        assert record["table"] == "positions"
        assert record["account_id"] == ""  # a position is not a record of the account itself
        assert security_of[record["holding_id"]] == record["security_id"]
        assert record["source_keys"].startswith("Acct #=")
        assert "|Symbol=" in record["source_keys"]


def test_every_position_row_is_matched_to_its_holding_and_security(
    nightmare: DatasetResult,
) -> None:
    provenance = [r for r in truth(nightmare, "provenance.csv") if r["table"] == "positions"]
    matches = truth(nightmare, "entity_matches.csv")
    for kind, column in (("holding", "holding_id"), ("security", "security_id")):
        by_row = {m["row_uid"]: m["truth_id"] for m in matches if m["entity_type"] == kind}
        assert {r["row_uid"]: r[column] for r in provenance} == by_row


def test_entity_groups_have_holding_and_security_kinds(nightmare: DatasetResult) -> None:
    groups = truth(nightmare, "entity_groups.csv")
    holdings = [g for g in groups if g["entity_type"] == "holding"]
    securities = [g for g in groups if g["entity_type"] == "security"]
    assert holdings and securities
    assert all(g["row_count"] == "1" for g in holdings)  # one row per holding
    assert max(int(g["row_count"]) for g in securities) > 1  # a security is held more than once


def test_column_mappings_list_all_eight_holding_columns(nightmare: DatasetResult) -> None:
    rows = [r for r in truth(nightmare, "column_mappings.csv") if r["file"] == POSITIONS_FILE]
    assert {r["concept"] for r in rows} == HOLDING_CONCEPTS
    assert len(rows) == 8


def test_source_id_map_has_the_symbol_and_the_holding(nightmare: DatasetResult) -> None:
    rows = truth(nightmare, "source_id_map.csv")
    securities = [r for r in rows if r["entity_type"] == "security"]
    holdings = [r for r in rows if r["entity_type"] == "holding"]
    assert securities and all(r["truth_id"].startswith("SEC-") for r in securities)
    assert holdings and all(r["truth_id"].startswith("HOLD-") for r in holdings)
    assert all("/" in r["source_id"] for r in holdings)  # account number and symbol


def test_nightmare_mess_touches_holdings_and_reuses_account_variants(
    nightmare: DatasetResult,
) -> None:
    lines = (nightmare.path / "truth" / "mess_events.jsonl").read_text(encoding="utf-8")
    events = [json.loads(line) for line in lines.splitlines()]
    touched = [e for e in events if str(e["concept"]).startswith("holding.")]
    assert touched
    assert {e["concept"] for e in touched} <= {
        "holding.account_number",
        "holding.as_of",
        "holding.value",
    }
    assert {e["table"] for e in touched} == {"positions"}
    accounts = {e["subtype"] for e in touched if e["concept"] == "holding.account_number"}
    assert accounts <= {"acct_separators", "acct_prefix_case", "acct_leading_zeros"}
    assert all(e["refs"]["holding_id"].startswith("HOLD-") for e in touched)


def test_clean_has_no_mess_on_holdings(clean: DatasetResult) -> None:
    assert clean.mess_events == 0
    lines = (clean.path / "truth" / "mess_events.jsonl").read_text(encoding="utf-8")
    assert "holding." not in lines


def test_a_varied_position_account_number_is_a_moderate_match(nightmare: DatasetResult) -> None:
    lines = (nightmare.path / "truth" / "mess_events.jsonl").read_text(encoding="utf-8")
    varied = {
        row_uid
        for event in map(json.loads, lines.splitlines())
        if event["concept"] == "holding.account_number"
        for row_uid in event["row_uids"]
    }
    assert varied
    by_row = {
        m["row_uid"]: m["difficulty"]
        for m in truth(nightmare, "entity_matches.csv")
        if m["entity_type"] == "holding"
    }
    assert all(by_row[uid] in ("moderate", "hard") for uid in varied)


def test_no_export_contains_a_holding_or_security_id(nightmare: DatasetResult) -> None:
    text = (nightmare.path / "exports" / POSITIONS_FILE).read_text(encoding="utf-8-sig")
    assert not TRUTH_ID.search(text)


def test_check_passes_on_clean_and_nightmare(
    clean: DatasetResult, nightmare: DatasetResult
) -> None:
    assert check_truth(clean.path) == []
    assert check_truth(nightmare.path) == []


def test_the_firm_file_carries_securities_and_holdings(nightmare: DatasetResult) -> None:
    path: Path = nightmare.path / "truth" / "firm.json"
    firm = json.loads(path.read_text(encoding="utf-8"))
    assert firm["securities"] and firm["holdings"]
    assert {"security_id", "symbol", "price"} <= set(firm["securities"][0])

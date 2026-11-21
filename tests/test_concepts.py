import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from onboardkit.datagen.sources.concepts import ConceptCatalogue, load_concepts

DOC = Path(__file__).resolve().parents[1] / "docs" / "source-systems.md"


def test_catalogue_loads_with_unique_valid_ids() -> None:
    catalogue = load_concepts()
    ids = [c.id for c in catalogue.concepts]
    assert len(ids) == len(set(ids)) > 0
    assert all(re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", i) for i in ids)


def test_duplicate_ids_rejected() -> None:
    entry = {"id": "a.b", "description": "x", "value_type": "string"}
    with pytest.raises(ValidationError, match="duplicate"):
        ConceptCatalogue.model_validate({"concepts": [entry, entry]})


def test_bad_id_and_type_rejected() -> None:
    with pytest.raises(ValidationError):
        ConceptCatalogue.model_validate(
            {"concepts": [{"id": "Bad Id", "description": "x", "value_type": "string"}]}
        )
    with pytest.raises(ValidationError):
        ConceptCatalogue.model_validate(
            {"concepts": [{"id": "a.b", "description": "x", "value_type": "blob"}]}
        )


def test_document_matrix_matches_catalogue() -> None:
    rows = re.findall(r"^\| `([a-z_]+\.[a-z0-9_]+)` \|", DOC.read_text(encoding="utf-8"), re.M)
    assert set(rows) == load_concepts().ids()


def test_account_number_headers_from_readme_examples() -> None:
    text = DOC.read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| `account.number`"))
    assert "`Acct #`" in row
    assert "`account_number`" in row
    assert "`AcctNo`" in row

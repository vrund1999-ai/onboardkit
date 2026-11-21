"""Guard: the concept catalogue and the source profiles describe the same columns."""

from onboardkit.datagen.config import resolve_config
from onboardkit.datagen.pipeline import build_rows
from onboardkit.datagen.sources.concepts import ConceptCatalogue, load_concepts

# Concepts in the catalogue that no profile uses yet, on purpose. Keep this empty if you can;
# add an id only with a comment saying which later story will use it.
INTENTIONALLY_UNUSED: frozenset[str] = frozenset()


def used_concepts() -> set[str]:
    built = build_rows(resolve_config("clean", 3, 1))
    return {
        column.concept
        for exporter in built.exporters.values()
        for table in exporter.profile.tables
        for column in table.columns
    }


def problems(catalogue: ConceptCatalogue, used: set[str]) -> list[str]:
    known = catalogue.ids()
    found = [f"profile column uses unknown concept {c!r}" for c in sorted(used - known)]
    found += [
        f"concept {c!r} is used by no profile and not listed as intentionally unused"
        for c in sorted(known - used - INTENTIONALLY_UNUSED)
    ]
    found += [
        f"{c!r} is listed as intentionally unused but a profile uses it or it is gone"
        for c in sorted(INTENTIONALLY_UNUSED & (used | (INTENTIONALLY_UNUSED - known)))
    ]
    return found


def test_every_profile_column_has_a_concept_and_every_concept_is_used() -> None:
    assert problems(load_concepts(), used_concepts()) == []


def test_removing_a_concept_that_a_profile_uses_fails_the_guard() -> None:
    catalogue = load_concepts()
    reduced = ConceptCatalogue(concepts=[c for c in catalogue.concepts if c.id != "account.number"])
    assert problems(reduced, used_concepts()) == [
        "profile column uses unknown concept 'account.number'"
    ]


def test_an_unused_concept_fails_the_guard() -> None:
    assert any("used by no profile" in p for p in problems(load_concepts(), set()))

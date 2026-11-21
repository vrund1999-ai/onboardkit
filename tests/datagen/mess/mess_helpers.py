"""Shared fixtures for the mess tests: a cached truth firm and its projection."""

from functools import cache

from onboardkit.datagen.sources.base import SourceRow
from onboardkit.datagen.sources.book_of_business import BookOfBusinessExporter
from onboardkit.datagen.sources.crm import CrmExporter
from onboardkit.datagen.sources.custodian import CustodianExporter
from onboardkit.datagen.truth.builder import build_firm
from onboardkit.datagen.truth.model import TruthFirm
from onboardkit.datagen.truth.profile import load_profile


@cache
def firm_of(households: int, seed: int = 42) -> TruthFirm:
    return build_firm(load_profile(), households, seed)


def projection(firm: TruthFirm) -> dict[str, list[SourceRow]]:
    return {
        "custodian": CustodianExporter.for_firm(firm).project(firm),
        "crm": CrmExporter().project(firm),
        "book_of_business": BookOfBusinessExporter().project(firm),
    }

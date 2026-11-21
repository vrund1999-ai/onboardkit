"""Generation stages that work in memory: truth, projection, coverage, and mess.

Writing to disk, the manifest, and answer keys arrive with E4-S2 and later; they build on
``build_rows``. Every stage takes all its input from the config.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from onboardkit.datagen import mess as _mess  # noqa: F401  (registers the mess types)
from onboardkit.datagen.config import DatasetConfig, effective_rate
from onboardkit.datagen.mess.base import MessContext, MessEvent, SourceDataset, group_by_table
from onboardkit.datagen.mess.engine import run_mess
from onboardkit.datagen.sources.base import SourceRow
from onboardkit.datagen.sources.book_of_business import BookOfBusinessExporter
from onboardkit.datagen.sources.coverage import CoverageEvent, apply_coverage
from onboardkit.datagen.sources.crm import CrmExporter
from onboardkit.datagen.sources.custodian import CustodianExporter
from onboardkit.datagen.truth.builder import build_firm
from onboardkit.datagen.truth.model import TruthFirm
from onboardkit.datagen.truth.profile import load_profile


@dataclass
class BuiltRows:
    config: DatasetConfig
    firm: TruthFirm
    projected: dict[str, list[SourceRow]]  # every source row before coverage and mess
    coverage_events: list[CoverageEvent]
    data: SourceDataset  # what the sources export: after coverage and mess
    mess_events: list[MessEvent]


def project_sources(firm: TruthFirm, config: DatasetConfig) -> dict[str, list[SourceRow]]:
    return {
        "custodian": CustodianExporter.for_firm(firm).project(firm),
        "crm": CrmExporter().project(firm),
        "book_of_business": BookOfBusinessExporter(config.book_of_business).project(firm),
    }


def build_rows(config: DatasetConfig) -> BuiltRows:
    """Truth, projection, coverage, and mess for one configuration, without touching the disk."""
    firm = build_firm(load_profile(), config.size.households, config.seed, config.as_of_date)
    projected = project_sources(firm, config)
    kept, coverage_events = apply_coverage(projected, firm, config.coverage, config.seed)
    data = group_by_table(copy.deepcopy(kept))
    mess_events = run_mess(
        data,
        config.mess.active_names(),
        lambda mess: MessContext(
            mess.name, effective_rate(config.mess, mess), config.seed, firm, config.as_of_date
        ),
    )
    return BuiltRows(config, firm, projected, coverage_events, data, mess_events)

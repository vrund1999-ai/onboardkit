"""The generation pipeline: configuration in, a complete dataset out.

```
resolve config -> truth -> projection -> coverage -> mess -> write exports
                                                           -> answer keys (E5) -> manifest
```

``build_rows`` runs the in-memory stages and can be used on its own. ``generate_dataset`` adds
the write stages and the output layout. Every stage takes all its input from the config; nothing
is read from global state.
"""

from __future__ import annotations

import copy
import os
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from onboardkit.datagen import mess as _mess  # noqa: F401  (registers the mess types)
from onboardkit.datagen.config import DatasetConfig, dataset_id, effective_rate
from onboardkit.datagen.manifest import write_manifest
from onboardkit.datagen.mess.base import (
    MessContext,
    MessEvent,
    SourceDataset,
    flatten,
    group_by_table,
)
from onboardkit.datagen.mess.engine import run_mess
from onboardkit.datagen.sources.base import RowLocator, SourceExporter, SourceRow
from onboardkit.datagen.sources.book_of_business import BookOfBusinessExporter
from onboardkit.datagen.sources.coverage import CoverageEvent, apply_coverage
from onboardkit.datagen.sources.crm import CrmExporter
from onboardkit.datagen.sources.custodian import CustodianExporter
from onboardkit.datagen.truth.builder import build_firm
from onboardkit.datagen.truth.model import TruthFirm
from onboardkit.datagen.truth.profile import load_profile

DEFAULT_OUT_ROOT = Path("data") / "generated"
EXPORTS = "exports"
TRUTH = "truth"
SOURCE_ORDER = ("custodian", "crm", "book_of_business")


class DatasetExistsError(FileExistsError):
    """The dataset directory already exists and ``overwrite`` was not requested."""


@dataclass
class BuiltRows:
    config: DatasetConfig
    firm: TruthFirm
    exporters: dict[str, SourceExporter]
    projected: dict[str, list[SourceRow]]  # every source row before coverage and mess
    coverage_events: list[CoverageEvent]
    data: SourceDataset  # what the sources export: after coverage and mess
    mess_events: list[MessEvent]


@dataclass
class AnswerKeyContext:
    """Everything an answer key writer needs. ``truth_dir`` is where its files go."""

    config: DatasetConfig
    firm: TruthFirm
    locators: dict[str, dict[str, RowLocator]]  # source -> row uid -> where the row landed
    source_id_maps: dict[str, Any]  # source -> its truth-to-source id maps, when it has any
    coverage_events: list[CoverageEvent]
    mess_events: list[MessEvent]
    truth_dir: Path


AnswerKeyWriter = Callable[[AnswerKeyContext], None]


@dataclass
class DatasetResult:
    dataset_id: str
    path: Path
    config: DatasetConfig
    counts: dict[str, int] = field(default_factory=dict)
    coverage_events: int = 0
    mess_events: int = 0


def make_exporters(firm: TruthFirm, config: DatasetConfig) -> dict[str, SourceExporter]:
    return {
        "custodian": CustodianExporter.for_firm(firm),
        "crm": CrmExporter(),
        "book_of_business": BookOfBusinessExporter(config.book_of_business),
    }


def project_sources(
    firm: TruthFirm, exporters: dict[str, SourceExporter]
) -> dict[str, list[SourceRow]]:
    return {source: exporters[source].project(firm) for source in SOURCE_ORDER}


def build_rows(config: DatasetConfig) -> BuiltRows:
    """Truth, projection, coverage, and mess for one configuration, without touching the disk."""
    firm = build_firm(load_profile(), config.size.households, config.seed, config.as_of_date)
    exporters = make_exporters(firm, config)
    projected = project_sources(firm, exporters)
    kept, coverage_events = apply_coverage(projected, firm, config.coverage, config.seed)
    data = group_by_table(copy.deepcopy(kept))
    mess_events = run_mess(
        data,
        config.mess.active_names(),
        lambda mess: MessContext(
            mess.name, effective_rate(config.mess, mess), config.seed, firm, config.as_of_date
        ),
    )
    return BuiltRows(config, firm, exporters, projected, coverage_events, data, mess_events)


def write_exports(built: BuiltRows, exports_dir: Path) -> dict[str, dict[str, RowLocator]]:
    """Write every source's export under ``exports_dir/<source>/`` and return the row locators."""
    rows_by_source = flatten(built.data)
    locators: dict[str, dict[str, RowLocator]] = {}
    for source in SOURCE_ORDER:
        source_dir = exports_dir / source
        source_dir.mkdir(parents=True)
        result = built.exporters[source].write(rows_by_source[source], source_dir)
        locators[source] = result.locators
    return locators


def count_rows(built: BuiltRows) -> dict[str, int]:
    counts = {
        "households": len(built.firm.households),
        "persons": len(built.firm.people),
        "accounts": len(built.firm.accounts),
    }
    for source in SOURCE_ORDER:
        counts[f"rows.{source}"] = sum(len(rows) for rows in built.data[source].values())
    return counts


def _publish(staging: Path, final: Path, overwrite: bool) -> None:
    if final.exists():
        if not overwrite:
            raise DatasetExistsError(f"dataset already exists: {final}")
        retired = final.with_name(f".{final.name}.old")
        shutil.rmtree(retired, ignore_errors=True)
        os.replace(final, retired)
        try:
            os.replace(staging, final)
        except BaseException:
            os.replace(retired, final)
            raise
        shutil.rmtree(retired, ignore_errors=True)
        return
    os.replace(staging, final)


def generate_dataset(
    config: DatasetConfig,
    out_root: Path = DEFAULT_OUT_ROOT,
    *,
    overwrite: bool = False,
    answer_key_writers: Sequence[AnswerKeyWriter] = (),
) -> DatasetResult:
    """Write one complete dataset to ``out_root/<dataset_id>`` and return what was produced.

    The dataset is built in a sibling temporary directory and renamed into place only when every
    stage succeeded, so a failed run leaves no partial dataset at the final path.
    """
    identifier = dataset_id(config)
    final = out_root / identifier
    if final.exists() and not overwrite:
        raise DatasetExistsError(f"dataset already exists: {final}")
    out_root.mkdir(parents=True, exist_ok=True)
    staging = out_root / f".{identifier}.tmp"
    shutil.rmtree(staging, ignore_errors=True)
    try:
        built = build_rows(config)
        staging.mkdir()
        locators = write_exports(built, staging / EXPORTS)
        truth_dir = staging / TRUTH
        truth_dir.mkdir()
        context = AnswerKeyContext(
            config=config,
            firm=built.firm,
            locators=locators,
            source_id_maps={"crm": getattr(built.exporters["crm"], "id_maps", None)},
            coverage_events=built.coverage_events,
            mess_events=built.mess_events,
            truth_dir=truth_dir,
        )
        for writer in answer_key_writers:
            writer(context)
        write_manifest(staging, config, count_rows(built))
        _publish(staging, final, overwrite)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return DatasetResult(
        dataset_id=identifier,
        path=final,
        config=config,
        counts=count_rows(built),
        coverage_events=len(built.coverage_events),
        mess_events=len(built.mess_events),
    )

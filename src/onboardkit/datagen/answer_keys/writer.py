"""Shared CSV helper for answer-key files: UTF-8, ``\n`` line endings, rows in a stable order."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from pathlib import Path


def write_table(path: Path, header: Sequence[str], rows: Iterable[Sequence[str]]) -> int:
    """Write ``header`` and the rows sorted by their cell values; return the number of rows."""
    ordered = sorted(tuple(row) for row in rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(ordered)
    return len(ordered)


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))

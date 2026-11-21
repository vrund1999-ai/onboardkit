"""Shared CSV helper for answer-key files: UTF-8, ``\n`` line endings, rows in a stable order."""

from __future__ import annotations

import csv
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any


def write_table(
    path: Path,
    header: Sequence[str],
    rows: Iterable[Sequence[str]],
    key: Callable[[tuple[str, ...]], Any] | None = None,
) -> int:
    """Write ``header`` and the rows in a stable order; return the number of rows.

    Rows are sorted by ``key`` when given, otherwise by their cell values.
    """
    ordered = sorted((tuple(row) for row in rows), key=key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(ordered)
    return len(ordered)


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))

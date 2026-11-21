"""Helpers for writing Excel workbooks that are byte-for-byte reproducible.

``openpyxl`` stamps the current time into the workbook properties and the zip entries, and
``save`` overwrites the modified time at the last moment. ``save_deterministic`` avoids all of it.
"""

from __future__ import annotations

import io
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from openpyxl import Workbook
from openpyxl.writer.excel import ExcelWriter

CREATOR = "onboardkit"
ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_UNIX = 3
_FILE_MODE = 0o600 << 16


def stamp_for(as_of_date: date) -> datetime:
    """The fixed workbook timestamp: noon on the as-of date."""
    return datetime(as_of_date.year, as_of_date.month, as_of_date.day, 12, 0, 0)


def save_deterministic(workbook: Workbook, path: Path, stamp: datetime) -> None:
    """Save ``workbook`` so that identical content always gives identical bytes."""
    props: Any = workbook.properties
    props.creator = CREATOR
    props.lastModifiedBy = CREATOR
    props.created = stamp
    props.modified = stamp

    first = io.BytesIO()
    # Use the writer directly: ``Workbook.save`` resets the modified time to now.
    ExcelWriter(workbook, ZipFile(first, "w", ZIP_DEFLATED, allowZip64=True)).save()

    final = io.BytesIO()
    with ZipFile(first) as source, ZipFile(final, "w", ZIP_DEFLATED, compresslevel=6) as target:
        for name in sorted(source.namelist()):
            info = ZipInfo(name, date_time=ZIP_TIME)
            info.compress_type = ZIP_DEFLATED
            info.create_system = _UNIX
            info.external_attr = _FILE_MODE
            target.writestr(info, source.read(name), compresslevel=6)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(final.getvalue())

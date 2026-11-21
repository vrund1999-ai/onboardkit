# E2-S1: Source exporter framework

| | |
|---|---|
| **Epic** | [E2: Multi-source messy exports](../../../epics/m0-foundation-epics.md#e2-multi-source-messy-exports) |
| **Size** | M |
| **Depends on** | E1-S4 |
| **Blocks** | E2-S2, E2-S3, E2-S4, E3-S1, E5-S1, E5-S3 |

## User story

As a contributor, I want a shared framework for turning the truth into per-source rows and writing them to files, so that each source only has to describe what makes it different.

## Context

The three sources differ in columns, formats, and file type, but the mechanics are the same: project truth into rows, format values, write a file, remember where each row landed. Building that once keeps the three exporters small and makes provenance (E5-S1) uniform.

## Scope

**In scope**
- In-memory row model with truth references.
- A source profile that declares tables, columns, and formatting.
- Formatters for dates, money, names, phones, and booleans.
- CSV and XLSX writer helpers returning row locators.

**Out of scope**
- The three concrete exporters (E2-S2 to E2-S4).
- Mess (E3) and coverage (E2-S5).

## Technical design

### Row model

```python
@dataclass(frozen=True)
class TruthRefs:
    person_ids: tuple[str, ...] = ()
    household_id: str | None = None
    account_id: str | None = None

@dataclass
class SourceRow:
    row_uid: str                 # e.g. "custodian:accounts:000123", stable per dataset
    source: str                  # "custodian" | "crm" | "book_of_business"
    table: str                   # logical table name
    values: dict[str, Any]       # keyed by concept id, e.g. "account.number"
    refs: TruthRefs
```

Typed values (`date`, `Decimal`, `str`) are kept in `values`. Mess (E3) edits these before formatting. Keying by concept id (from the E1-S3 catalogue) means the column mapping answer key falls out of the profile for free.

### Source profile

```python
class ColumnSpec(BaseModel):
    concept: str            # must exist in concepts.yaml
    header: str             # header text as the source writes it
    formatter: str          # name in the formatter registry
    options: dict[str, Any] = {}

class TableSpec(BaseModel):
    name: str
    file_name: str          # e.g. "custodian_accounts.csv"
    sheet_name: str | None  # XLSX only
    columns: list[ColumnSpec]

class SourceProfile(BaseModel):
    source: str
    file_type: Literal["csv", "xlsx"]
    encoding: str = "utf-8"
    delimiter: str = ","
    line_ending: Literal["\n", "\r\n"] = "\n"
    tables: list[TableSpec]
```

A validation step rejects any `concept` not in `concepts.yaml`.

### Formatter registry

Pure functions `(value, options) -> str | number`. Initial set: `date` (strftime pattern option), `money` (`plain`, `dollar_commas`, `parens_negative`), `name_last_first`, `name_first_last`, `phone` (styles), `upper`, `passthrough`. Money formatting uses `Decimal` quantization; never `float`.

### Exporter protocol

```python
class SourceExporter(Protocol):
    profile: SourceProfile
    def project(self, firm: TruthFirm) -> list[SourceRow]: ...
    def write(self, rows: list[SourceRow], out_dir: Path) -> WriteResult: ...
```

`WriteResult` maps each `row_uid` to a `RowLocator(file, sheet, row_number)` where `row_number` is the 1-based line in a CSV or row in a sheet, as a user would see it. `write` helpers:

- `write_csv(profile_table, rows, path)`: uses `csv.writer` with the profile's encoding, delimiter, and line ending; records locators, accounting for header and any preamble/trailer lines.
- `write_xlsx(...)`: implemented in E2-S4 on top of a shared helper that makes the workbook byte-deterministic (see that story).

Rows are written in a stable order (sorted by `row_uid` unless a profile specifies otherwise).

## Files to create or change

- `src/onboardkit/datagen/sources/base.py` (row model, profile, protocol)
- `src/onboardkit/datagen/sources/formatters.py`
- `src/onboardkit/datagen/sources/writers.py`
- `tests/datagen/sources/`

## Acceptance criteria

- [ ] A profile referencing an unknown concept fails validation with a clear message.
- [ ] Every formatter has tests including edge values (zero, negative, `None`).
- [ ] `write_csv` writes the header on the profile-declared line and returns correct locators when a preamble or trailer is configured.
- [ ] CSV output honors encoding, delimiter, and line ending from the profile (verified by reading bytes).
- [ ] Row order in output is stable across runs.
- [ ] No source-specific logic lives in `base.py`, `formatters.py`, or `writers.py`.

## Test plan

- Unit tests for each formatter with table-driven cases.
- Round trip: write a small CSV with a trailer, read it back, check locators point to the right lines.
- Byte-level test for `\r\n` line endings and a UTF-8 BOM profile.

## Risks and notes

- `csv` in text mode on Windows can double carriage returns. Open files with `newline=""`.
- Keep `values` typed until formatting so that mess types can reason about real dates and amounts.

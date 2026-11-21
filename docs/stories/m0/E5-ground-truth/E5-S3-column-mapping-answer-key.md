# E5-S3: Column mapping answer key

| | |
|---|---|
| **Epic** | [E5: Ground truth](../../../epics/m0-foundation-epics.md#e5-ground-truth) |
| **Size** | S |
| **Depends on** | E1-S3, E2-S1 |
| **Blocks** | E5-S5 |

## User story

As a contributor, I want an answer key giving the true meaning of every column in every exported file, so that later AI-assisted mapping can be scored.

## Context

M2 will propose what each column means. The truth is already declared in the source profiles (each column has a concept id from the E1-S3 catalogue), so this key is a direct, mechanical export of those profiles. It is deliberately small, but it must cover every column of every file and sheet, including columns that carry no structured meaning.

## Scope

**In scope**
- `truth/column_mappings.csv`.
- Handling of columns that map to a slice of a concept (owner 1 and owner 2) and columns with no concept.

**Out of scope**
- Scoring logic.
- Value-level mapping (for example account type codes to labels), which can be added in M2 if needed.

## Technical design

### File

| Field | Meaning |
|---|---|
| `source` | `custodian`, `crm`, `book_of_business` |
| `file` | Path relative to `exports/` |
| `sheet` | Sheet name or empty |
| `column_position` | 1-based position of the column in the file |
| `header` | Header text exactly as written in the file |
| `concept` | Concept id, or `none` for unmapped columns |
| `slice` | Index when several columns share one concept (`0`, `1`), else empty |
| `value_format` | Name of the formatter applied (for example `date:%m/%d/%Y`) |
| `notes` | Short text for quirks (`header on row 3`, `blank on continuation rows`) |

### Derivation

Iterate the source profiles. For each table and column emit one row. For the workbook, emit one row per column **per sheet** (each advisor sheet repeats the same mapping; the `Summary` sheet's columns are marked `none` with a note). Header positions and the header row number come from the profile, not from re-reading the file.

### Verification against the files

A check re-reads each file, finds the header row via the profile, and confirms that headers and positions in the key equal the actual file. This guards drift between profile and writer.

### Mess interaction

Header text is never altered by M0 mess types, so the key is static per source layout. If a later milestone adds header mess, the key must be generated from the as-written headers; add that as a requirement of any such mess type.

## Files to create or change

- `src/onboardkit/datagen/answer_keys/column_mappings.py`
- `tests/datagen/answer_keys/test_column_mappings.py`

## Acceptance criteria

- [x] Every column in every exported file and sheet has exactly one row in the key.
- [x] Every non-`none` concept exists in `concepts.yaml`.
- [x] `Acct #`, `account_number`, and `AcctNo` all map to `account.number`.
- [x] Owner columns map to `account.owner_names` with slices `0` and `1`.
- [x] Re-reading the files confirms headers and positions match the key exactly.
- [x] Output is byte-identical across runs and the same for any seed (layouts are static).

## Test plan

- Unit test over profiles.
- File re-read verification test for each source, including sheets.
- Test that the number of key rows equals the sum of columns across files.

## Risks and notes

- Because this key does not depend on the seed, it can be cached; still generate it per dataset so every dataset is self-describing.
- If a column is added to an exporter without a concept id, profile validation (E2-S1) fails first, which is intended.

## Notes

- `answer_keys/column_mappings.py` has `build_column_mappings`, `write_column_mappings` (opt-in until E5-S5 registers the defaults) and `verify_column_mappings`.
- The workbook's header row (5) and its sheet list are not in the workbook profile (its table says `header_line` 1, and advisor sheets are created per advisor). The workbook exporter now describes its own sheets through `sheets(rows)` (a `SheetInfo` per sheet, and a `HasSheets` protocol in `sources/base.py`), and `AnswerKeyContext` gained `exporters` so a key writer can ask. The summary sheet's own headers are declared there too and are mapped to `none` with a note.
- The key has no header-row column (the story's field list has none), so `verify_column_mappings` finds the header row by looking for the row whose cells equal the key's headers in position order. It also reports a file or sheet that the key does not mention, gaps in positions, and unknown concepts.
- `value_format` is the formatter name plus its options (`date:%m/%d/%Y`, `money:commas`, `name_last_first:index=0,upper=True`); mapping tables are shown as `map:codes=6` since value-level mapping is out of scope.
- Rows are written in numeric column order (`write_table` gained an optional sort key) so positions read 1, 2, 10 rather than 1, 10, 2.
- `meta.notes` and `meta.review_date` are real concepts in the catalogue, so only the Summary sheet's three columns map to `none`.


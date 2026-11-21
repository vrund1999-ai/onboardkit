# E5-S1: Row provenance and locators

| | |
|---|---|
| **Epic** | [E5: Ground truth](../../../epics/m0-foundation-epics.md#e5-ground-truth) |
| **Size** | M |
| **Depends on** | E2-S1 |
| **Blocks** | E5-S2, E5-S4 |

## User story

As a contributor, I want a complete record of where every exported row landed and which truth entities it refers to, so that every answer key can point at real file locations.

## Context

All three answer keys talk about rows in files: "these two contact rows are the same person", "this balance disagrees with that one". Without a precise row address (file, sheet, row number) and the truth entities behind each row, answer keys would be vague. Provenance is the shared foundation. It is internal and never appears in the exports.

## Scope

**In scope**
- A `provenance` table with one record per exported row.
- Per-source maps from truth identifiers to the source's own identifiers.
- A verification step that re-reads the exported files and confirms every locator.

**Out of scope**
- The answer keys themselves (E5-S2 to E5-S4).

## Technical design

### Provenance record

| Field | Meaning |
|---|---|
| `row_uid` | Internal stable identifier, for example `crm:contacts:000042` |
| `source` | `custodian`, `crm`, or `book_of_business` |
| `table` | Logical table name |
| `file` | Path relative to `exports/` |
| `sheet` | Sheet name or empty for CSV |
| `row_number` | 1-based line (CSV) or Excel row, as a user would see it |
| `person_ids` | Truth person ids, separated by `|`, may be empty |
| `household_id` | Truth household id or empty |
| `account_id` | Truth account id or empty (empty for stale extras) |
| `source_keys` | The source's own identifiers on the row, as `name=value` pairs separated by `|` (for example `contact_id=C004211`) |
| `origin` | `projected`, `duplicate`, `split`, or `stale_extra`, taken from coverage and mess events |

Written to `truth/provenance.csv`, sorted by `row_uid`, UTF-8, `\n` endings.

### Source-id maps

`truth/source_id_map.csv`: `source`, `entity_type`, `truth_id`, `source_id`, one row per mapping, including duplicates created by household mess (several `source_id` values for one `truth_id`).

### Verification

`verify_provenance(dataset_dir) -> list[Problem]` re-opens each export file and, for every record, checks that the cell or line at the locator contains an identifying value that matches the row: the account number for account rows, the contact id for contact rows, and so on. This catches off-by-one errors from preamble, trailer, and spacer rows (custodian preamble, workbook title rows).

## Files to create or change

- `src/onboardkit/datagen/answer_keys/provenance.py`
- `src/onboardkit/datagen/answer_keys/writer.py` (shared CSV helper with stable ordering)
- `tests/datagen/answer_keys/test_provenance.py`

## Acceptance criteria

- [ ] Every row in every export file (excluding header, preamble, trailer, and spacer rows) has exactly one provenance record, and vice versa.
- [ ] Locators verify against the files for all three sources, including advisor sheets in the workbook.
- [ ] Rows created by household mess carry `origin` of `duplicate` or `split`; stale extras carry `stale_extra` and an empty `account_id`.
- [ ] `source_id_map.csv` contains every contact id and household id used by the CRM, including duplicates.
- [ ] Output files are byte-identical across runs.
- [ ] Provenance files are written only under `truth/`.

## Test plan

- Round trip verification on the `sample` dataset for each preset.
- Negative test: shift a locator by one and confirm `verify_provenance` reports it.
- Count test: number of provenance records equals the number of data rows read back from the files.

## Risks and notes

- Row numbers shift if preamble or spacer behavior changes in exporters; the verification test is the safety net.
- Keep `source_keys` as simple text pairs. This is an internal artifact, not a data model.

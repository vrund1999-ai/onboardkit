# E9-S3: Holdings in the answer keys and mess

| | |
|---|---|
| **Epic** | [E9: Holdings in the test data](../../../epics/m1-ingestion-epics.md#e9-holdings-in-the-test-data) |
| **Size** | M |
| **Depends on** | E9-S2 |
| **Blocks** | E9-S4 |

## User story

As a contributor, I want holdings covered by the answer key and the controllable mess like every other kind of data, so that ingestion and later matching can be scored on them.

## Context

Everything the generator exports has a record in the answer key (where each row came from, what each column means, what was changed) and is exposed to the mess types. Holdings must follow the same rule, or they would be the one part of the data that cannot be scored.

## Scope

**In scope**
- Provenance, entity matches, and column mappings for the positions file.
- Source id mapping for securities and holdings.
- Existing mess types applied to the positions file where they make sense (formats and identifiers).
- Truth consistency checks extended to holdings.

**Out of scope**
- New mess types for holdings (security name variants, holdings that disagree with balances). These are listed as later enhancements.
- Discrepancy keys between sources for holdings: only the custodian exports holdings, so there is nothing to disagree with in M1.

## Technical design

- **Provenance.** One row per position row, with file, line, and the truth `holding_id`.
- **Entity matches.** Add `holding` as an entity kind; each position row matches its `HOLD-` id. Securities are an entity kind too (`security`), one group per security with all rows that mention it.
- **Column mappings.** Rows for the eight holding columns, mapping header to concept.
- **Source id map.** The custodian's account number and symbol for each holding and security.
- **Mess.** The formats mess may vary quantity, price, value and date formats in the positions file within the same subtypes as the account master (for example a text-formatted value, a differently formatted date). The identifiers mess may alter the account number display. Every change is a `MessEvent` with concept ids from E9-S2. The mess catalogue is regenerated.
- **Checks.** `onboardkit-gen check` additionally verifies: every position row has provenance and a match; every truth holding is either exported or accounted for by a coverage event; no truth identifier (`HOLD-`, `SEC-`) appears in the exports.
- `clean` stays free of mess: positions in a clean dataset have no events.

## Files to create or change

- `src/onboardkit/datagen/answer_keys/` (provenance, entity_matches, column_mappings, checks, truth_files)
- `src/onboardkit/datagen/mess/formats.py` (and identifiers handling if separate): add the positions columns to `touches`
- `docs/mess-catalogue.md` (regenerated), `docs/source-systems.md`, `docs/datagen-changelog.md` (extend the 0.3.0 entry; the version is not bumped again because 0.3.0 has not been released)
- `tests/datagen/answer_keys/`, `tests/datagen/mess/`

## Acceptance criteria

- [ ] Every row of `custodian_positions.csv` has a provenance row, an entity match, and column mapping entries.
- [ ] `entity_groups.csv` has groups of kind `holding` and `security`.
- [ ] At the `nightmare` preset at least one mess event touches a holdings concept; at `clean`, none do.
- [ ] `onboardkit-gen check` passes, and fails when a position row's provenance is removed (tampering test).
- [ ] No truth identifier of the new kinds appears in any export.
- [ ] The mess catalogue and checksums are regenerated and the guards pass.

## Test plan

- Answer key unit tests for the new kinds.
- Mess coverage test extended (`test_mess_coverage.py` already checks every subtype appears at `nightmare`).
- Tampering test for `check`.
- Standard dataset checksum test after refresh.

## Risks and notes

- Mess on the account number column of the positions file must produce the same variant forms as the account master, or reconciliation between the two files becomes artificially hard. Reuse the same formatting functions.
- Keep the 0.3.0 changelog entry honest: it lists everything that changed, across E9-S2 and E9-S3, in one release.

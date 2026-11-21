# E5-S5: Truth separation and consistency checks

| | |
|---|---|
| **Epic** | [E5: Ground truth](../../../epics/m0-foundation-epics.md#e5-ground-truth) |
| **Size** | M |
| **Depends on** | E5-S2, E5-S3, E5-S4 |
| **Blocks** | none |

## User story

As a contributor, I want the truth kept apart from the exports, summarized, and cross-checked, so that answer keys cannot leak into the material a product works from and always agree with each other.

## Context

The epic's "done when" requires that we can state exactly how many true clients, households, accounts, and discrepancies each dataset contains, that the three answer keys agree, and that ground truth is clearly internal. This story registers all answer key writers in the pipeline, adds the summary, and enforces the separation and consistency rules.

## Scope

**In scope**
- Registration of provenance and the three answer key writers in the pipeline hook (E4-S2).
- `truth/summary.json` and `truth/README.txt`.
- Separation and consistency checks, exposed as a function and a CLI subcommand.

**Out of scope**
- Scoring tools for M2 and M4.

## Technical design

### Truth directory contents

```
truth/
  README.txt                 plain notice that this folder is internal answer material
  summary.json
  firm.json                  the complete truth firm (people, households, accounts)
  provenance.csv             E5-S1
  source_id_map.csv          E5-S1
  entity_matches.csv         E5-S2
  entity_groups.csv          E5-S2
  column_mappings.csv        E5-S3
  discrepancies.csv          E5-S4
  mess_events.jsonl          every MessEvent, one JSON object per line
  coverage_events.jsonl      every CoverageEvent
```

All files listed in the manifest (E4-S3) so `verify` covers them.

### `summary.json`

Counts: truth persons, households, accounts; rows per source; entity groups by type and difficulty; discrepancies by kind and severity; mess events by type and subtype; coverage events by kind. Sorted keys, no timestamps.

### Separation rules

1. Nothing under `truth/` is imported by export-writing code (an import-boundary test).
2. No file under `exports/` contains any truth identifier prefix (`P-`, `HH-`, `ACCT-`) or any value from the `source_id_map` mapped to a truth id in a way that reveals it.
3. `truth/README.txt` states: internal, synthetic, not part of what a firm would send, do not read this folder when building the product pipeline.
4. The CLI documents `truth/` as excluded from any "firm delivery" listing, and `onboardkit-gen show` labels it internal.

### Consistency checks (`check_truth(dataset_dir) -> list[Problem]`)

- Every `truth_id` in answer keys exists in `firm.json`.
- Every `row_uid` in answer keys exists in `provenance.csv`.
- Persons, households, and accounts counts in `summary.json` equal `firm.json`.
- Every entity in `firm.json` appears in at least one group (coverage guarantee).
- Every event-based discrepancy appears in `discrepancies.csv` (E5-S4).
- Every column in `column_mappings.csv` matches the actual file (E5-S3 verification).
- Provenance locators verify against files (E5-S1).
- All CSV and JSON files parse and are sorted deterministically.

The CLI gains `onboardkit-gen check DATASET_DIR`, exit code 1 when problems exist.

## Files to create or change

- `src/onboardkit/datagen/answer_keys/summary.py`, `checks.py`
- `src/onboardkit/datagen/answer_keys/__init__.py` (writer registry)
- `src/onboardkit/datagen/pipeline.py` (register writers)
- `src/onboardkit/datagen/cli.py` (`check` subcommand)
- `tests/datagen/answer_keys/test_checks.py`, `tests/datagen/test_import_boundary.py`

## Acceptance criteria

- [x] Every generated dataset contains the full `truth/` directory above and passes `check_truth`.
- [x] `summary.json` counts equal independent counts taken from the files.
- [x] A scan of `exports/` finds no truth identifiers.
- [x] The import-boundary test fails if export writers import from `answer_keys`.
- [x] Tampering with any answer key (removing a row, altering a truth id) is detected by `check`.
- [x] `truth/README.txt` exists and contains the notice.
- [x] For all presets, the three keys agree: group member rows exist in provenance; discrepancies reference real entities.
- [x] The manifest lists truth files and `verify` detects changes to them.

## Test plan

- Preset-wide test calling `check_truth`.
- Tamper tests, one per rule.
- Import-boundary test using `ast` or `importlib` inspection.
- CLI test for `check`.

## Risks and notes

- `firm.json` contains the whole truth, so it is also the easiest file to leak. Never place it in `exports/`, and keep the boundary test strict.
- When new answer keys arrive in later milestones, they join this directory and these checks.

## Notes

- Generator version is now `0.2.0` (minor: new files under `truth/`; exports are byte-identical to 0.1.0). Changelog entry and the recorded standard checksums for 0.2.0 are included.
- `generate_dataset(answer_key_writers=None)` now runs `answer_keys.DEFAULT_WRITERS` (imported lazily to avoid a cycle). Pass `()` for a dataset with an empty `truth/`.
- New modules: `answer_keys/truth_files.py` (README notice, `firm.json`, the two event logs), `summary.py`, `checks.py`. `firm.json` holds people, households and accounts plus the firm name; the large firm profile is left out.
- Deviation: the "every entity appears in a group" check also accepts an entity listed in `entities_not_exported.csv` (E5-S2 note) and fails if an entity is in both or neither.
- Deviation: the "no value from `source_id_map`" rule is implemented as "no source id embeds its truth id". Source ids themselves (for example `C000123`) legitimately appear in exports.
- The import-boundary test scans `sources/`, `mess/` and `truth/` and requires that only `pipeline.py` (lazy default hook) and `cli.py` import `answer_keys` outside the package.
- `check_truth` also runs `verify_provenance` and `verify_column_mappings`, and checks event-based discrepancies from the files (coverage events all cited; value-conflict mess events cited, except a stale custodian balance on an account the book does not hold).
- `onboardkit-gen show` prints delivered and internal file counts; `generate --help` says `truth/` is internal.
- Older tests that listed every file of a dataset were updated to include the 12 truth files.


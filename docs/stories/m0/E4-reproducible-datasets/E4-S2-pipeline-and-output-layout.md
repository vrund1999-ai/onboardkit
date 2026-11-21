# E4-S2: Generation pipeline and output layout

| | |
|---|---|
| **Epic** | [E4: Reproducible datasets](../../../epics/m0-foundation-epics.md#e4-reproducible-datasets) |
| **Size** | M |
| **Depends on** | E2-S5, E4-S1 |
| **Blocks** | E4-S3, E4-S4, E6-S3 |

## User story

As a contributor, I want a single function that turns a configuration into a complete dataset on disk, so that generation is one repeatable step with a predictable folder layout.

## Context

The pieces exist separately: truth builder, three exporters, coverage, mess engine, and (later) answer keys. This story wires them into one orchestrated pipeline and fixes where outputs go. The layout keeps exports (what a firm would send) physically apart from truth (internal answer material), which E5-S5 enforces.

## Scope

**In scope**
- `generate_dataset(config, out_root) -> DatasetResult`.
- Output directory layout and safe overwrite rules.
- A hook where answer key writers (E5) plug in.

**Out of scope**
- The manifest contents (E4-S3) and CLI (E4-S4).

## Technical design

### Pipeline

```
resolve config
  -> build truth firm                        (E1-S4)
  -> project rows per source                 (E2-S2..S4)
  -> apply coverage          -> coverage events   (E2-S5)
  -> apply mess              -> mess events       (E3)
  -> write exports           -> row locators      (E2-S1)
  -> write truth + answer keys                    (E5)
  -> write manifest                               (E4-S3)
```

Each stage is a pure function from inputs to outputs, except the write stages. `generate_dataset` holds no state between calls and takes all input from the config.

### Output layout

```
data/generated/<dataset_id>/
  exports/
    custodian/custodian_accounts.csv
    crm/crm_contacts.csv
    crm/crm_linked_accounts.csv
    book_of_business/book_of_business.xlsx
  truth/                     # internal; written by E5
  manifest.json
```

Default `out_root` is `data/generated` (already git-ignored).

### Writing safely

1. Write into a sibling temporary directory `.<dataset_id>.tmp`.
2. On success, atomically rename to the final directory.
3. If the final directory exists: with `overwrite=False` (default) raise `DatasetExistsError`; with `overwrite=True` replace it. A failed run leaves no partial dataset.

### Result object

```python
@dataclass
class DatasetResult:
    dataset_id: str
    path: Path
    config: DatasetConfig
    counts: dict[str, int]       # households, persons, accounts, rows per source
    coverage_events: int
    mess_events: int
```

### Answer key hook

`generate_dataset` accepts a list of `AnswerKeyWriter` callables, each given the truth, locators, source-id maps, coverage events, and mess events. Until E5 lands the default list is empty; E5-S5 registers the real writers.

## Files to create or change

- `src/onboardkit/datagen/pipeline.py`
- `tests/datagen/test_pipeline.py`

## Acceptance criteria

- [x] `generate_dataset` produces the layout above for `sample` and `default` sizes.
- [x] A failure mid-run (injected in a test) leaves no directory at the final path.
- [x] Re-running without `overwrite` raises `DatasetExistsError`; with it, replaces the directory.
- [x] The result counts equal what is found on disk.
- [x] No export file contains a truth identifier (`P-`, `HH-`, `ACCT-` prefixes) anywhere.
- [x] Pipeline reads no global state beyond the config.

## Test plan

- Integration test on the `sample` size for each preset.
- Failure-injection test using a monkeypatched writer that raises.
- Scan test for truth identifier prefixes across all export files.

## Risks and notes

- Atomic rename can fail on Windows if a file is open; close handles before renaming and test on Windows in CI.
- Keep stages independently callable so tests can run any stage on hand-built input.

## Notes

- `build_rows(config)` (added in E3-S7) is the in-memory part: truth, projection, coverage, mess. `generate_dataset` writes around it. It now also returns the exporters used, so `generate_dataset` writes each source with the same exporter that projected it (the CRM's id maps depend on that).
- The `manifest.json` written here is a placeholder with `dataset_id` and the resolved config; E4-S3 replaces it with the full manifest.
- `truth/` is created empty for the answer key writers. Each writer gets an `AnswerKeyContext` (config, truth firm, row locators per source, source id maps, coverage and mess events, the `truth_dir`).
- Overwrite swaps the old directory aside, renames the new one in, then deletes the old one, and puts the old one back if the rename fails.
- The truth profile still loads from the packaged `lantern_ridge.yaml`; there is no other source of input than the config.
- The default `out_root` is relative (`data/generated`); tests confirm nothing is written relative to the working directory when an `out_root` is given.


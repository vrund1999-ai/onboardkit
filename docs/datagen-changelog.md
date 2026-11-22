# Data generator changelog

Every generated dataset records `generator_version` in its `manifest.json`. The version lives in
`src/onboardkit/datagen/__init__.py` (`GENERATOR_VERSION`) and follows semantic versioning:

| Bump | When |
|---|---|
| **Patch** | A change that does not alter generated output (refactors, docs, tests, performance). |
| **Minor** | Output changes for existing configurations (tuned rates, a new mess subtype, new columns). |
| **Major** | The configuration schema or the manifest format changes incompatibly. |

Any change that alters generated output requires a version bump and an entry here. The standard
dataset checksums recorded for each version are checked by the determinism tests (E4-S5).

## Standard datasets and updating their checksums

| Name | Command | Purpose |
|---|---|---|
| `sample` | `onboardkit-gen generate --preset typical --size sample --seed 42` | Fast tests, screenshots, walkthroughs (15 households) |
| `demo` | `onboardkit-gen generate --preset typical --size default --seed 42` | Realistic demonstration (300 households) |

The SHA-256 of every file of both datasets is recorded per generator version in
`tests/datagen/expected/standard_datasets.json`; `test_standard_datasets.py` compares against it on
Linux and Windows in CI. When that test fails:

1. Find out why. An unintended change is a bug; fix it.
2. If the change is intended (or a dependency upgrade changed the bytes and that is acceptable),
   bump `GENERATOR_VERSION` according to the table above.
3. Add an entry to this file describing what changed.
4. Run `python scripts/update_expected_checksums.py` and commit the updated JSON with the change.

Datasets made by different versions are not comparable: a result quoted against a dataset should
name its `dataset_id` and `generator_version`.

## 0.3.0

Holdings arrive (milestone M1, epic E9). The sample and demo datasets keep their dataset ids,
because ids come from the configuration, but every manifest, `column_mappings.csv` and
`provenance.csv` changes, and there is one new export file.

- New export `exports/custodian/custodian_positions.csv`: one row per holding, in the custodian's
  style (preamble, upper case, `EQ`/`FI`/`FUND`/`CASH` codes, quantities and prices to four
  decimals, a `Total positions` trailer). The firm's securities and holdings come from the truth
  firm (E9-S1); positions follow their account, so an account the custodian leaves out has no
  positions either.
- New concepts `holding.account_number`, `holding.security_symbol`, `holding.security_name`,
  `holding.asset_class`, `holding.quantity`, `holding.price`, `holding.value` and
  `holding.as_of`, and the value type `decimal`.
- `column_mappings.csv` and `provenance.csv` list the new file. Position rows carry no account
  reference in the answer key yet (entity matches arrive with E9-S3).
- Everything else in `exports/` is unchanged byte for byte. The mess and coverage events are the
  same events, but each `refs` object gains a `holding_id` key (null for these events).

## 0.2.0

Every dataset now carries its answer keys in `truth/` (E5). Exports are unchanged byte for byte.

- New files under `truth/`: `README.txt`, `summary.json`, `firm.json`, `provenance.csv`,
  `source_id_map.csv`, `entity_matches.csv`, `entity_groups.csv`, `entities_not_exported.csv`,
  `column_mappings.csv`, `discrepancies.csv`, `mess_events.jsonl`, `coverage_events.jsonl`.
- The manifest lists them, so `verify` covers them; `onboardkit-gen check` validates them.
- `onboardkit-gen show` separates delivered (`exports/`) from internal (`truth/`) file counts.

## 0.1.0

First version of the generator.

- Fictional firm, three source exporters (custodian CSV, CRM CSV, book of business workbook).
- Coverage gaps and stale spreadsheet rows.
- Four mess types: names, households, formats, balances.
- Presets `clean`, `typical`, `nightmare`.
- Dataset layout `exports/`, `truth/`, `manifest.json`, with checksums for every file.

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

Datasets made by different versions are not comparable: a result quoted against a dataset should
name its `dataset_id` and `generator_version`.

## 0.1.0

First version of the generator.

- Fictional firm, three source exporters (custodian CSV, CRM CSV, book of business workbook).
- Coverage gaps and stale spreadsheet rows.
- Four mess types: names, households, formats, balances.
- Presets `clean`, `typical`, `nightmare`.
- Dataset layout `exports/`, `truth/`, `manifest.json`, with checksums for every file.

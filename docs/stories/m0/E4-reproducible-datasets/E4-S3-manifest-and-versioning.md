# E4-S3: Dataset manifest and versioning

| | |
|---|---|
| **Epic** | [E4: Reproducible datasets](../../../epics/m0-foundation-epics.md#e4-reproducible-datasets) |
| **Size** | S |
| **Depends on** | E4-S2 |
| **Blocks** | E4-S4, E4-S5 |

## User story

As a contributor, I want every dataset labelled with what produced it, so that it is always clear which settings and generator version a result came from.

## Context

Results in later milestones (mapping accuracy, match accuracy) will be quoted against a dataset. If the dataset cannot be identified and regenerated, those numbers are not comparable over time. The manifest records the configuration, the generator version, the key dependency versions, and a checksum for every file, so a dataset can be verified and regenerated.

## Scope

**In scope**
- `manifest.json` written with every dataset.
- A generator version constant and changelog.
- A `verify_manifest` function that checks files against their checksums.

**Out of scope**
- A registry or catalogue of datasets across runs.

## Technical design

### Manifest content

```json
{
  "manifest_version": 1,
  "dataset_id": "typical-default-s42-3fa9c1d2",
  "generator_version": "0.1.0",
  "config": { "...canonical config..." },
  "config_hash": "3fa9c1d2e5b7",
  "dependencies": { "python": "3.12.x", "faker": "x.y.z", "openpyxl": "x.y.z", "pydantic": "x.y.z" },
  "counts": { "households": 300, "persons": 0, "accounts": 0 },
  "files": [
    { "path": "exports/custodian/custodian_accounts.csv", "sha256": "...", "bytes": 0 }
  ]
}
```

Rules:
- **No timestamps and no hostnames.** The manifest itself must be reproducible. A creation time would break determinism, so none is recorded.
- Files are listed in sorted path order, paths use forward slashes.
- `manifest.json` is not listed in `files` (it cannot contain its own checksum). A separate `files_digest` field hashes the concatenation of the listed checksums.
- JSON written with sorted keys and two-space indent, trailing newline.

### Generator version

`GENERATOR_VERSION` lives in `src/onboardkit/datagen/__init__.py` and follows semantic versioning:

- **Patch:** change that does not alter generated output.
- **Minor:** output changes for existing configs (tuned rates, new mess subtype).
- **Major:** config schema or manifest format changes incompatibly.

Any change that alters output requires a version bump and a line in `docs/datagen-changelog.md`. A test (E4-S5) enforces that the sample dataset's checksums match the recorded values for the current version.

### Verification

`verify_manifest(dataset_dir) -> list[Problem]` recomputes sizes and checksums and reports missing, extra, or changed files. Extra files under `exports/` and `truth/` are reported as problems.

## Files to create or change

- `src/onboardkit/datagen/manifest.py`
- `src/onboardkit/datagen/__init__.py` (version constant)
- `docs/datagen-changelog.md`
- `tests/datagen/test_manifest.py`

## Acceptance criteria

- [x] Every generated dataset contains a `manifest.json` with the fields above.
- [x] The manifest contains no timestamp, username, hostname, or absolute path.
- [x] Generating the same config twice yields byte-identical manifests.
- [x] `verify_manifest` passes on a fresh dataset and reports a problem after a file is edited, deleted, or added.
- [x] Dependency versions recorded match the installed ones.
- [x] The changelog exists and explains version rules.

## Test plan

- Unit tests for serialization stability and key ordering.
- Tamper tests for `verify_manifest`.
- Test that no field in the manifest contains the working directory path.

## Risks and notes

- Recording dependency versions in the manifest makes the manifest differ across environments with different Faker versions, which is the point: it signals why output might differ.
- Keep the manifest small; it should be readable by eye.

## Notes

- `manifest.py` has `build_manifest`, `write_manifest`, `dumps`, `files_digest`, and `verify_manifest`; `generate_dataset` writes the manifest last, after the answer keys, so truth files are listed too (everything under the dataset except `manifest.json`).
- `counts` is the pipeline's full count mapping: `households`, `persons`, `accounts`, and `rows.<source>`.
- `verify_manifest` returns `Problem(kind, path, detail)` values with kinds `manifest` (unreadable, wrong version, bad `files_digest`), `missing`, `changed` (size or checksum), and `extra` (any unlisted file, anywhere under the dataset).
- Dependencies recorded are Python, Faker, openpyxl, and pydantic, read from the installed package metadata.
- The enforcement of the standard dataset checksums per version belongs to E4-S5.


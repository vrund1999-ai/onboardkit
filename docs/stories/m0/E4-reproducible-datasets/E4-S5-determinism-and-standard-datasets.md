# E4-S5: Determinism guarantee and standard datasets

| | |
|---|---|
| **Epic** | [E4: Reproducible datasets](../../../m0-foundation-epics.md#e4-reproducible-datasets) |
| **Size** | M |
| **Depends on** | E4-S4, E3-S7 |
| **Blocks** | E7-S2 |

## User story

As a contributor, I want an automated guarantee that the same settings give identical files, and two named standard datasets, so that results stay comparable and everyone demonstrates against the same data.

## Context

Reproducibility is the central promise of E4. It needs a mechanical check, run on every change and on every supported operating system, because subtle sources of non-determinism (set ordering, zip timestamps, line endings, dependency upgrades) tend to creep in. The two standard datasets are the "sample" for quick tests and the realistic "default" firm for demos.

## Scope

**In scope**
- Determinism tests across runs, processes, and operating systems.
- Recorded checksums for the standard datasets.
- A documented procedure for updating those checksums when output intentionally changes.

**Out of scope**
- Committing generated data to version control (it stays git-ignored).

## Technical design

### Standard datasets

| Name | Command | Purpose |
|---|---|---|
| `sample` | `onboardkit-gen generate --preset typical --size sample --seed 42` | Fast tests, screenshots, walkthroughs (about 15 households) |
| `demo` | `onboardkit-gen generate --preset typical --size default --seed 42` | Realistic demonstration (about 300 households) |

Expected checksums live in `tests/datagen/expected/standard_datasets.json`, keyed by generator version and dataset name, listing the SHA-256 of every file (the same data that appears in the manifest).

### Determinism tests

1. **Same process:** generate twice in one test run, compare the whole directory byte for byte.
2. **Separate processes:** generate via `subprocess` twice with different `PYTHONHASHSEED` values (for example `0` and `12345`) and compare. This catches reliance on string hash ordering or set iteration order.
3. **Different working directory and output root:** same result.
4. **Cross-platform:** the checksum test runs in CI on Linux and Windows (E6-S2) against the same expected file, which catches line-ending and path-separator differences.
5. **Stream independence:** enabling or disabling an unrelated mess type does not change another type's events (covered in earlier stories; asserted again end to end here).

### Checksum guard

A test generates both standard datasets and compares file checksums with `standard_datasets.json` for the current `GENERATOR_VERSION`. Failure message explains: "Output changed. If intentional, bump the generator version, update the changelog, and run `scripts/update_expected_checksums.py`."

### Sources of non-determinism to verify explicitly

- Zip timestamps inside the `.xlsx` (see E2-S4).
- `openpyxl` workbook properties.
- CSV line endings on Windows.
- Iteration over sets and dictionaries built from unordered input.
- Faker version differences (recorded in the manifest).

## Files to create or change

- `tests/datagen/test_determinism.py`
- `tests/datagen/test_standard_datasets.py`
- `tests/datagen/expected/standard_datasets.json`
- `scripts/update_expected_checksums.py`

## Acceptance criteria

- [ ] Two runs in one process yield byte-identical directories.
- [ ] Two runs in separate processes with different `PYTHONHASHSEED` values yield byte-identical directories.
- [ ] Output is identical regardless of working directory and output root.
- [ ] Standard dataset checksums match on both Linux and Windows CI.
- [ ] Changing a generator behavior without bumping the version fails the checksum test with the guidance message.
- [ ] Both standard datasets generate in one command each and finish within 60 seconds on a typical laptop (sample within 5 seconds).
- [ ] Generated files are not tracked by git.

## Test plan

- The tests above, with the cross-platform run enforced by the CI matrix.
- A negative test that deliberately perturbs output to prove the guard fires.

## Risks and notes

- This is the story most likely to fail when a dependency is upgraded. That is intended: investigate, bump the version if the change is acceptable, update the expected checksums.
- Cross-platform byte equality depends on writing CSVs with explicit line endings and `newline=""`.

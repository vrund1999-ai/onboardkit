# E4-S4: Generator command line

| | |
|---|---|
| **Epic** | [E4: Reproducible datasets](../../../epics/m0-foundation-epics.md#e4-reproducible-datasets) |
| **Size** | M |
| **Depends on** | E4-S2, E4-S3 |
| **Blocks** | E4-S5, E7-S1, E7-S2 |

## User story

As a contributor, I want a command line to generate, list, and verify datasets, so that regenerating the standard demo dataset is a single step.

## Context

The epic's exit criteria say a dataset can be regenerated "in one step". A Typer-based command, `onboardkit-gen`, is that step. It is also how CI, the documentation, and the walkthrough produce data, so it must be predictable and give clear errors.

## Scope

**In scope**
- Console script `onboardkit-gen` with subcommands `generate`, `presets`, `verify`, `show`.
- Exit codes and error messages.

**Out of scope**
- Interactive prompts.
- Anything that reads or writes outside the output root.

## Technical design

### Commands

```
onboardkit-gen generate [--preset NAME] [--size sample|default|N] [--seed INT]
                        [--mess NAME=LEVEL ...] [--as-of YYYY-MM-DD]
                        [--config FILE.yaml] [--out DIR] [--overwrite]
onboardkit-gen presets
onboardkit-gen verify DATASET_DIR
onboardkit-gen show DATASET_DIR
```

Defaults: preset `typical`, size `default`, seed `42`, out `data/generated`.

- `generate`: resolves the configuration (E4-S1), runs the pipeline (E4-S2), prints the dataset id, location, and counts. `--config` loads a YAML file whose values are overridden by explicit flags. `--mess` is repeatable (`--mess names=heavy --mess balances=0.2`) and uses E3-S2 parsing.
- `presets`: lists each preset with its description and mess summary.
- `verify`: runs `verify_manifest` and prints problems.
- `show`: prints the manifest summary (id, version, counts, mess event totals).

### Output

Plain text, one fact per line, no color dependency; `--quiet` prints only the dataset path. Errors go to stderr.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Verification problems found |
| 2 | Invalid arguments or configuration |
| 3 | Dataset already exists (without `--overwrite`) |
| 4 | Unexpected error |

### Packaging

`pyproject.toml` declares `[project.scripts] onboardkit-gen = "onboardkit.datagen.cli:app"`. `python -m onboardkit.datagen` also works.

## Files to create or change

- `src/onboardkit/datagen/cli.py`, `__main__.py`
- `pyproject.toml` (script entry)
- `tests/datagen/test_cli.py` using `typer.testing.CliRunner`

## Acceptance criteria

- [ ] `onboardkit-gen generate` with no arguments produces the default `typical` dataset at seed 42.
- [ ] `--size sample --preset clean --seed 7` produces a small clean dataset.
- [ ] Unknown preset, mess name, or level gives exit code 2 and lists valid values.
- [ ] Re-running without `--overwrite` exits 3 and changes nothing on disk.
- [ ] `verify` exits 0 on a fresh dataset and 1 after tampering.
- [ ] `--help` for each command documents every option.
- [ ] Works from any working directory when `--out` is absolute.

## Test plan

- `CliRunner` tests for each command and exit code.
- Test that `--config` values are overridden by flags.
- Windows path handling test (drive letters, spaces in paths).

## Risks and notes

- Keep the console script name and flags stable; the documentation depends on them.
- Do not print absolute user paths into the manifest or dataset files; printing them on the terminal is fine.

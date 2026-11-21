# E3-S7: Presets and mess coverage

| | |
|---|---|
| **Epic** | [E3: Controllable mess](../../../epics/m0-foundation-epics.md#e3-controllable-mess) |
| **Size** | M |
| **Depends on** | E3-S3, E3-S4, E3-S5, E3-S6 |
| **Blocks** | E4-S5 |

## User story

As a contributor, I want named presets (`clean`, `typical`, `nightmare`) and proof that every mess type shows up and stays isolated, so that common scenarios are one choice away and the mess catalogue is trustworthy.

## Context

This story closes E3. It wraps the individual mess types into presets and adds the tests behind the epic's "done when" claims: the same firm can be generated clean or heavily messy, turning one mess type on affects only that kind of problem, and every mess type has a visible example.

## Scope

**In scope**
- Three preset YAML files covering mess settings and coverage rates.
- A preset loader.
- Isolation and coverage tests over the whole pipeline.
- A short generated catalogue of mess types for documentation.

**Out of scope**
- The CLI (E4-S4).

## Technical design

### Presets

Located in `src/onboardkit/datagen/presets/` as package data. Each has `name`, `description`, `coverage`, and `mess` blocks.

| Preset | Coverage | Mess intensities | Intended use |
|---|---|---|---|
| `clean` | all sources 1.0, no stale extras | all mess off | Baseline and plumbing tests |
| `typical` | custodian 1.0, CRM 0.97/0.90, book 0.85/0.80, stale extras 0.03 | names 0.5, households 0.3, formats 0.5, balances 0.4 | Default demo |
| `nightmare` | custodian 0.98, CRM 0.90/0.75, book 0.70/0.60, stale extras 0.08 | all 0.9 | Stress testing |

`load_preset(name) -> DatasetConfig fragment`. Unknown names list the valid ones.

### Isolation harness

A test helper `run_pipeline_with(mess={...}, seed=...)` returns the final `SourceDataset` and events. The isolation test, for each mess type `X`:

1. Run with all mess off (coverage at 1.0) to get the baseline.
2. Run with only `X` at 0.8.
3. Assert every difference from the baseline is accounted for by an event of type `X`, within `X.touches`, and that no row differs outside the sources `X` declares.

### Coverage test

At `nightmare`, on the 300-household dataset, assert each subtype of each mess type produced at least one event. The list of expected subtypes comes from each type's own `subtypes` attribute, so adding a subtype automatically adds the expectation.

### Catalogue document

A small script `scripts/mess_catalogue.py` (or CLI subcommand later) renders `docs/mess-catalogue.md` from the registry: name, description, subtypes, max rate, touched concepts, example event. The document is generated, committed, and checked for staleness by a test that regenerates and compares.

## Files to create or change

- `src/onboardkit/datagen/presets/clean.yaml`, `typical.yaml`, `nightmare.yaml`
- `src/onboardkit/datagen/presets/__init__.py` (loader)
- `tests/datagen/test_presets.py`, `tests/datagen/test_mess_isolation.py`, `tests/datagen/test_mess_coverage.py`
- `scripts/mess_catalogue.py`, `docs/mess-catalogue.md`

## Acceptance criteria

- [ ] `clean` output equals the projection exactly (no events, nothing omitted).
- [ ] `typical` and `nightmare` load and validate.
- [ ] The isolation test passes for every registered mess type.
- [ ] The coverage test passes: every subtype has at least one event at `nightmare`.
- [ ] `docs/mess-catalogue.md` is generated from the registry and the staleness test passes.
- [ ] The same seed yields a clean dataset and a heavily messy dataset of the same underlying firm (identical truth, different exports).

## Test plan

- The three test files above.
- Test that the truth portion of the output is identical across presets for one seed.

## Risks and notes

- Isolation tests are slower than unit tests. Run them on the 15-household sample for each type, and on 300 households only in the coverage test.
- Treat intensity values in the presets as tunable; record changes in the changelog because they alter generated data.

# E4-S1: Dataset configuration and seeding

| | |
|---|---|
| **Epic** | [E4: Reproducible datasets](../../../epics/m0-foundation-epics.md#e4-reproducible-datasets) |
| **Size** | M |
| **Depends on** | E1-S4 |
| **Blocks** | E3-S2, E4-S2 |

## User story

As a contributor, I want one validated configuration object that fully describes a dataset, so that the same settings always produce identical data.

## Context

A dataset is defined by its settings: size, seed, as-of date, coverage, and mess. If any input that influences output sits outside the configuration (an environment variable, today's date, a hidden default), reproducibility breaks. This story defines the top-level `DatasetConfig` and the rules that make it a complete description. It is pulled forward in the build order because mess settings (E3-S2) are part of it.

## Scope

**In scope**
- `DatasetConfig` Pydantic model and YAML loading.
- Size handling (`sample`, `default`, or an explicit household count).
- Canonical serialization and a stable configuration hash.
- Merging a preset with overrides.

**Out of scope**
- Output layout, manifest, and CLI (E4-S2 to E4-S4).

## Technical design

### Model

```python
class SizeConfig(BaseModel):
    households: int = Field(ge=1, le=5000)

SIZES = {"sample": 15, "default": 300}

class DatasetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    preset: str | None = None          # informational, resolved before use
    size: SizeConfig
    seed: int = Field(ge=0, le=2**63 - 1)
    as_of_date: date = date(2025, 12, 31)
    firm_profile: str = "lantern_ridge"   # name of a bundled profile
    coverage: CoverageConfig
    mess: MessConfig
```

`extra="forbid"` makes typos in YAML errors rather than silent no-ops.

### Resolution order

`resolve_config(preset: str, size: str | int, seed: int, overrides: dict) -> DatasetConfig`:

1. Load the preset's coverage and mess blocks (E3-S7).
2. Apply size (`sample`, `default`, or an integer).
3. Apply `seed` and `as_of_date`.
4. Apply `--mess` style overrides using E3-S2 functions.
5. Validate.

No step consults the environment or the clock.

### Canonical form and hash

`canonical_json(config) -> str`: `model_dump(mode="json")` with sorted keys, no whitespace, floats written with `repr`. `config_hash(config) -> str`: first 12 hex characters of SHA-256 over that string. Intensity floats are normalized (rounded to 6 places) before hashing so equal values hash equally.

### Dataset identifier

`dataset_id = f"{preset}-{size_label}-s{seed}-{config_hash[:8]}"`, for example `typical-default-s42-3fa9c1d2`. The hash makes any override produce a distinct identifier.

## Files to create or change

- `src/onboardkit/datagen/config.py` (extend with `SizeConfig`, `DatasetConfig`, `resolve_config`, `canonical_json`, `config_hash`, `dataset_id`)
- `tests/datagen/test_config.py`

## Acceptance criteria

- [ ] Loading a YAML with an unknown key fails with a message naming the key.
- [ ] `sample` resolves to 15 households and `default` to 300; an explicit integer is accepted within limits.
- [ ] Equal configs have equal hashes; changing seed, size, any mess intensity, or any coverage rate changes the hash.
- [ ] Key order in YAML does not affect the hash.
- [ ] `resolve_config` reads neither environment variables nor the clock (verified by a test that patches both to raise).
- [ ] The dataset id has the documented shape.

## Test plan

- Table-driven validation tests.
- Hash stability test pinned to a known config (guards accidental changes to canonical form).
- Hash sensitivity tests over each field group.

## Risks and notes

- Changing canonical form changes every dataset id. Treat `config_hash` as a public format and note changes in the generator changelog.
- Keep the model flat enough that a person can read a full config in one screen.

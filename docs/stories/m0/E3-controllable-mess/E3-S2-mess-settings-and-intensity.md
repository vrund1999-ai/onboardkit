# E3-S2: Mess settings and intensity model

| | |
|---|---|
| **Epic** | [E3: Controllable mess](../../../m0-foundation-epics.md#e3-controllable-mess) |
| **Size** | S |
| **Depends on** | E3-S1, E4-S1 |
| **Blocks** | E3-S3 to E3-S6 |

## User story

As a contributor, I want to switch each mess type on or off and dial it from light to heavy in the dataset settings, so that I can generate exactly the difficulty I want to test.

## Context

E3-S1 provides the engine; this story provides the control surface. Intensity must be easy to reason about (a number from 0 to 1) and translate into real rates differently for each type, because a "full" level of nickname substitution and a "full" level of balance mismatch are not equally common in real data.

## Scope

**In scope**
- `MessConfig` Pydantic model and its YAML representation.
- Intensity-to-rate mapping.
- Validation of unknown mess names and out-of-range values.
- Named intensity words usable on the command line.

**Out of scope**
- The preset files themselves (E3-S7).
- The CLI plumbing (E4-S4), though this story defines the override parsing function.

## Technical design

### Settings model

```yaml
mess:
  names:        { enabled: true,  intensity: 0.5 }
  households:   { enabled: true,  intensity: 0.3 }
  formats:      { enabled: true,  intensity: 0.5 }
  balances:     { enabled: false, intensity: 0.0 }
```

```python
class MessSetting(BaseModel):
    enabled: bool = False
    intensity: float = Field(0.0, ge=0.0, le=1.0)

class MessConfig(BaseModel):
    settings: dict[str, MessSetting]
    # validator: every key must be a registered mess type
```

A type is **active** only if `enabled` is true and `intensity > 0`. Missing keys default to disabled.

### Intensity to rate

For a type with `max_rate`, the share of eligible rows affected is `intensity * max_rate`. Each type declares `max_rate` (for example names 0.35, households 0.15, formats 0.40, balances 0.25). Where a type has several subtypes, the type splits the rate by fixed weights declared in code and documented in the type's module docstring.

### Named levels

Accept words as shorthand where a number is expected: `off` = 0, `light` = 0.2, `moderate` = 0.5, `heavy` = 0.8, `max` = 1.0. A `parse_level(text) -> float` function accepts either a word or a number.

### Overrides

`apply_overrides(config, overrides: list[str])` parses items like `names=heavy` or `balances=0.4` and returns a new config with the type enabled. Unknown names list the valid ones in the error.

## Files to create or change

- `src/onboardkit/datagen/config.py` (add `MessSetting`, `MessConfig`, `parse_level`, `apply_overrides`)
- `tests/datagen/test_mess_config.py`

## Acceptance criteria

- [ ] An unknown mess name in YAML fails validation and lists valid names.
- [ ] Intensity below 0 or above 1 fails validation.
- [ ] `enabled: false` with nonzero intensity is treated as inactive.
- [ ] `parse_level` accepts words and numbers and rejects anything else.
- [ ] `apply_overrides` returns a new object and leaves the original unchanged.
- [ ] The effective rate for each active type is available through one function, `effective_rate(config, mess_type)`.

## Test plan

- Table-driven tests for `parse_level` and `effective_rate`.
- YAML round trip test (dump then load equals original).
- Negative validation tests.

## Risks and notes

- `max_rate` values are first guesses. Tune them after viewing the `typical` dataset; changing them changes generated data, so record changes in a changelog note and bump the generator version (E4-S3).

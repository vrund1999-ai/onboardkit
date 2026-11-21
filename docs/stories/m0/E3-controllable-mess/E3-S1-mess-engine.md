# E3-S1: Mess engine and event log

| | |
|---|---|
| **Epic** | [E3: Controllable mess](../../../m0-foundation-epics.md#e3-controllable-mess) |
| **Size** | M |
| **Depends on** | E2-S1 |
| **Blocks** | E3-S2 to E3-S6, E5-S4 |

## User story

As a contributor, I want a small engine that applies pluggable mess types to the projected rows and records exactly what each one did, so that mess is deliberate, isolated, and explainable.

## Context

Mess is the point of the test data, but unexplained noise is useless: the answer keys (E5) need to know precisely what was changed, and the isolation requirement ("turning one type on affects only that kind of problem") needs a contract each type must honor. The engine defines that contract. Individual mess types arrive in E3-S3 to E3-S6.

## Scope

**In scope**
- `MessType` interface, registry, and execution order.
- `SourceDataset` container passed through the engine.
- `MessEvent` log schema.
- A no-op mess type used for tests.

**Out of scope**
- Concrete mess types.
- Settings and intensity (E3-S2).

## Technical design

### Container

```python
SourceDataset = dict[str, dict[str, list[SourceRow]]]   # source -> table -> rows
```

### Interface

```python
class MessType(Protocol):
    name: str                      # registry key, e.g. "names"
    description: str
    touches: frozenset[str]        # concept ids this type may modify, e.g. {"person.first_name", ...}
    structural: bool               # True if it may add or remove rows
    max_rate: float                # upper bound on the share of eligible rows affected at intensity 1.0

    def apply(self, ctx: MessContext, data: SourceDataset) -> list[MessEvent]: ...
```

`MessContext` provides: the rate for this run (`intensity * max_rate`), a seeded `random.Random` from `derive_rng(seed, "mess", name, source)`, the truth firm for lookups, and the `as_of_date`.

### Events

```python
@dataclass(frozen=True)
class MessEvent:
    event_id: str                       # "mess:<name>:<n>" sequential
    mess_type: str
    subtype: str                        # e.g. "nickname", "transposed_digits"
    source: str
    table: str
    row_uids: tuple[str, ...]           # rows affected
    concept: str | None                 # concept changed, if value-level
    before: str | None                  # value rendered as text
    after: str | None
    refs: TruthRefs                     # truth entities involved
    effect: Literal["entity_variant", "format_variant", "value_conflict", "structural"]
    severity: Literal["immaterial", "material"] | None = None
    ambiguity: Literal["low", "medium", "high"] | None = None
```

`effect` tells downstream answer keys how to use the event: entity variants inform matching, value conflicts inform reconciliation, format variants inform normalization, structural events change household shapes.

### Rules the engine enforces

1. **Declared scope.** After a type runs, the engine diffs the dataset against a snapshot and fails if any value changed in a concept not in `touches`, or if rows were added or removed by a non-`structural` type.
2. **Events match changes.** Every changed `(row_uid, concept)` must be covered by at least one event; otherwise raise.
3. **Order.** Types execute in a fixed registry order: `structural` types first (households), then value types (names, formats, balances). Order is part of the dataset definition.
4. **Isolation.** Each type uses its own random stream, so enabling or disabling one type never changes another's choices.

### Registry

A simple dictionary populated by an `@register` decorator. `get(name)` raises with the list of valid names for unknown keys.

## Files to create or change

- `src/onboardkit/datagen/mess/base.py` (interface, context, event)
- `src/onboardkit/datagen/mess/registry.py`
- `src/onboardkit/datagen/mess/engine.py` (`run_mess(data, enabled, ctx_factory) -> list[MessEvent]`)
- `src/onboardkit/datagen/mess/noop.py` (test-only)
- `tests/datagen/mess/test_engine.py`

## Acceptance criteria

- [ ] A registered type can be run and its events are returned in a stable order.
- [ ] A test type that modifies an undeclared concept makes the engine fail with a clear message.
- [ ] A test type that changes a value without emitting an event makes the engine fail.
- [ ] A non-structural type that removes a row makes the engine fail.
- [ ] Event ids are sequential and unique per mess type.
- [ ] Two mess types draw from independent random streams (verified by enabling one, then both, and comparing the first type's events).
- [ ] The engine never mutates truth objects.

## Test plan

- Unit tests with small hand-built `SourceDataset` fixtures.
- Negative tests for each enforcement rule.
- Stream-independence test as above.

## Risks and notes

- Rule 1 and 2 give the isolation guarantee a mechanical backing, so later mess types stay honest. Keep the diff fast: compare only rows that the type declared in its events plus a hash of the untouched rows.
- `before` and `after` are text renderings so events serialize cleanly to the answer key files.

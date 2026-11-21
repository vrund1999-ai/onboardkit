# E2-S5: Source coverage and overlap

| | |
|---|---|
| **Epic** | [E2: Multi-source messy exports](../../../m0-foundation-epics.md#e2-multi-source-messy-exports) |
| **Size** | M |
| **Depends on** | E2-S2, E2-S3, E2-S4 |
| **Blocks** | E4-S2 |

## User story

As a contributor, I want each source to hold only part of the firm, with some overlap and some stale extras, so that datasets exercise cross-source matching and reconciliation realistically.

## Context

If every source held every record, reconciliation would be trivial. Real exports overlap partially: the custodian has nearly every account, the CRM misses some people and links, and the spreadsheet omits households and still lists accounts that were closed. Coverage is applied after projection and before mess. Every omission or extra is logged, because missing records are discrepancies the answer key must know about (E5-S4).

## Scope

**In scope**
- Coverage configuration per source and per entity type.
- Deterministic selection of which truth entities each source omits.
- Stale extra rows (records for entities that no longer exist).
- A `CoverageEvent` log.

**Out of scope**
- Value-level mess such as balance drift (E3-S6).
- Household splitting and duplication (E3-S4).

## Technical design

### Configuration

```yaml
coverage:
  custodian:
    accounts: 1.00
  crm:
    persons: 0.97
    account_links: 0.90
  book_of_business:
    households: 0.85
    accounts: 0.80
    stale_extra_rate: 0.03   # extras as a share of included rows
```

A Pydantic `CoverageConfig` validates ranges (0 to 1). Presets (E3-S7) override rates; `clean` uses 1.0 for all and `stale_extra_rate: 0`.

### Selection

`apply_coverage(rows_by_source, firm, config, root_seed) -> (rows_by_source, events)`:

1. For each source and table, choose rows to omit by a seeded shuffle of row uids and cutting at `1 - rate`, using stream `derive_rng(seed, "coverage", source, table)`.
2. Guarantee rule: every truth account remains in at least one source, and every truth household appears in at least one source. If an omission would violate this, restore the omitted row from the lowest-numbered source.
3. For `stale_extra_rate`, create extra rows representing accounts that were closed or households that left: copy a random row, change its account number to a new fictional but plausible number not present in the truth, and mark `refs.account_id = None`. These rows land in the `Archive` sheet or are flagged `CLOSED` according to source habits.

### Events

```python
@dataclass(frozen=True)
class CoverageEvent:
    kind: Literal["omitted", "stale_extra"]
    source: str
    table: str
    row_uid: str | None       # None when the row was dropped before it existed
    refs: TruthRefs
```

Events are returned to the pipeline and consumed by the discrepancy answer key (E5-S4).

### Order in the pipeline

Project (E2-S2 to S4), then coverage, then mess (E3), then write. Because projection runs first, row uids are stable regardless of which rows are later dropped.

## Files to create or change

- `src/onboardkit/datagen/sources/coverage.py`
- Add `CoverageConfig` to `config.py` (coordinate with E4-S1)
- `tests/datagen/sources/test_coverage.py`

## Acceptance criteria

- [ ] With rates of 1.0 and no extras, output equals the projection exactly and no events are produced.
- [ ] With the `typical` rates, omitted share per source is within 3 percentage points of the configured rate on the 300-household dataset.
- [ ] Every truth account and household remains in at least one source after coverage.
- [ ] Stale extra rows have no truth account reference and use account numbers that do not collide with any truth account.
- [ ] Every omission and extra generates exactly one event.
- [ ] The same seed and config produce identical omissions.

## Test plan

- Property test over many seeds: guarantee rule holds.
- Event count equals the number of rows removed plus added.
- Determinism test across two runs.
- Test that changing the `crm` rate does not alter which rows the custodian omits (independent streams).

## Risks and notes

- Overlap tuning is a judgment call. Start with the sample rates and adjust after viewing the data with the E7-S2 walkthrough.
- Avoid making the spreadsheet so sparse that matching is impossible; at least a few households must appear in all three sources.

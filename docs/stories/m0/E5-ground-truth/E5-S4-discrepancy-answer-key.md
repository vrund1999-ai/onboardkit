# E5-S4: Discrepancy answer key

| | |
|---|---|
| **Epic** | [E5: Ground truth](../../../m0-foundation-epics.md#e5-ground-truth) |
| **Size** | M |
| **Depends on** | E5-S1, E3-S1 |
| **Blocks** | E5-S5 |

## User story

As a contributor, I want an answer key listing every real disagreement between sources, with its type and severity, so that later reconciliation can be scored on what it finds and what it misses.

## Context

Reconciliation (M4) should flag, for example, an account at the custodian missing from the CRM, or balances that differ. The generator knows exactly which disagreements it introduced, but disagreements also arise from each source's inherent habits (the spreadsheet's stale, rounded balances; omissions from coverage). The key must list **all** of them, not just the deliberate mess events, so that a perfect reconciler is not penalized for finding genuine differences.

## Scope

**In scope**
- A derived list of discrepancies from two independent methods that must agree.
- Authority and severity fields following the roadmap decisions.

**Out of scope**
- Resolution workflow (M4).
- Tolerance configuration beyond recording the generator's constants.

## Technical design

### File: `truth/discrepancies.csv`

| Field | Meaning |
|---|---|
| `discrepancy_id` | `D-000001`, sequential by sorted key |
| `kind` | `missing_in_source`, `value_conflict`, `stale_extra` |
| `entity_type` | `person`, `household`, `account` |
| `truth_id` | Entity involved (empty for stale extras) |
| `concept` | Concept id for value conflicts, empty otherwise |
| `sources` | Sources involved, separated by `|` |
| `authoritative_source` | Source the roadmap rules trust for this concept (custodian for money data, CRM for people data, book of business otherwise) |
| `authoritative_value` | Rendered value from the authoritative source |
| `other_values` | `source=value` pairs for the disagreeing sources, separated by `|` |
| `severity` | `immaterial` or `material` using the tolerance constants from E3-S6 |
| `origin_events` | Event ids (coverage or mess) that caused it, may be empty for inherent drift |

### Two derivations that must agree

1. **Event-based:** coverage events (`omitted`, `stale_extra`) and mess events with `effect = "value_conflict"`.
2. **State-based:** compare the final exported typed values of the same entity across sources using the authority table and tolerance; list every difference, regardless of cause. Format variants are normalized before comparison (they are not discrepancies), using the original typed value stored in `RawText.original`.

The written key is the **state-based** list, enriched with `origin_events` where an event explains it. A consistency check (also run in E5-S5) asserts that every event-based discrepancy appears in the state-based list. State-based extras with no event are labelled in `origin_events` as `inherent`; they should correspond to the book of business's rounding and drift, and the check reports their count.

### Missing records

`missing_in_source` is produced when an entity that should appear in a source (for example an account the CRM tracks links for, or any account in the book of business's advisors' scope) is absent after coverage. Define the expectation per source in one table in the code so it is reviewable:

| Source | Expected to contain |
|---|---|
| Custodian | All accounts |
| CRM | All persons and households, and an account link for each owner of each open account |
| Book of business | All households and accounts (closed ones on `Archive`) |

### Severity

Constants from `balances.py` (E3-S6): immaterial if the absolute difference is at most `$1.00` or the relative difference at most `0.1 percent`, whichever is larger. Missing records and status or type mismatches are `material`.

## Files to create or change

- `src/onboardkit/datagen/answer_keys/discrepancies.py`
- `tests/datagen/answer_keys/test_discrepancies.py`

## Acceptance criteria

- [ ] A `clean` dataset has zero discrepancies, apart from the book of business's documented inherent drift (if the `clean` preset disables drift, zero).
- [ ] Every coverage omission and stale extra appears as a discrepancy.
- [ ] Every mess event with `effect = "value_conflict"` appears as a discrepancy with matching severity.
- [ ] State-based and event-based derivations agree (event set is a subset of the state set) on all presets.
- [ ] Format-only variants never appear as discrepancies.
- [ ] `authoritative_source` follows the roadmap defaults for every concept.
- [ ] Output is byte-identical across runs.

## Test plan

- Hand-built mini cases for each kind.
- Preset-level consistency test.
- Test that a purely format-mess dataset yields no new discrepancies.

## Risks and notes

- State-based derivation is the safeguard against incomplete event logging. If the two disagree, fix the event emitter rather than relaxing the check.
- Decide in E2-S4 whether `clean` turns off the spreadsheet's inherent drift; if it does not, this key will list immaterial differences even for `clean`, and the test above must be adjusted. Prefer making `clean` truly clean.

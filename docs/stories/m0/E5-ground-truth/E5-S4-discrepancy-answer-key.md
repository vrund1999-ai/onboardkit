# E5-S4: Discrepancy answer key

| | |
|---|---|
| **Epic** | [E5: Ground truth](../../../epics/m0-foundation-epics.md#e5-ground-truth) |
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

- [x] A `clean` dataset has zero discrepancies, apart from the book of business's documented inherent drift (if the `clean` preset disables drift, zero).
- [x] Every coverage omission and stale extra appears as a discrepancy.
- [x] Every mess event with `effect = "value_conflict"` appears as a discrepancy with matching severity.
- [x] State-based and event-based derivations agree (event set is a subset of the state set) on all presets.
- [x] Format-only variants never appear as discrepancies.
- [x] `authoritative_source` follows the roadmap defaults for every concept.
- [x] Output is byte-identical across runs.

## Test plan

- Hand-built mini cases for each kind.
- Preset-level consistency test.
- Test that a purely format-mess dataset yields no new discrepancies.

## Risks and notes

- State-based derivation is the safeguard against incomplete event logging. If the two disagree, fix the event emitter rather than relaxing the check.
- Decide in E2-S4 whether `clean` turns off the spreadsheet's inherent drift; if it does not, this key will list immaterial differences even for `clean`, and the test above must be adjusted. Prefer making `clean` truly clean.

## Notes

- `answer_keys/discrepancies.py` has `build_discrepancies` (the state-based list), `check_consistency` (event-based entries missing from it), `inherent_count`, `write_discrepancies` (opt-in until E5-S5 registers the defaults) and `authority`.
- `CoverageEvent` gained an `event_id` property (`cov:<kind>:<row uid>`) so coverage events can be cited in `origin_events` next to mess event ids.
- Value conflicts cover four account facts: balance, type, status and registration. The book of business has no status or registration column, so its status is read from the sheet (`Archive` means closed) and from the status-mismatch note, and its registration from the registration-mismatch note. People and households appear only as `missing_in_source` (the CRM is the only source of person detail).
- Deviation: the CRM is expected to hold a link for each owner of **every** account, not only open ones, because that is what the generator writes for closed accounts too.
- Deviation: when events explain a value conflict, its severity is the events' label (a `small_drift` of up to 0.5 percent is labelled immaterial by the balances mess type, although it can exceed the 0.1 percent tolerance). Conflicts with no event use the tolerance rule for balances and are `material` for the other facts.
- A custodian balance made stale can only be seen against another source's balance. A stale event on an account that the book of business lacks is therefore not reported as an inconsistency.
- The consistency check found a real defect while writing the key: stale-extra detection must unwrap `RawText.original`, otherwise a format variant on an account number looks like a stale extra.
- With the default book-of-business drift the `typical` and `nightmare` presets list many `inherent` balance differences (hundreds on `typical/default`). `clean` has none, because it disables drift.


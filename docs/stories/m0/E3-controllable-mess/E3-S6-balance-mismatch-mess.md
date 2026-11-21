# E3-S6: Balance mismatch mess

| | |
|---|---|
| **Epic** | [E3: Controllable mess](../../../epics/m0-foundation-epics.md#e3-controllable-mess) |
| **Size** | M |
| **Depends on** | E3-S1, E3-S2 |
| **Blocks** | E3-S7, E5-S4 |

## User story

As a contributor, I want intentional value disagreements between sources, with known size and type, so that reconciliation can be tested on discrepancies of different severity.

## Context

Balances only exist at the custodian and in the book of business, so they are where money disagreements arise. The roadmap decision says the custodian wins for money, but disagreements are still reported. The spreadsheet's inherent drift (E2-S4) is small background noise. This mess type creates deliberate, labelled disagreements, including ones inside any sensible tolerance, so tolerance handling can be tested in M4. It also covers status and account-type disagreements between sources.

## Scope

**In scope**
- A `balances` mess type with value, status, and type mismatch subtypes.
- Severity labels (`immaterial` or `material`) on every event.

**Out of scope**
- Missing records (E2-S5).
- Format-only differences (E3-S5).

## Technical design

### Mess type

`name = "balances"`, `max_rate = 0.25`, `structural = False`,
`touches = {"account.balance", "account.balance_as_of", "account.status", "account.type", "account.registration"}`.

Eligible rows: book of business and CRM account rows that correspond to a custodian account (via truth refs). The custodian is treated as authoritative and is not modified, except for `stale_value`, where the custodian row is the one carrying an older as-of date.

### Subtypes

| Subtype | What changes | Size | Severity |
|---|---|---|---|
| `rounding_diff` | Book balance differs from custodian by $0.01 to $1.00 | tiny | immaterial |
| `small_drift` | Differs by up to 0.5 percent | small | immaterial |
| `transposed_digits` | Two adjacent digits swapped | varies | material |
| `magnitude_error` | Missing or extra zero (limited to balances under $200,000 to avoid absurd values) | large | material |
| `stale_value` | Book value is the previous quarter-end value; `balance_as_of` is older | moderate | material if difference over 2 percent, else immaterial |
| `status_mismatch` | Book or CRM says open when custodian says closed (or the reverse) | n/a | material |
| `type_mismatch` | Account type differs (for example Roth versus Traditional) | n/a | material |
| `registration_mismatch` | Owner on record differs (one owner dropped from a joint account) | n/a | material |

Weights favor immaterial cases (about 40 percent) so tolerance logic is exercised often.

### Rules

- A given account receives at most one balance-family event per source.
- Changed balances stay positive and finite, with two decimal places.
- `stale_value` derives its prior value deterministically: truth balance multiplied by a draw in a plausible band, tied to a recorded `prior_as_of` (previous quarter end).
- The tolerance used to label severity is a constant in the module (`$1.00` absolute or `0.1 percent` relative, whichever is larger) and recorded in the event, so the later reconciliation milestone can compare against it.

### Events

`effect = "value_conflict"`. `severity` required. `before` is the authoritative value, `after` the disagreeing value. `refs.account_id` set. These events are the primary input to the discrepancy answer key (E5-S4).

## Files to create or change

- `src/onboardkit/datagen/mess/balances.py`
- `tests/datagen/mess/test_balances.py`

## Acceptance criteria

- [ ] At intensity 0, no values change.
- [ ] Every subtype is producible and appears at high intensity on the 300-household dataset.
- [ ] Every event has a severity, and `rounding_diff` and `small_drift` are always `immaterial`.
- [ ] No balance becomes zero, negative, or non-numeric.
- [ ] The custodian's balances are untouched, except where `stale_value` is applied by design and documented.
- [ ] No account receives two balance-family events in the same source.
- [ ] Tolerance constants are exposed in the module and recorded in events.

## Test plan

- Unit tests per subtype with fixed seeds.
- Severity classification tests on boundary values around the tolerance.
- Invariant test across seeds: all balances positive with two decimals.

## Risks and notes

- `magnitude_error` can produce absurd values if unchecked; the under-$200,000 limit is deliberate.
- Severity here is the generator's intention. Real reconciliation will apply the firm's own tolerance rules in M4.

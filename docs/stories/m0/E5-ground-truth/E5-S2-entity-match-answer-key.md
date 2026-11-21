# E5-S2: Entity match answer key

| | |
|---|---|
| **Epic** | [E5: Ground truth](../../../m0-foundation-epics.md#e5-ground-truth) |
| **Size** | M |
| **Depends on** | E5-S1 |
| **Blocks** | E5-S5 |

## User story

As a contributor, I want an answer key saying which source rows refer to the same real person, household, or account, so that later entity matching can be scored precisely.

## Context

Entity matching (M2) will propose groups of rows that represent one entity. To judge it, we need the true groups, including awkward ones: duplicate households, households split across two CRM records, and name variants. Because truth identifiers sit behind provenance (E5-S1), the groups can be derived exactly, with difficulty labels from the mess events.

## Scope

**In scope**
- Group files for persons, households, and accounts.
- Difficulty labelling based on mess events.
- Summary counts.

**Out of scope**
- Evaluation code that scores a candidate matcher (M2).
- Cross-firm matching.

## Technical design

### Files (under `truth/`)

**`entity_matches.csv`**, one row per (entity, exported row) membership:

| Field | Meaning |
|---|---|
| `entity_type` | `person`, `household`, or `account` |
| `truth_id` | The group identifier, for example `P-00012` |
| `row_uid` | Member row |
| `source`, `file`, `sheet`, `row_number` | Locator copied from provenance |
| `difficulty` | `easy`, `moderate`, or `hard` (rules below) |
| `variant_events` | Event ids that altered this row's identifying values, separated by `|` |

**`entity_groups.csv`**, one row per group: `entity_type`, `truth_id`, `row_count`, `sources` (distinct, separated by `|`), `max_difficulty`.

### Derivation

1. Group provenance records by truth id per entity type: persons from `person_ids` (a joint account row contributes to each owner), households from `household_id`, accounts from `account_id`.
2. A group appears in the key only if it has at least one row; entities invisible in all sources (impossible given the coverage guarantee, but checked) raise an error.
3. Link mess events to rows through `row_uids` and `refs` to compute difficulty:
   - `easy`: no identifying value was varied for any row in the group.
   - `moderate`: at least one `entity_variant` event with ambiguity `low` or `medium`, or a format variant on an account number.
   - `hard`: any event with ambiguity `high`, a `split` or `duplicate` household event, or two different people in the same household sharing a first initial and surname.
4. `max_difficulty` is the hardest among a group's rows.

### Pairs for convenience

A helper `expected_pairs(entity_type)` yields every unordered pair of rows in the same group (excluding pairs within one source row set where that would be trivially the same row). Used by later scoring code; not written to disk.

### Important cases

- Duplicate CRM households: two household groups in the CRM map to **one** truth household, and `entity_groups.csv` shows `row_count` covering both.
- Split households: members' rows appear under two CRM household ids but one truth household.
- Joint accounts: one account group, two person groups share it.

## Files to create or change

- `src/onboardkit/datagen/answer_keys/entity_matches.py`
- `tests/datagen/answer_keys/test_entity_matches.py`

## Acceptance criteria

- [ ] Every provenance row with at least one truth reference appears in `entity_matches.csv` for each entity type it references.
- [ ] Stale extra rows (no account reference) do not appear in account groups.
- [ ] Duplicate and split households from mess produce one household group each, spanning both CRM household ids.
- [ ] Difficulty values follow the rules above and are unit tested for each category.
- [ ] A dataset generated with `clean` has every group `easy`.
- [ ] Group counts agree with the truth firm: persons seen equals persons in truth for fully covered datasets.
- [ ] Files are byte-identical across runs.

## Test plan

- Hand-built mini dataset covering joint account, duplicate household, split household, nickname variant.
- `clean` preset test for all-easy.
- Property test: union of all group members equals the set of provenance rows with refs.

## Risks and notes

- Difficulty is the generator's view. Later evaluation may add its own measures; do not treat the labels as a model of matcher difficulty, only of constructed variation.
- Keep pair expansion out of the file format; it grows quadratically.

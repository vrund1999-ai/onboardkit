# E3-S4: Household mess

| | |
|---|---|
| **Epic** | [E3: Controllable mess](../../../epics/m0-foundation-epics.md#e3-controllable-mess) |
| **Size** | L |
| **Depends on** | E3-S1, E3-S2 |
| **Blocks** | E3-S7 |

## User story

As a contributor, I want households that are duplicated, split, or missing in the source data, so that household reconstruction can be tested against known structure.

## Context

The README lists "households are duplicated, split, or missing" as a core problem. Only the CRM and the spreadsheet have a household concept, so this mess applies to them. These are the only structural changes in M0 that add rows, so the type declares `structural = True` and runs before value-level types.

## Scope

**In scope**
- A `households` mess type with three subtypes: `duplicate`, `split`, `missing`.
- Fresh source identifiers for any new household or contact rows.

**Out of scope**
- Trusts, business accounts, and deceased clients (deferred from M0).
- Missing records caused by coverage rather than by household logic (E2-S5).

## Technical design

### Mess type

`name = "households"`, `structural = True`, `max_rate = 0.15`,
`touches = {"household.source_id", "household.name", "person.source_id", "person.household_role", "household.advisor"}`.

Eligible households: those present in the CRM (for `duplicate` and `split`) and those with a name cell in the book of business (for `missing`).

### Subtypes

**`duplicate`** (weight 0.35). Choose a household in the CRM. Copy all its contact rows with new `contact_id` values and a new `household_id`. Apply a mild variation to the household name (for example `Smith Household` becomes `Smith, John & Jane` or `The Smiths`). Truth refs stay the same, so the answer key records two contact rows mapping to one person. Tag every copied row with the event.

**`split`** (weight 0.40). Choose a multi-member household. Move one non-primary member (spouse or dependent) to a new `household_id` with a household name built from that member's own name. Their role becomes `Primary` in the new household. Their linked accounts follow them in the links table. The truth household is unchanged, so the answer key records that two CRM households correspond to one real household.

**`missing`** (weight 0.25). For the chosen contacts, blank `household_id`, `household_name`, and `household_role`, leaving orphan contact rows. In the book of business, blank the household cell on the first row of the block. Truth refs remain.

### Constraints

- A household is subject to at most one household mess event per run.
- Splitting never leaves a household with zero members.
- New source ids come from the same stream as the exporter's source ids so formats look alike and cannot be guessed to be synthetic.
- Row ordering of new rows follows the original household.

### Events

`effect = "structural"`. `refs` carries the true `household_id` and the person ids affected. `subtype` is one of `duplicate`, `split`, `missing`. `row_uids` lists every new or changed row. These events feed the entity match answer key (E5-S2) with expected merge groups.

## Files to create or change

- `src/onboardkit/datagen/mess/households.py`
- `tests/datagen/mess/test_households.py`

## Acceptance criteria

- [x] At intensity 0, no rows are added, changed, or removed.
- [x] `duplicate` produces a second household in the CRM with the same members' truth refs and different source ids.
- [x] `split` yields two CRM households whose members' truth refs share one truth household id.
- [x] `missing` produces contact rows with blank household fields but unchanged person data.
- [x] No household receives more than one event.
- [x] Contact and household source ids remain unique per source after mess.
- [x] Linked-account rows stay consistent with the moved or duplicated contacts (no orphan links).
- [x] The engine's change-versus-event check passes.

## Test plan

- Unit tests for each subtype on a hand-built dataset.
- Referential integrity test between contacts and links after each subtype.
- Statistical test of household shares at moderate intensity on the 300-household dataset.
- Test that running with only `households` enabled changes nothing outside the CRM and book of business.

## Risks and notes

- This is the most intricate mess type because it adds rows and must keep two files consistent. Build and test the CRM side first, then the spreadsheet.
- Keep the truth untouched. Correct merge groups are derived, not stored on the rows.

## Notes

- Each truth household gets at most one event, and each event covers one source table: `duplicate` and `split` and the CRM form of `missing` write to the CRM `contacts` table, the spreadsheet form to its sheet's table. Whether `missing` hits the CRM or the spreadsheet is chosen at random when a household is in both.
- Eligible households are those with CRM contacts or a spreadsheet block with a household name; the selection probability is the effective rate. At 0.075 on the 300-household dataset that gave 17 of 300 households in one run.
- A moved contact keeps its contact id, so its linked-account rows stay valid without being rewritten. Duplicated contacts get new contact ids and do not get copies of the link rows, so no link ever points at a missing contact.
- Duplicate rows use the original row's uid plus `-dup`, so they sit next to the original in the written file. New ids copy the format of the CRM ids already present rather than drawing from the exporter's own stream, which the mess type cannot see.
- In the CRM the missing fields are written as empty cells (values `None`); in the spreadsheet the household cell of the first row of the block becomes an empty string, which leaves the cell blank in the workbook.
- A split household is named `<First> <Last> Household`, after the CRM's own convention. A duplicate's name varies to `Last, First & First` or `The Lasts`.


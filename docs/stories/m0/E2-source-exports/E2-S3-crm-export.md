# E2-S3: CRM export

| | |
|---|---|
| **Epic** | [E2: Multi-source messy exports](../../../epics/m0-foundation-epics.md#e2-multi-source-messy-exports) |
| **Size** | M |
| **Depends on** | E2-S1, E1-S3 |
| **Blocks** | E2-S5 |

## User story

As a contributor, I want a CRM-style export of people, households, and linked accounts, so that datasets include the source that knows who clients are and how they are grouped.

## Context

The CRM is the default source of truth for people data and household relationships. It stores contacts and a household grouping, with only a loose list of linked account numbers and no balances. Its style is machine-friendly (`snake_case`, ISO dates), which contrasts with the custodian and the spreadsheet. The fictional product is `ClientHub`.

## Scope

**In scope**
- A `CrmExporter` producing two related CSV files.
- Reserved-domain emails and fictional phone numbers.

**Out of scope**
- Activity history, notes, tasks.
- Mess (E3) and coverage (E2-S5).

## Technical design

### Files

Both UTF-8 without BOM, `\n` line endings, comma delimiter, minimal quoting.

**`crm_contacts.csv`**, one row per person:

| Header | Concept | Format |
|---|---|---|
| `contact_id` | `person.source_id` | `C` plus six digits, unrelated to truth ids |
| `first_name` | `person.first_name` | as is |
| `last_name` | `person.last_name` | as is |
| `suffix` | `person.suffix` | as is, often blank |
| `date_of_birth` | `person.date_of_birth` | ISO `%Y-%m-%d` |
| `email` | `person.email` | lower case; domains `example.com` or `example.test` only |
| `phone` | `person.phone` | `(555) 010-NNNN` style using the 555-01XX fictional range |
| `street` | `person.address_line1` | as is |
| `city`, `state`, `zip` | address parts | state as two letters |
| `household_id` | `household.source_id` | `H` plus four digits |
| `household_name` | `household.name` | for example `Smith Household` |
| `household_role` | `person.household_role` | `Primary`, `Spouse`, `Dependent` |
| `advisor` | `household.advisor` | advisor display name |
| `client_since` | `person.client_since` | ISO date |

**`crm_linked_accounts.csv`**, one row per account-to-contact link:

| Header | Concept | Format |
|---|---|---|
| `contact_id` | `person.source_id` | matches contacts file |
| `account_number` | `account.number` | as the CRM holds it (same digits as custodian, no formatting) |
| `account_type` | `account.type` | long text (`Joint Brokerage`, `Roth IRA`) |

Joint accounts produce one link row per owner.

### Projection

- Source identifiers (`contact_id`, `household_id`) are generated from a dedicated stream and carry **no** relation to truth ids, so matching cannot be solved by string parsing.
- A deterministic map `truth id -> source id` is kept per run and handed to the answer key writer (E5-S2).
- `household_name` derives from the primary member's last name, with ` Household` appended.

## Files to create or change

- `src/onboardkit/datagen/sources/crm.py`
- `tests/datagen/sources/test_crm.py`

## Acceptance criteria

- [ ] Every truth person appears exactly once in `crm_contacts.csv` before coverage is applied.
- [ ] Every account owner gets a link row for each account they own.
- [ ] All emails use only `example.com` or `example.test`; all phones fall in the fictional 555-01XX range.
- [ ] Source ids contain no truth id substring and are unique per source.
- [ ] Dates are ISO formatted; roles use the capitalized values above.
- [ ] Locators resolve for both files.
- [ ] The README's `account_number` header example is present.

## Test plan

- Contract test: join links to contacts on `contact_id` yields no orphans.
- Test that email and phone validators accept every generated value and reject real-looking ones.
- Snapshot of the first rows for the sample dataset.

## Risks and notes

- Linked-account completeness is deliberately weaker than the custodian's. That is applied through coverage (E2-S5), not here.
- Keep the source-id map out of the export directory; it belongs to the truth files.

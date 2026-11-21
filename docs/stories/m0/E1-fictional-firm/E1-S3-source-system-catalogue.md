# E1-S3: Source system and concept catalogue

| | |
|---|---|
| **Epic** | [E1: Fictional firm and shared vocabulary](../../../epics/m0-foundation-epics.md#e1-fictional-firm-and-shared-vocabulary) |
| **Size** | M |
| **Depends on** | E1-S1, E1-S2 |
| **Blocks** | E2-S2, E2-S3, E2-S4, E5-S3 |

## User story

As a contributor, I want a catalogue that says which facts each source holds and under what column names, so that exports, answer keys, and later mapping work all share one reference.

## Context

Real firms split data across systems: the custodian knows money, the CRM knows people, the spreadsheet knows whatever the operations team wrote down. The exports in E2 must mirror that split. The catalogue also defines a **concept vocabulary**: stable identifiers for the meaning of each column (for example `account.number`). The column mapping answer key (E5-S3) uses these identifiers to say what each source column truly means. The concept vocabulary is an evaluation reference, not the M1 data model, which may name and structure things differently.

## Scope

**In scope**
- A document `docs/source-systems.md` describing each source and a field-level matrix.
- A machine-readable concept catalogue, `src/onboardkit/datagen/sources/concepts.yaml`, created once E6-S1 provides the package; until then the document holds the draft.

**Out of scope**
- Writing any exporter (E2).
- The M1 canonical schema.

## Technical design

### Concept identifiers

Dotted lowercase, `<entity>.<attribute>`. Initial set:

| Concept | Meaning |
|---|---|
| `household.name` | Display name of the household |
| `household.source_id` | The source's own household key |
| `household.advisor` | Responsible advisor |
| `person.source_id` | The source's own person key |
| `person.full_name` | Whole name as written |
| `person.first_name`, `person.last_name`, `person.suffix` | Name parts |
| `person.date_of_birth` | Date of birth |
| `person.tax_id_last4` | Last four digits of a synthetic tax identifier |
| `person.email`, `person.phone` | Contact details |
| `person.address_line1`, `person.address_city`, `person.address_state`, `person.address_postal` | Address parts |
| `person.household_role` | Primary, spouse, or dependent |
| `person.client_since` | Date relationship began |
| `account.number` | Account number |
| `account.type` | Account type |
| `account.registration` | Legal title on the account |
| `account.status` | Open, closed, restricted |
| `account.open_date` | Date opened |
| `account.balance` | Market value |
| `account.balance_as_of` | Date of that market value |
| `account.owner_names` | Owner names as printed on the registration |
| `account.custodian` | Name of the custodian |
| `meta.notes` | Free text with no structured meaning |
| `meta.review_date` | Date of last internal review |

### Source matrix

For each concept: which of the three sources carries it (yes, partial, no), the typical column header in that source, and the typical format. Guidance for realism:

- **Custodian:** accounts, registration, status, open date, balance and as-of date, owner names as printed, mailing address, tax id last four. No household concept. No email.
- **CRM:** people, contact details, date of birth, household name and key, household role, advisor, client-since, a list of linked account numbers without balances. Account numbers sometimes missing or mistyped.
- **Book of business:** household name, advisor, account number, account type, a hand-maintained balance, notes, review date. Balances are approximate and stale.

### Per-source conventions

For each source, record: file type, header style (for example `Acct #`, `account_number`, `AcctNo`), date format, number format, whether names are one column or two, encoding, and sheet layout.

## Files to create or change

- Create `docs/source-systems.md`.
- Create `src/onboardkit/datagen/sources/concepts.yaml` (after E6-S1) listing each concept with `id`, `description`, and `value_type` (`string`, `date`, `money`, `enum`).

## Acceptance criteria

- [x] Every concept in the table has an id, description, and value type.
- [x] The matrix shows, for each concept, which sources carry it and under what header.
- [x] Each of the three sources has stated conventions for headers, dates, numbers, names, and encoding.
- [x] Every fact appears in at least one source, and at least five concepts appear in two or more sources, so reconciliation has something to compare.
- [x] `concepts.yaml` loads and validates with a Pydantic model (id pattern, unique ids).
- [x] The README examples of mess (`Acct #`, `account_number`, `AcctNo`) appear as headers for `account.number` in different sources.

## Test plan

- Unit test: load `concepts.yaml`, assert ids are unique, match `^[a-z_]+\.[a-z0-9_]+$`, and every `value_type` is allowed.
- Unit test: every concept listed in the document matrix exists in `concepts.yaml` (a small parser over the document table, or a parallel list in the test).

## Risks and notes

- Adding a column to an exporter later requires adding its concept here first. State this in the document.
- Keep concept ids stable once published; E5-S3 answer keys depend on them.

## Notes

- Concept set grew from 24 rows in the outline to 29 ids: `person.full_name` is carried by the custodian's `Primary Owner` column, and names, addresses, and tax id are shared by custodian and CRM so reconciliation has overlap.
- Source conventions in `docs/source-systems.md` describe the clean form; mess (E3) varies them.

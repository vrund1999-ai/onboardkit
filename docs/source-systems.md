# Source systems and concept catalogue

What each of the three sources of [Lantern Ridge Wealth Partners](fictional-firm.md) holds, and under what column names. Exporters (E2), answer keys (E5) and later mapping work share this reference. Terms are defined in the [glossary](glossary.md).

**Rule for contributors.** Adding a column to an exporter means adding its concept here and in `src/onboardkit/datagen/sources/concepts.yaml` first. Concept ids are stable once published: column-mapping answer keys depend on them. The concept vocabulary is an evaluation reference, not the M1 [common data model](glossary.md#common-data-model).

## Concept ids

Dotted lowercase, `<entity>.<attribute>`, matching `^[a-z_]+\.[a-z0-9_]+$`. Value types are `string`, `date`, `money`, and `enum`.

## Source matrix

Each cell shows the typical header the source uses, or `no` when the source does not carry the concept. `(partial)` means the source carries only part of it (for example, an address line without city, or account numbers listed loosely).

| Concept | Meaning | Type | Custodian | CRM | Book of Business |
|---|---|---|---|---|---|
| `household.name` | Display name of the household | string | no | `household_name` | `Household` |
| `household.source_id` | The source's own household key | string | no | `household_id` | no |
| `household.advisor` | Responsible advisor | string | no | `advisor` | `Advisor` |
| `person.source_id` | The source's own person key | string | no | `contact_id` | no |
| `person.first_name` | Given name | string | no | `first_name` | no |
| `person.last_name` | Family name | string | no | `last_name` | no |
| `person.suffix` | Name suffix such as Jr. or III | string | no | `suffix` | no |
| `person.date_of_birth` | Date of birth | date | no | `date_of_birth` | no |
| `person.tax_id_last4` | Last four digits of a synthetic tax identifier | string | `TIN Last4` | no | no |
| `person.email` | Email address | string | no | `email` | no |
| `person.phone` | Phone number | string | no | `phone` | no |
| `person.address_line1` | Street address (the custodian holds the whole address on one line) | string | `Mail Addr` (partial) | `street` | no |
| `person.address_city` | City | string | no | `city` | no |
| `person.address_state` | State | string | no | `state` | no |
| `person.address_postal` | Postal code | string | no | `zip` | no |
| `person.household_role` | Primary, spouse, or dependent | enum | no | `household_role` | no |
| `person.client_since` | Date the relationship began | date | no | `client_since` | no |
| `account.number` | Account number | string | `Acct #` | `account_number` | `AcctNo` |
| `account.type` | Account type | enum | `Acct Type` | `account_type` | `Type` |
| `account.registration` | Legal title on the account | string | `Account Title` | no | no |
| `account.status` | Open, closed, or restricted | enum | `Status` | no | no |
| `account.open_date` | Date the account was opened | date | `Open Date` | no | no |
| `account.balance` | Market value of the account | money | `Market Value` | no | `Balance` |
| `account.balance_as_of` | Date of the market value | date | `Value As Of` | no | no |
| `account.owner_names` | Owner names as printed on the registration | string | `Owner 1` / `Owner 2` | no | no |
| `meta.notes` | Free text with no structured meaning | string | no | no | `Notes` |
| `meta.review_date` | Date of last internal review | date | no | no | `Last Review` |

Every concept appears in at least one source, and 6 appear in two or more, so reconciliation always has something to compare. The three README examples of account-number headers, `Acct #`, `account_number` and `AcctNo`, appear in the custodian, CRM and Book of Business columns respectively. The CRM column holds a semicolon-separated list.

## Per-source conventions

These are the clean forms, as specified by the export stories (E2-S2 to E2-S4). Mess (E3) layers variations on top, such as shifted headers, text dates, and extra blank rows.

### Custodian (Meridian Custody Services)

| Aspect | Convention |
|---|---|
| File | One CSV: `custodian_accounts.csv`, one row per account, with two report lines above the header and a `Total records` line below the data |
| Headers | Title Case with symbols and spaces, for example `Acct #`, `Value As Of` |
| Dates | `MM/DD/YYYY`, except `Value As Of` which is `YYYYMMDD` |
| Numbers | Thousands separators and two decimals, no currency symbol, for example `152,340.55` |
| Names | Upper case, `LAST, FIRST M`, one owner per column (`Owner 1`, `Owner 2`) |
| Codes | Account types as codes (`IND`, `JNT`, `TIRA`, `ROTH`, `RIRA`, `529`); statuses in upper case |
| Encoding | UTF-8 with a byte order mark, CRLF line endings, every field quoted |
| Shape | Flat. No household concept. No email address. The mailing address is one line. |
| Role | Source of truth for money data: balance, status, registration |

### CRM (Cedarline CRM)

| Aspect | Convention |
|---|---|
| Files | Two CSVs: `crm_contacts.csv` (one row per person) and `crm_linked_accounts.csv` (one row per account-to-contact link) |
| Headers | `snake_case`, for example `first_name`, `household_id`, `account_number` |
| Dates | ISO `YYYY-MM-DD` |
| Numbers | Not applicable. No balances |
| Names | Separate `first_name`, `last_name` and `suffix` columns, mixed case |
| Identifiers | Its own ids (`C000123`, `H0042`) that bear no relation to the custodian or to any truth id |
| Encoding | UTF-8 without a byte order mark, LF line endings, minimal quoting |
| Shape | Linked tables. Accounts appear only as links by account number and long-text type |
| Role | Source of truth for people data: names, contact details, household and role, advisor |

### Book of Business (Excel)

| Aspect | Convention |
|---|---|
| File | One workbook, `book_of_business.xlsx`: a `Summary` sheet, a sheet per advisor, and an `Archive` sheet |
| Headers | Short and human, for example `AcctNo`, `Last Review`, on row 5 under title rows |
| Dates | Excel date cells shown as `d-mmm-yy` |
| Numbers | Currency format; balances rounded to the nearest 100 and often stale |
| Names | One column for the household, `Smith, John & Jane`, written on the first row of each household block only |
| Encoding | Not applicable (binary workbook) |
| Shape | Blocks of rows per household with spacer rows, a notes column, no formal keys |
| Role | Lowest priority. Used for context and to find accounts missing elsewhere |

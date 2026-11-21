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
| `person.full_name` | Whole name as written | string | `Primary Owner` (partial) | no | no |
| `person.first_name` | Given name | string | no | `first_name` | no |
| `person.last_name` | Family name | string | no | `last_name` | no |
| `person.suffix` | Name suffix such as Jr. or III | string | no | `suffix` | no |
| `person.date_of_birth` | Date of birth | date | no | `date_of_birth` | no |
| `person.tax_id_last4` | Last four digits of a synthetic tax identifier | string | `Tax ID (Last 4)` | `tax_id_last4` (partial) | no |
| `person.email` | Email address | string | no | `email` | no |
| `person.phone` | Phone number | string | no | `phone` | no |
| `person.address_line1` | First line of the address | string | `Mailing Address` (partial) | `address_line1` | no |
| `person.address_city` | City | string | `City` | `city` | no |
| `person.address_state` | State | string | `State` | `state` | no |
| `person.address_postal` | Postal code | string | `Zip` | `postal_code` | no |
| `person.household_role` | Primary, spouse, or dependent | enum | no | `household_role` | no |
| `person.client_since` | Date the relationship began | date | no | `client_since` | no |
| `account.number` | Account number | string | `Acct #` | `account_number` (partial) | `AcctNo` |
| `account.type` | Account type | enum | `Account Type` | no | `Type` |
| `account.registration` | Legal title on the account | string | `Registration` | no | no |
| `account.status` | Open, closed, or restricted | enum | `Status` | no | `Status` (partial) |
| `account.open_date` | Date the account was opened | date | `Open Date` | no | no |
| `account.balance` | Market value of the account | money | `Market Value` | no | `Balance` |
| `account.balance_as_of` | Date of the market value | date | `Value As Of` | no | `Updated` (partial) |
| `account.owner_names` | Owner names as printed on the registration | string | `Owner Names` | no | no |
| `account.custodian` | Name of the custodian | string | `Custodian` | no | `Custodian` (partial) |
| `meta.notes` | Free text with no structured meaning | string | no | `notes` | `Notes` |
| `meta.review_date` | Date of last internal review | date | no | no | `Last Review` |

Every concept appears in at least one source, and 14 appear in two or more, so reconciliation always has something to compare. The three README examples of account-number headers, `Acct #`, `account_number` and `AcctNo`, appear in the custodian, CRM and Book of Business columns respectively. The CRM column holds a semicolon-separated list.

## Per-source conventions

### Custodian (Meridian Custody Services)

| Aspect | Convention |
|---|---|
| File | One CSV: `custodian_accounts.csv`, one row per account |
| Headers | Title Case with symbols and spaces, for example `Acct #`, `Value As Of` |
| Dates | `MM/DD/YYYY` |
| Numbers | Plain decimals with two places, no currency symbol or thousands separator, for example `152340.55` |
| Names | Upper case, printed on the registration as `LAST, FIRST M`; several owners joined with ` & ` |
| Encoding | Windows-1252 with CRLF line endings |
| Shape | Flat. No household concept. No email address. |
| Role | Source of truth for money data: balance, status, registration |

### CRM (Cedarline CRM)

| Aspect | Convention |
|---|---|
| Files | Two CSVs: `crm_contacts.csv` (one row per person) and `crm_households.csv` (one row per household) |
| Headers | `snake_case`, for example `first_name`, `household_id` |
| Dates | ISO `YYYY-MM-DD` |
| Numbers | Not applicable. No balances |
| Names | Separate `first_name`, `last_name` and `suffix` columns, mixed case |
| Encoding | UTF-8 with LF line endings |
| Shape | Linked tables. Accounts appear only as a loose, semicolon-separated list of account numbers per person, which may be missing or mistyped |
| Role | Source of truth for people data: names, contact details, household and role, advisor |

### Book of Business (Excel)

| Aspect | Convention |
|---|---|
| File | One workbook, `book_of_business.xlsx`: a sheet per advisor and an `Archive` sheet |
| Headers | Short and human, for example `AcctNo`, `Last Review`, with a title row above the header row |
| Dates | Excel date cells shown as `M/D/YY`, some entered as text |
| Numbers | Currency format with thousands separators; balances rounded and often stale |
| Names | One column for the household, free text, for example `Smith, John & Jane` |
| Encoding | Not applicable (binary workbook, UTF-8 strings inside) |
| Shape | One row per account, a notes column, no formal keys |
| Role | Lowest priority. Used for context and to find accounts missing elsewhere |

These conventions describe the clean form. Mess (E3) layers variations on top, such as shifted headers, text dates, and extra blank rows.

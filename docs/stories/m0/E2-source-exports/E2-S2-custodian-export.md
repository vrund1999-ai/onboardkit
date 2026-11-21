# E2-S2: Custodian export

| | |
|---|---|
| **Epic** | [E2: Multi-source messy exports](../../../m0-foundation-epics.md#e2-multi-source-messy-exports) |
| **Size** | M |
| **Depends on** | E2-S1, E1-S3 |
| **Blocks** | E2-S5 |

## User story

As a contributor, I want a custodian-style account export, so that datasets include the authoritative record of accounts, balances, and registrations in the way a custodian really delivers it.

## Context

The custodian is the system of record for money data (see the roadmap decisions). Its file is flat, one row per account, shouted in upper case, with no concept of a household. Its conventions are the "formal and rigid" end of the mess spectrum, which gives the other two sources something to disagree with. M0 simulates a single custodian, `Meridian Custody Services`. A second is added in M2.

## Scope

**In scope**
- A `CustodianExporter` with a `SourceProfile` and projection from truth.
- One CSV file, with preamble and trailer lines typical of custodian files.

**Out of scope**
- Holdings, positions, and transactions.
- Any mess beyond the source's inherent style (E3).
- Partial coverage (E2-S5).

## Technical design

### File

`custodian_accounts.csv`: UTF-8 with BOM (`utf-8-sig`), `\r\n` line endings, comma delimiter, all text fields quoted.

Layout:

| Line | Content |
|---|---|
| 1 | `MERIDIAN CUSTODY SERVICES - ACCOUNT MASTER` |
| 2 | `Report date: 12/31/2025` (formatted from `as_of_date`) |
| 3 | Header row |
| 4..N | One row per account |
| N+1 | `Total records: <count>` |

### Columns

| Header | Concept | Formatter |
|---|---|---|
| `Acct #` | `account.number` | passthrough |
| `Account Title` | `account.registration` | upper |
| `Acct Type` | `account.type` | custodian code map (`IND`, `JNT`, `TIRA`, `ROTH`, `RIRA`, `529`) |
| `Status` | `account.status` | map (`OPEN`, `CLOSED`, `RESTRICTED`) |
| `Open Date` | `account.open_date` | `date` with `%m/%d/%Y` |
| `Market Value` | `account.balance` | `money` plain with thousands separators, two decimals |
| `Value As Of` | `account.balance_as_of` | `date` with `%Y%m%d` |
| `Owner 1` | `account.owner_names` (first owner) | `name_last_first`, upper |
| `Owner 2` | `account.owner_names` (second owner) | same, blank when none |
| `Mail Addr` | `person.address_line1` plus city, state, postal | single line, comma separated |
| `TIN Last4` | `person.tax_id_last4` | passthrough |

If two columns map to one concept (as with the owner pair), the profile marks which slice each takes via an option (`index: 0` or `index: 1`) so the answer key stays unambiguous.

### Projection

One `SourceRow` per `TruthAccount`. `refs` carries `account_id`, `household_id`, and the owner `person_ids`. Mailing address and tax id come from the first owner. A small share of truth accounts have status `CLOSED` or `RESTRICTED` (set in E1-S4 or applied here from a profile weight; decide in implementation and document).

## Files to create or change

- `src/onboardkit/datagen/sources/custodian.py`
- Update `concepts.yaml` only if a header needs a concept that does not exist (add it in E1-S3 first).
- `tests/datagen/sources/test_custodian.py`

## Acceptance criteria

- [ ] Output file has the three preamble/header lines and a trailer whose count equals the number of data rows.
- [ ] Every truth account appears exactly once before coverage is applied.
- [ ] The first bytes of the file are a UTF-8 BOM, and every line ends `\r\n`.
- [ ] Balances, dates, account types, and names appear in the formats in the table above.
- [ ] Every column's concept exists in the catalogue.
- [ ] Row locators from `write` point to the correct data lines (header line number accounted for).
- [ ] The README's `Acct #` header example is present.

## Test plan

- Snapshot test of the first five lines for the 15-household sample at a fixed seed.
- Unit tests for the type-code and status maps.
- Locator test: read the file, check the line at a returned locator contains the row's account number.

## Risks and notes

- Trailer and preamble lines must be ignorable by a CSV reader with `skiprows`; do not put commas in the title line in a way that creates misleading columns. Quote it.
- Keep names in upper case; case variants are an E3 concern.

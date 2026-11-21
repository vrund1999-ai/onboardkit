# Common data model

The single, clean structure every source is converted into. This page describes it in business terms: what each thing is, which facts it holds, and how things relate. How it is stored is a separate matter. Terms are defined in the [glossary](glossary.md).

All data is synthetic. The examples come from the fictional firm in [fictional-firm.md](fictional-firm.md).

## The model is not the concept catalogue

The [concept catalogue](source-systems.md) describes what each source column means, so answers can be scored. The common model is what the product keeps and what later steps (matching, review, reconciliation, reporting) work on. Every catalogue concept has a place in the model or is explicitly left out; that mapping is kept alongside the model definition and checked by a test.

## Entities at a glance

```
Firm
 +-- Source systems (custodian, CRM, book of business)
 +-- Households
 |     +-- Clients (people)
 +-- Accounts  <---- owned by ---- Clients (many to many)
 |     +-- Balances  (one per source and date)
 |     +-- Holdings  (one per security, source and date)
 +-- Securities
 +-- Source records (where a value came from)
```

| Entity | What it is | Facts it holds |
|---|---|---|
| **Firm** | The advisor firm being onboarded. Everything below belongs to exactly one firm. | Name |
| **Household** | The group of people the firm plans for together. | Name, advisor |
| **Client** | One person the firm serves. | First name, last name, suffix, date of birth, email, phone, address (street, city, state, postal code), last four digits of the tax id, role in the household, client since |
| **Account** | One account at the custodian. | Account number, type, registration title, status, open date, owners |
| **Balance** | What an account was worth on a date, as reported by one source. | Amount, as-of date, source |
| **Security** | Something that can be held, such as a stock or a fund. | Identifier, description, asset class |
| **Holding** | An amount of one security held in one account on a date, as reported by one source. | Quantity, value, as-of date, source |
| **Source record** | The original row a value came from. | Source, file, sheet, row, original text |

## Required and optional facts

Real exports are incomplete, so the model asks for very little and records the rest when it exists.

| Entity | Required | Everything else |
|---|---|---|
| Firm | Name | n/a |
| Household | Name | Advisor |
| Client | Last name | Optional |
| Account | Account number, type | Optional |
| Balance | Amount, as-of date, source | n/a |
| Security | Identifier | Optional |
| Holding | Quantity or value, as-of date, source | Optional |
| Source record | Source, file, row | Sheet (only for workbooks) |

A missing required fact is not hidden. The row is still loaded, and the gap is reported (see the intake report, epic E15).

## Relationships

- A **firm** has many households, accounts, securities and source systems. Nothing is shared between firms.
- A **household** has one or more **clients**. A client belongs to one household.
- An **account** has one or more **owners**, and a client can own several accounts. Joint accounts are the common case of many owners.
- An **account** has many **balances** and many **holdings**: one for each source that reports them and each date.
- A **holding** is of one **security**.
- Every stored value can point at a **source record**.

## Rules

1. **The original is kept.** A standardized value is stored next to the text it came from. The model speaks of a value and its original value, so a person can always check what was changed (see [lineage](glossary.md#lineage)).
2. **One fact, many reports.** An account's balance is recorded once per source, because sources disagree and a later milestone reconciles them. The model never overwrites one source's balance with another's.
3. **Source-specific notes stay notes.** Facts only one source has, such as the free-text notes in the book of business or the report date at the top of a custodian file, are kept as labelled notes on the source record. They are not columns of the model.
4. **The model has its own identifiers.** Each source's own key (a custodian account number, a CRM contact id) is kept as an [alias](glossary.md#alias) of the model's entity, so the same thing can be found by any source's name for it.
5. **Differently spelled records are not merged here.** Two rows that look like the same person become two clients until the matching step (M2) decides otherwise.

## Where source columns land

These tables show where the columns of the three simulated sources, and the planned positions file, go. `-` means the column is kept only as a note on the source record.

### Custodian account master (`custodian_accounts.csv`)

| Column | Lands in |
|---|---|
| `Acct #` | Account: account number |
| `Account Title` | Account: registration title |
| `Acct Type` | Account: type |
| `Status` | Account: status |
| `Open Date` | Account: open date |
| `Market Value`, `Value As Of` | Balance: amount, as-of date |
| `Owner 1`, `Owner 2` | Account: owners (names to be matched to clients) |
| `Mail Addr` | Client: address |
| `TIN Last4` | Client: tax id last four |
| Report date line | - (note) |

### CRM contacts and linked accounts (`crm_contacts.csv`, `crm_linked_accounts.csv`)

| Column | Lands in |
|---|---|
| `contact_id` | Client: alias |
| `first_name`, `last_name`, `suffix` | Client: name |
| `date_of_birth` | Client: date of birth |
| `email`, `phone` | Client: email, phone |
| `street`, `city`, `state`, `zip` | Client: address |
| `household_id`, `household_name` | Household: alias, name |
| `household_role` | Client: role in the household |
| `advisor` | Household: advisor |
| `client_since` | Client: client since |
| `account_number`, `account_type` (linked accounts) | Account: ownership link, account number, type |

### Book of business workbook (`book_of_business.xlsx`)

| Column | Lands in |
|---|---|
| `Household` | Household: name |
| `Advisor` | Household: advisor |
| `AcctNo` | Account: account number |
| `Type` | Account: type |
| `Balance` | Balance: amount (as-of date is the file's date) |
| `Notes` | - (note) |
| `Last Review` | - (note) |

### Custodian positions (planned, epic E9)

| Column | Lands in |
|---|---|
| `Acct #` | Holding: account |
| `Symbol`, `Security Description`, `Asset Class` | Security: identifier, description, asset class |
| `Quantity`, `Market Value` | Holding: quantity, value |
| `Price`, `Price Date` | Holding: as-of date (price is a note) |

## Later enhancements

Not in the first version of the model, by decision: prices over time, cost basis and tax lots, transactions, income, and richer holdings detail.

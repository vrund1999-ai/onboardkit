# The fictional firm

onboardkit is developed and demonstrated against one fictional advisory firm, **Lantern Ridge Wealth Partners**. This page describes who they are, who their clients are, and what their data looks like. Everything here is invented; no real client, firm, or person is represented.

The numbers on this page are the single source of truth for the data generator. The [parameter table](#8-parameters-for-the-generator) at the end is transcribed into configuration by story [E1-S4](stories/m0/E1-fictional-firm/E1-S4-truth-model-and-population.md). If a number changes, change it here and in the configuration together.

Related: [roadmap](../ROADMAP.md), [M0 epics](epics/m0-foundation-epics.md).

## 1. Identity

| Role | Fictional name | Notes |
|---|---|---|
| The advisory firm | Lantern Ridge Wealth Partners | Independent registered advisory firm, the customer in every scenario |
| The custodian | Meridian Custody Services | Holds client assets and produces the account master file |
| The CRM | Cedarline CRM | Where the firm keeps client contacts and households |
| The spreadsheet | Book of Business | Operations team's hand-maintained Excel workbook |

**Name check (2026-11-21).** Web searches for each name found no firm or product with that exact name.

- "Lantern Ridge Wealth Partners": no match. The closest results were differently named firms such as Lantern Wealth Advisors, LLC. The names are distinct, but avoid using this name outside the project.
- "Meridian Custody Services": no match.
- "ClientHub" was the first choice for the CRM but is a real product (practice management software for accounting firms), so it was **replaced** by "Cedarline CRM", which has no match.

Re-run the check if any name changes.

## 2. Staffing

Four advisors. Each household has exactly one advisor, which becomes the `advisor` attribute in the CRM and the book of business.

| Advisor | Share of households |
|---|---|
| Marcus Delgado | 40% |
| Elena Whitfield | 25% |
| Sam Okafor | 20% |
| Hannah Brecker | 15% |

One advisor carries a much larger book than the others, as is common in small firms. This also gives the book of business a lopsided look (one long sheet and three shorter ones).

## 3. Clients and household archetypes

A **household** is the unit the firm serves: one or more people who share financial planning. Each household follows one of five archetypes.

| Archetype | Members | Share of households |
|---|---|---|
| Single adult | 1 adult | 30% |
| Couple | 2 adults | 45% |
| Couple with dependents | 2 adults, 1 to 3 children | 15% |
| Single parent | 1 adult, 1 to 2 children | 5% |
| Widowed or retired single | 1 adult, age 65 or older | 5% |

Rules for the people in a household:

- Adults in a couple are within eight years of age of each other.
- A parent is at least 18 years older than each of their children, and parents in households with children are born in 1965 or later.
- Most couples share a surname; about 15% of couples use different surnames.
- A household's display name comes from its primary member (the first adult), for example "Smith Household".
- The widowed or retired archetype exists so that older clients and larger balances are represented.

**Role names** used for people in a household: `primary`, `spouse`, `dependent`.

### Firm sizes

The same firm exists in two sizes.

| Size | Households | Used for |
|---|---|---|
| `sample` | 15 | Fast tests, demonstrations, and reviewing by eye |
| `default` | 300 | A realistic firm that also exposes scale problems |

The 15 households of the sample are the first 15 households of the default firm.

## 4. Account types and ownership rules

Six account types are in scope for M0.

| Account type | Who can own it | Rule |
|---|---|---|
| Individual brokerage | One adult | Taxable account in one person's name |
| Joint brokerage | Two adults | Only in households with two adults; both are owners |
| Traditional IRA | One adult | Always single-owner |
| Roth IRA | One adult | Always single-owner |
| Rollover IRA | One adult | Always single-owner |
| 529 education account | One adult owner, one child beneficiary | Only in households with at least one child; the beneficiary is a dependent in the same household |

Further rules:

- Every owner belongs to the account's household.
- A person holds at most one traditional IRA, one Roth IRA, and one rollover IRA.
- Each account has a status of `open` for almost all accounts. A small share (about 3%) are `closed` and a small share (about 1%) are `restricted`. Closed accounts appear in the custodian file and on the book of business's archive sheet.
- Account numbers are eight characters: the fictional prefix `MC` followed by six digits. Numbers are unique across the firm.
- The **registration title** (the legal name on the account) is built from the owners and type, for example `JOHN A SMITH INDIVIDUAL`, `JOHN A SMITH & JANE B SMITH JTWROS` for a joint account, `JANE B SMITH ROTH IRA` for a Roth IRA, or `JANE B SMITH FBO EMMA SMITH 529` for a 529.

### Account mix

When a household needs an account, the type is drawn from the types it is eligible for, using these weights.

| Account type | Weight |
|---|---|
| Individual brokerage | 25 |
| Joint brokerage | 20 |
| Traditional IRA | 15 |
| Roth IRA | 15 |
| Rollover IRA | 15 |
| 529 education account | 10 |

Ineligible types are dropped and the rest are re-weighted. For example, a single adult household can never receive a joint brokerage account or a 529.

## 5. Accounts per household

| Accounts in the household | Share of households |
|---|---|
| 1 | 20% |
| 2 | 35% |
| 3 | 30% |
| 4 to 6 (evenly spread) | 15% |

On average this is about 2.5 accounts per household: roughly 38 accounts in the `sample` and 765 in the `default` dataset.

## 6. Balances and dates

### Balances

Balances are in US dollars and always positive.

- The distribution is log-normal: a few large accounts and many modest ones.
- The median account is about **$150,000**, and the 90th percentile is about **$900,000**.
- 529 accounts are smaller: their typical value is a quarter of the others (a median of about $37,500).
- Balances are never zero or negative, and are clamped between $2,500 and $10,000,000.
- Balances are rounded to the cent.

### Dates

| Item | Rule |
|---|---|
| As-of date | Fixed at **2025-12-31** for every dataset unless changed in configuration. Nothing depends on today's date. |
| Client since | Spread over the 15 years before the as-of date, and never before the primary's 21st birthday |
| Adult date of birth | Between 1945 and 1995 (retired and widowed archetype: 1960 or earlier) |
| Child date of birth | Between 2005 and 2022 |
| Account open date | On or after the household's client-since date and every owner's 18th birthday (and for a 529, the beneficiary's birth), and on or before the as-of date |

## 7. The three source systems

The same fictional firm is seen through three sources. Each holds different facts, and none holds everything. Field-level detail comes in story [E1-S3](stories/m0/E1-fictional-firm/E1-S3-source-system-catalogue.md).

**Custodian (Meridian Custody Services).** The system of record for money. It produces a flat account master file: one row per account, with the account number, registration title, type, status, open date, market value, valuation date, owner names, and a mailing address. It has no idea what a household is, holds no email addresses, and prints names in upper case.

**CRM (Cedarline CRM).** The system of record for people. It holds each person's name, date of birth, contact details, household and role, advisor, and client-since date, plus a loose list of the account numbers linked to each person. It carries no balances. Its exports are tidy and machine-friendly.

**Book of Business (Excel).** A workbook the operations team keeps by hand: one sheet per advisor and an archive sheet. It has household names, account numbers, short account types, rounded and often stale balances, notes, and a last-review date. It is the lowest-priority source and the messiest in layout.

The sources deliberately overlap but are incomplete, for example some accounts are missing from the CRM or the spreadsheet. How much is controlled in later stories.

## 8. Parameters for the generator

This block is what [E1-S4](stories/m0/E1-fictional-firm/E1-S4-truth-model-and-population.md) transcribes into `firm_profile.yaml`. It repeats the numbers above in machine-readable form.

```yaml
firm:
  name: Lantern Ridge Wealth Partners
  custodian: Meridian Custody Services
  crm: Cedarline CRM
  spreadsheet: Book of Business
  as_of_date: 2025-12-31
sizes:
  sample: 15
  default: 300
advisors:
  - { name: Marcus Delgado, share: 0.40 }
  - { name: Elena Whitfield, share: 0.25 }
  - { name: Sam Okafor, share: 0.20 }
  - { name: Hannah Brecker, share: 0.15 }
archetypes:
  single_adult:      { share: 0.30, adults: 1, children: [0, 0] }
  couple:            { share: 0.45, adults: 2, children: [0, 0] }
  couple_dependents: { share: 0.15, adults: 2, children: [1, 3] }
  single_parent:     { share: 0.05, adults: 1, children: [1, 2] }
  retired_single:    { share: 0.05, adults: 1, children: [0, 0], min_age: 65 }
people:
  couple_age_gap_max_years: 8
  parent_child_gap_min_years: 18
  couples_with_different_surnames: 0.15
  dependents_parent_birth_year_min: 1965
account_counts:
  - { accounts: [1, 1], share: 0.20 }
  - { accounts: [2, 2], share: 0.35 }
  - { accounts: [3, 3], share: 0.30 }
  - { accounts: [4, 6], share: 0.15 }
account_types:
  individual:      { weight: 25, owners: 1 }
  joint:           { weight: 20, owners: 2 }
  traditional_ira: { weight: 15, owners: 1 }
  roth_ira:        { weight: 15, owners: 1 }
  rollover_ira:    { weight: 15, owners: 1 }
  education_529:   { weight: 10, owners: 1, needs_child_beneficiary: true }
account_status:
  open: 0.96
  closed: 0.03
  restricted: 0.01
account_number:
  prefix: MC
  digits: 6
balances:
  distribution: lognormal
  median: 150000
  p90: 900000
  min: 2500
  max: 10000000
  type_scale: { education_529: 0.25 }
dates:
  client_since_years_back: 15
  primary_min_age_at_client_since: 21
  adult_birth_years: [1945, 1995]
  retired_birth_year_max: 1960
  child_birth_years: [2005, 2022]
```

Checks on this table: advisor shares sum to 1.00, archetype shares sum to 1.00, account-count shares sum to 1.00, account status shares sum to 1.00, and account type weights sum to 100.

## 9. Not in scope for M0

These are real-world cases that the fictional firm leaves out for now. They are deferred until the basics work and M1 has defined the common data model, and will come back as an optional mess type.

- **Trusts.** They introduce trustees, beneficiaries, and different registrations.
- **Business accounts.** They change who an "owner" is and what a household means.
- **Deceased clients.** They create inherited accounts and status changes that depend on more history.
- **Other account types** such as annuities, custodial (UTMA) accounts, and holdings or transactions within accounts.
- **Multiple custodians.** M0 has one; a second, differently shaped one arrives in M2.

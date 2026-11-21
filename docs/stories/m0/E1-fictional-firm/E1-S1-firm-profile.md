# E1-S1: Fictional firm profile

| | |
|---|---|
| **Epic** | [E1: Fictional firm and shared vocabulary](../../../epics/m0-foundation-epics.md#e1-fictional-firm-and-shared-vocabulary) |
| **Size** | S |
| **Depends on** | none |
| **Blocks** | E1-S3, E1-S4 |

## User story

As a contributor, I want a one-page description of the fictional advisory firm, so that everyone generates, tests, and demonstrates against the same believable picture.

## Context

The generator needs concrete numbers (how many households, what mix of household shapes, what account types). Those numbers should be decided once, in prose a non-developer can review, and then transcribed into configuration by E1-S4. This story is documentation only and has no code dependency, so it can start on day one.

## Scope

**In scope**
- A new document `docs/fictional-firm.md`.
- Firm identity, staffing, client mix, household archetypes, account types, and the three source systems at a high level.
- A machine-readable parameter table that E1-S4 transcribes into configuration.

**Out of scope**
- Field-level detail for each source (E1-S3).
- Edge cases deferred from M0: trusts, business accounts, deceased clients.

## Technical design

The document contains these sections, in order:

1. **Identity.** Fictional firm name (`Lantern Ridge Wealth Partners`), a fictional custodian (`Meridian Custody Services`), a fictional CRM (`ClientHub`), and the internal spreadsheet (`Book of Business`). Names must not match any real firm; do a quick web check and record the date.
2. **Staffing.** Four advisors (fictional names), used as the `advisor` attribute on households. Roughly even spread with one advisor carrying about 40 percent of households.
3. **Household archetypes.** Each archetype has a target share of households:

   | Archetype | Members | Share |
   |---|---|---|
   | Single adult | 1 adult | 30% |
   | Couple | 2 adults | 45% |
   | Couple with dependents | 2 adults, 1 to 3 children | 15% |
   | Single parent | 1 adult, 1 to 2 children | 5% |
   | Widowed or retired single | 1 adult, age 65+ | 5% |

4. **Account types in M0.** Individual brokerage, joint brokerage, traditional IRA, Roth IRA, rollover IRA, and 529 education account. Rules: IRAs are always single-owner; joint accounts need two adults in the household; 529s are owned by an adult and name a child as beneficiary.
5. **Accounts per household.** Distribution: 1 account (20%), 2 (35%), 3 (30%), 4 to 6 (15%).
6. **Balances.** Log-normal-style distribution described in words with target ranges: median account about 150,000, 90th percentile about 900,000, no negative or zero balances.
7. **Dates.** `as_of_date` fixed at `2025-12-31`; client-since dates spread over the previous 15 years; adult dates of birth between 1945 and 1995; child dates of birth between 2005 and 2022.
8. **Size presets.** `sample` is 15 households, `default` is 300 households.
9. **Source systems overview.** One paragraph each for custodian, CRM, and book of business, linking to E1-S3 for detail.
10. **Explicit exclusions.** List the deferred edge cases and why.

## Files to create or change

- Create `docs/fictional-firm.md`.
- Linking it from the top-level README is handled in E7-S4.

## Acceptance criteria

- [ ] `docs/fictional-firm.md` exists and covers all ten sections.
- [ ] Archetype shares sum to 100 percent and account-count shares sum to 100 percent.
- [ ] Every account type has an ownership rule stated.
- [ ] Firm, custodian, and CRM names are fictional and the check is recorded.
- [ ] A reader unfamiliar with the project can say what the firm is and what its data looks like after one read.

## Test plan

Documentation review only. A second person reads the page and answers: how many households are there, what shapes are they, and what accounts can a couple own? Record any question they could not answer and fix the page.

## Risks and notes

- Numbers here become configuration in E1-S4. If the numbers change later, change this page and the configuration together.
- Keep the page short enough to read in a few minutes.

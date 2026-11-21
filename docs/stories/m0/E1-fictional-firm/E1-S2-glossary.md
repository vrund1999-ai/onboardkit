# E1-S2: Business glossary

| | |
|---|---|
| **Epic** | [E1: Fictional firm and shared vocabulary](../../../epics/m0-foundation-epics.md#e1-fictional-firm-and-shared-vocabulary) |
| **Size** | S |
| **Depends on** | none |
| **Blocks** | E1-S3 |

## User story

As a contributor, I want one glossary of business and project terms, so that documents, code, and conversations use words consistently.

## Context

The README and roadmap already use terms such as household, custodian, book of business, reconciliation, and ground truth. Without a shared definition, the same word will drift in meaning across code and docs. Terms in the glossary also seed naming in code (class and column names), so spelling and casing guidance matters.

## Scope

**In scope**
- A new document `docs/glossary.md`.
- Terms used in the README, `ROADMAP.md`, and the M0 epics and stories.

**Out of scope**
- Defining the M1 common data model. The glossary defines meanings, not schemas.

## Technical design

Format: alphabetical list, one entry per term, each with:

- **Definition** in one or two sentences, in plain language.
- **Also known as**, listing spellings and synonyms seen in real exports (for example `Acct #`, `account_number`, `AcctNo`).
- **Not to be confused with**, where a nearby term differs.
- **Code name**, the identifier used in code when one exists (for example `household_id`).

Minimum term list:

| Group | Terms |
|---|---|
| Firm and people | advisor, client, household, household role (primary, spouse, dependent), beneficiary |
| Accounts | account, account number, account type, registration (title), custodian, market value, balance, as-of date, account status |
| Sources | source system, custodian export, CRM, book of business, export, sheet |
| Data quality | mess, mess type, intensity, naming variant, duplicate household, split household, missing household, discrepancy, tolerance |
| Onboarding | mapping, entity match, merge, reconciliation, exception |
| Project | synthetic data, truth (ground truth), answer key, preset, seed, dataset, manifest, lineage, provenance |

Cross-link rule: the first mention of a glossary term in other docs links to its entry. That is a convention for new docs, not a retrofit of existing ones.

## Files to create or change

- Create `docs/glossary.md`.

## Acceptance criteria

- [x] Every term in the minimum list has an entry with a definition.
- [x] Entries for `account number`, `client`, and `balance` list at least three real-world spellings or synonyms.
- [x] `truth` and `answer key` are defined precisely and distinguished from each other.
- [x] Every term used in the README, `ROADMAP.md`, and the M0 epics file either appears in the glossary or is plain English.
- [x] Entries are alphabetical and each has a stable anchor so other documents can link to it.

## Test plan

Documentation review. As a check, search the README, roadmap, and epics for domain words and confirm each appears in the glossary.

## Risks and notes

- Keep definitions business-facing. Resist describing implementation here.
- Add terms as later milestones introduce them.

## Notes

- Added terms beyond the minimum list that the README, roadmap, and epics use: archetype, audit trail, common data model, concept, confidence, coverage, normalization, severity, source of truth.

# E8-S1: Model definition and glossary terms

| | |
|---|---|
| **Epic** | [E8: Common data model](../../../epics/m1-ingestion-epics.md#e8-common-data-model) |
| **Size** | M |
| **Depends on** | none |
| **Blocks** | E8-S2, E8-S4 |

## User story

As a newcomer to the project, I want one written definition of clients, households, accounts, holdings, and balances, so that I know what every source is being converted into before I read any code.

## Context

M0 produced a *concept catalogue* (`concepts.yaml`): a vocabulary for scoring, describing what each source column means. The common model is different: it is the target representation the product stores and that later milestones match, review, and report on. The glossary already warns that the two are not the same thing. This story defines the model in business terms first. The table layout comes later (E8-S4).

## Scope

**In scope**
- `docs/data-model.md`: each entity, in plain language, with its facts, which are required and which optional, and how entities relate.
- Glossary entries for the model's terms.
- A rule separating facts the model keeps from source-specific notes.

**Out of scope**
- The mapping of every catalogue concept (E8-S2).
- Table layout, types, and migrations (E8-S4).
- Deciding two records are the same person (M2).

## Technical design

### Entities

| Entity | What it is | Key facts |
|---|---|---|
| Firm | The advisor firm being onboarded; the owner of everything below | name |
| Household | A group of people the firm treats as one client relationship | name, advisor |
| Client | One person | first name, last name, suffix, date of birth, email, phone, address, tax id last four, role in the household, client since |
| Account | One investment account | account number, type, registration, status, open date, owners |
| Balance | An account's market value on a date, as reported by one source | amount, as-of date, source |
| Security | Something that can be held | identifier, description, asset class |
| Holding | A quantity of one security in one account on a date | quantity, value, as-of date, source |
| Source record | Where a fact came from (the detail is lineage, E13) | source, file, sheet, row |

### Rules to write down

- **Required versus optional.** A client needs at least a last name; an account needs an account number and a type. Everything else is optional because sources are incomplete.
- **Values keep the original.** A standardized value is stored next to the original text (lineage, E13), so the definition says "value" and "original value" separately.
- **One fact, many reports.** A balance belongs to the account but is recorded per source, because sources disagree and M4 reconciles them. The model never overwrites one source's balance with another's.
- **Source-specific notes.** Facts that no other source has (the book of business free-text notes, the custodian's report date) are kept as labelled notes on the source record, not as columns of the model.
- **Identifiers.** The model has its own identifiers; each source's own key is kept as an alias.

### Glossary terms to add

Common model (already present: check and extend), client, household, account, balance, security, holding, source record, alias, standardized value.

## Files to create or change

- `docs/data-model.md`
- `docs/glossary.md`
- `docs/architecture.md` (one sentence in the extension points linking to the model)

## Acceptance criteria

- [x] `docs/data-model.md` defines each entity in the table above with required and optional facts and its relationships.
- [x] The five rules above are written down in plain language.
- [x] A reader can say where each column of the demo dataset's three sources belongs (checked in E8-S2).
- [x] Every new term is in the glossary, and the link and anchor guards pass.
- [x] The document describes the model in business terms; no table or column types appear in it.

## Test plan

- The existing link and anchor guards cover the new document.
- Read-through: walk the custodian headers through the entity table by hand and note any column with no home (feeds E8-S2).

## Risks and notes

- Resist modelling every possible source. The model covers the three simulated sources plus holdings; M2 will stretch it for a second custodian.
- Joint accounts have several owners and clients can own several accounts: write the relationship as many-to-many.

## Notes

- The model page also carries a "where source columns land" section for the three sources and the planned positions file. E8-S2 turns the catalogue half of that into a generated, tested mapping.
- Glossary additions: alias, firm, holding, security, source record, standardized value. "Common data model" now points at the page. Client was already defined in M0 and was kept.
- The check that every column of the demo dataset has a home was run for real against a generated `typical-default-s42` dataset: every header of the custodian, CRM and workbook files appears on the page (0 missing).

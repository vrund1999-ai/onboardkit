# M0: Foundation and realistic test data — Epics

This document breaks the M0 milestone from the [roadmap](../../ROADMAP.md) into epics. Like the roadmap, it describes business capabilities and outcomes, not implementation. Detailed stories and tasks will be written when each epic is picked up.

All data is synthetic. No real client or firm data is used anywhere.

## Milestone goal

Have a safe, repeatable way to develop and demonstrate the product without real client data.

## Epic overview

| # | Epic | Why it matters | Depends on |
|---|---|---|---|
| E1 | Fictional firm and shared vocabulary | Everything else needs an agreed picture of what the fictional firm looks like | none |
| E2 | Multi-source messy exports | The core test material for every later milestone | E1 |
| E3 | Controllable mess | Lets us test easy and hard cases deliberately | E2 |
| E4 | Reproducible datasets | Makes results comparable over time | E2 |
| E5 | Ground truth | Makes quality measurable rather than anecdotal | E1, E2 |
| E6 | Automated quality gate | Keeps the project healthy from day one | none |
| E7 | Contributor experience | Lets someone else pick the project up | E2, E6 |

E1 and E6 can start immediately and in parallel. E2 is the critical path for the rest.

---

## E1: Fictional firm and shared vocabulary

**Goal:** Define a believable fictional advisory firm and the plain-language vocabulary used across the project.

**Capabilities**
- A described fictional firm: a mix of individual and joint clients, household structures, and account types. Trusts, business accounts, and deceased clients are deliberately left out of M0.
- Two firm sizes: a small sample of roughly 15 households and a realistic default of roughly 300.
- A glossary of the business terms the project uses (client, household, account, custodian, book of business, and so on), so documents and later features speak the same language.
- A definition of which facts each source system holds and which it does not, mirroring how real firms are split across systems.

**Done when**
- A newcomer can read one page and understand who the fictional firm is and what data each source holds.
- Terms used in the README, roadmap, and these epics are defined in one place.

**Out of scope:** the full common data model, which belongs to M1.

---

## E2: Multi-source messy exports

**Goal:** Produce realistic exports from the three sources, each in a different shape, covering the same underlying firm.

**Capabilities**
- A custodian-style export focused on accounts, balances, and registrations. M0 simulates a single custodian format; a second is added in M2.
- A CRM-style export focused on people, contact details, and household relationships.
- A hand-maintained "book of business" spreadsheet with its own layout and habits.
- Each source uses its own column naming, formats, and structure, as described in the README.
- Both CSV and Excel files are produced, including spreadsheet habits such as title rows, multiple sheets, and blank rows.
- The sources overlap in ways that matter: the same client and account appear in more than one source, but not completely.

**Done when**
- Three exports exist that clearly describe the same firm but cannot be joined without effort.
- The README's examples of mess (differing column names, name spellings, date formats, mismatched balances) can each be found in the output.
- A reviewer can open the files and agree they look like something a real firm would send.

---

## E3: Controllable mess

**Goal:** Let us choose which kinds of mess appear and how much, so we can test easy and hard cases on purpose.

**Capabilities**
- A catalogue of mess types: naming variants, nicknames and suffixes, duplicate households, split households, missing households, mixed date formats, inconsistent identifiers, and balance mismatches.
- Each mess type can be turned on or off and dialed from light to heavy.
- A small set of named presets, for example "clean", "typical", and "nightmare", so common scenarios are one choice away.
- Mess is applied deliberately and recorded, never random noise with no explanation.

**Done when**
- The same fictional firm can be generated as a clean dataset and as a heavily messy one.
- Turning a single mess type on affects only that kind of problem.
- Every mess type in the catalogue has at least one visible example in a generated dataset.

---

## E4: Reproducible datasets

**Goal:** Make any dataset recreatable on demand so comparisons over time are fair.

**Capabilities**
- A dataset is fully described by its settings, so the same settings always yield identical data.
- Datasets are labelled and versioned so it is clear which one a result came from.
- Generated files are kept out of version control, in line with the README, while the settings that produce them are tracked.
- A small, fixed sample dataset (roughly 15 households) is available for quick demonstrations and tests, alongside a realistic default (roughly 300 households).

**Done when**
- Generating a dataset twice from the same settings gives identical files.
- Changing the settings in a documented way gives a predictably different dataset.
- Anyone can regenerate the project's standard demo dataset in one step.

---

## E5: Ground truth

**Goal:** For every dataset, know exactly what the correct answer is, so later quality can be scored.

**Capabilities**
- A hidden record of the true clients, households, and accounts behind each dataset.
- A record of which source rows refer to the same real client or account, which is the answer key for later entity matching.
- A record of the true meaning of each source column, which is the answer key for later column mapping.
- A record of every deliberate discrepancy that was introduced, which is the answer key for later reconciliation.
- Ground truth is kept separate from the exports, so it cannot leak into the material the product works from.

**Done when**
- For any messy dataset, we can state exactly how many true clients, households, accounts, and discrepancies it contains.
- The answer keys for mapping, matching, and reconciliation all exist and agree with each other.
- Ground truth is clearly marked as internal and not part of what a firm would send.

---

## E6: Automated quality gate

**Goal:** Every proposed change is checked automatically before it is accepted.

**Capabilities**
- Automated checks run on every proposed change and report a clear pass or fail.
- The checks cover code style, correctness tests, and that data generation still behaves as documented.
- A failing check blocks acceptance of a change.
- Basic protections against accidentally committing generated data or sensitive material.

**Done when**
- A deliberately broken change is caught and blocked.
- A good change passes without manual steps.
- Results are visible to anyone reviewing a change.

---

## E7: Contributor experience

**Goal:** A newcomer can set up and run the project using the documentation alone.

**Capabilities**
- Setup instructions that work from a clean machine.
- A short guide to generating the standard demo dataset and viewing the results.
- A guide to how the project is organised and how to propose a change.
- The README and roadmap updated so they reflect what now exists, with M0 clearly marked as delivered.

**Done when**
- Someone who has not seen the project can follow the docs, generate a dataset, and see the checks pass, without asking for help.
- The README's status note no longer describes the project as scaffolding only.

---

## Suggested order

1. **Start together:** E1 (fictional firm) and E6 (quality gate).
2. **Then:** E2 (messy exports), the main piece of work.
3. **Build on E2:** E3 (controllable mess), E4 (reproducibility), and E5 (ground truth) can progress in parallel.
4. **Finish with:** E7 (contributor experience), once there is something real to document.

## Milestone exit criteria

M0 is complete when:

- A standard demo dataset can be regenerated in one step and looks like a real firm's messy exports.
- The mess can be turned up or down, and each kind of mess is visible when enabled.
- Ground truth exists for every dataset and covers mapping, matching, and reconciliation.
- Automated checks guard every change.
- A newcomer can get started from the docs alone.

## Decisions

These were open questions in the first draft and are now resolved.

- **Demo firm size:** two sizes. A small fixed sample of roughly 15 households, small enough to review by eye and used for tests and demonstrations. A realistic default of roughly 300 households, which feels like a real firm and exposes scale problems. Size is a setting of the dataset.
- **Edge cases:** M0 covers the core cases only: individual clients, joint accounts, and households. Trusts, business accounts, and deceased clients are deferred and will arrive later as an optional mess type, once the basics work and M1 has defined the common data model.
- **Custodians:** one custodian format in M0. A second, differently shaped custodian is added in M2, when testing reuse of learned mappings requires it.

# Roadmap

This roadmap lays out the work for onboardkit in terms of business capabilities: what an advisor firm, an onboarding specialist, or a reviewer will be able to do once each stage is delivered. It deliberately avoids implementation detail. See the [README](README.md) for the problem statement and design principles.

All data used throughout is synthetic.

## How to read this

- **Capability**: something a user can do or a guarantee the system provides.
- **Outcome**: how we know the capability is delivered.
- Milestones build on each other, but each one should leave the project in a usable, demonstrable state.

## Guiding outcomes

By the end of the roadmap, an onboarding specialist should be able to take a new firm's raw exports and produce a trusted, reconciled, client-ready view of its book of business, with every decision traceable and a person confirming anything uncertain.

---

## M0: Foundation and realistic test data

**Goal:** Have a safe, repeatable way to develop and demonstrate the product without real client data.

| Capability | Outcome |
|---|---|
| Generate realistic, messy multi-source data for a fictional firm | Custodian, CRM, and book-of-business exports exist, each in a different shape, with deliberate inconsistencies |
| Control the kinds and amount of mess | Naming variants, duplicate and split households, mixed date formats, and balance mismatches can be dialed up or down |
| Reproduce a dataset on demand | The same settings always yield the same data, so results can be compared over time |
| Know the "right answer" for each dataset | A hidden ground truth records the true clients, households, and accounts, so later quality can be measured |
| Automated quality checks on every change | Changes are validated automatically before they are accepted |
| Clear contributor guidance | A newcomer can set up and run the project from the docs alone |

## M1: Ingestion and a single clean data model

**Goal:** Bring every source into one consistent representation without losing where each value came from.

| Capability | Outcome |
|---|---|
| Accept CSV and Excel files from multiple sources | A user can submit a firm's exports and see them loaded |
| Handle real-world file quirks | Odd headers, extra title rows, blank rows, encodings, and multiple sheets do not break loading |
| Define the common model for clients, households, accounts, holdings, and balances | One agreed vocabulary exists regardless of source |
| Standardize formats | Dates, currency amounts, identifiers, names, and addresses are expressed uniformly |
| Preserve lineage | Every cleaned value can be traced back to its original file, sheet, and row |
| Keep each firm's data separate | One firm's onboarding never mixes with another's |
| Report on data quality at intake | A user sees what was loaded, what was skipped, and why |

## M2: AI-assisted mapping and entity matching

**Goal:** Cut the manual effort of figuring out what each column means and which records are the same entity.

| Capability | Outcome |
|---|---|
| Propose a mapping from each source column to the common model | Every column gets a suggested meaning with a confidence level and a short rationale |
| Propose likely matches between records | Variants of the same person, household, or account are grouped, each with a confidence level |
| Separate confident from uncertain suggestions | High-confidence items are applied; low-confidence items are routed to a person |
| Never silently merge uncertain records | Nothing below the confidence threshold changes data without human approval |
| Reuse what has been learned | A mapping confirmed for one firm or source is offered again the next time it appears |
| Keep numeric work out of the model | Balances, joins, and comparisons are computed by deterministic logic, with the model limited to interpretation and suggestion |
| Measure suggestion quality | Accuracy of mappings and matches is scored against the known ground truth |
| Degrade gracefully | If the AI service is unavailable, the user can still map and match manually |

## M3: Human review and audit trail

**Goal:** Give a person efficient control over every uncertain decision, and keep a permanent record.

| Capability | Outcome |
|---|---|
| Review queue of pending decisions | A reviewer sees uncertain mappings and matches ordered by importance |
| Accept, correct, or reject a suggestion | A reviewer can confirm, change, or split a proposed match or mapping |
| See the evidence behind a suggestion | Side-by-side source records and the reason for the suggestion are visible |
| Resolve many similar items at once | Repeated patterns can be handled in bulk with a single decision |
| Record every decision | Who decided what, when, and why is stored for every mapping, merge, split, and override |
| Undo and revisit decisions | A past decision can be reversed, with downstream results updated |
| Track review progress | A user can see how much is resolved, what remains, and what is blocking completion |
| Trace any output back to source | From any reported figure, a user can reach the original source rows and the decisions that shaped it |

## M4: Reconciliation and exceptions

**Goal:** Surface where the sources disagree so problems are found before the client does.

| Capability | Outcome |
|---|---|
| Detect missing records across systems | For example, an account at the custodian that is absent from the CRM |
| Detect value disagreements | Balances, ownership, registration, and status that differ between systems are flagged |
| Apply tolerances sensibly | Trivial differences such as rounding or timing are separated from material ones |
| Classify and prioritize exceptions | Each exception has a type, severity, and the records involved |
| Manage exception resolution | An exception can be assigned, explained, accepted, or marked fixed, with history kept |
| Define which source wins | Per-firm rules state which system is trusted for each kind of data |
| Summarize reconciliation health | A firm-level view shows how well the sources agree and how that is trending |
| Re-run after corrections | Fixing data or decisions updates the exception list without starting over |

## M5: Client-ready reporting

**Goal:** Deliver output an advisor can open, understand, and act on immediately.

| Capability | Outcome |
|---|---|
| Household summary workbook | Each household shows its members, accounts, and balances in a clear, consistent layout |
| Exceptions view | Open discrepancies are listed with severity and context |
| "What changed" view | Differences between the original exports and the cleaned result are explained, including merges and corrections |
| Professional presentation | Formatting, naming, and layout are polished enough to hand to a client without rework |
| Firm-specific branding and labels | Terminology and presentation can be adjusted per firm |
| Reproducible reports | The same inputs and decisions always produce the same report |
| Clear status of the data | A report states whether items are still pending review, so it is never mistaken for final |

## M6: Operating at scale and sharing the story

**Goal:** Make the toolkit dependable across many firms and communicate the approach clearly.

| Capability | Outcome |
|---|---|
| Onboard a new firm with configuration, not new code | Per-firm differences are captured as settings and learned mappings |
| Run end to end with minimal setup | A full onboarding, from files to report, can be demonstrated from a clean environment |
| Protect sensitive data | Access is controlled, and secrets and data are handled safely |
| Monitor and diagnose runs | A user can see what happened during a run and why something failed |
| Handle larger and repeated loads | Larger files and periodic refreshes complete reliably |
| Deployment write-up | Discovery notes, tradeoffs, a debugging story, and what would move into a shared platform are documented |

---

## Cross-cutting concerns

These apply to every milestone rather than being a stage of their own.

- **Human in the loop:** the system suggests, a person decides.
- **Auditability:** every change is attributable and reversible.
- **Determinism:** the same inputs and decisions give the same results.
- **Privacy:** only synthetic data is used in this repository.
- **Quality measurement:** each stage is evaluated against the known ground truth where possible.
- **Documentation:** each capability ships with user-facing explanation.

## Out of scope for now

- Live connections to custodians or CRMs (files only).
- Writing corrected data back to source systems.
- Real client or firm data.
- Billing, performance reporting, and portfolio analytics.

## Open questions

- What confidence threshold separates auto-apply from review, and should it be configurable per firm?
- Which source is authoritative for each data type by default?
- How should conflicting human decisions from different reviewers be handled?
- What is the minimum report content an advisor needs for a first conversation with a client?

# Capability and milestone progress

Status of every capability in the [roadmap](../../ROADMAP.md), rolled up into milestones. A capability's status is derived from the epics that deliver it. See [how tracking works](README.md).

**Last updated:** 2026-11-21

## Milestones

| Milestone | Title | Capabilities done | Status | Breakdown |
|---|---|---|---|---|
| M0 | Foundation and realistic test data | 1 / 6 | In progress | Epics and stories defined |
| M1 | Ingestion and a single clean data model | 0 / 7 | Not started | Not broken down yet |
| M2 | AI-assisted mapping and entity matching | 0 / 8 | Not started | Not broken down yet |
| M3 | Human review and audit trail | 0 / 9 | Not started | Not broken down yet |
| M4 | Reconciliation and exceptions | 0 / 8 | Not started | Not broken down yet |
| M5 | Client-ready reporting | 0 / 8 | Not started | Not broken down yet |
| M6 | Operating at scale and sharing the story | 0 / 6 | Not started | Not broken down yet |

## M0: Foundation and realistic test data

**Goal:** Have a safe, repeatable way to develop and demonstrate the product without real client data.

| Capability | Delivered by | Status | Notes |
|---|---|---|---|
| Generate realistic, messy multi-source data for a fictional firm | [E1](../epics/m0-foundation-epics.md#e1-fictional-firm-and-shared-vocabulary), [E2](../epics/m0-foundation-epics.md#e2-multi-source-messy-exports) | In progress |  |
| Control the kinds and amount of mess | [E3](../epics/m0-foundation-epics.md#e3-controllable-mess) | Done | E3 done |
| Reproduce a dataset on demand | [E4](../epics/m0-foundation-epics.md#e4-reproducible-datasets) | In progress | E4-S1 to E4-S3 done |
| Know the "right answer" for each dataset | [E5](../epics/m0-foundation-epics.md#e5-ground-truth) | Not started |  |
| Automated quality checks on every change | [E6](../epics/m0-foundation-epics.md#e6-automated-quality-gate) | In progress |  |
| Clear contributor guidance | [E7](../epics/m0-foundation-epics.md#e7-contributor-experience) | Not started |  |

## M1: Ingestion and a single clean data model

**Goal:** Bring every source into one consistent representation without losing where each value came from.

| Capability | Delivered by | Status | Notes |
|---|---|---|---|
| Accept CSV and Excel files from multiple sources | Not broken down yet | Not started |  |
| Handle real-world file quirks | Not broken down yet | Not started |  |
| Define the common model for clients, households, accounts, holdings, and balances | Not broken down yet | Not started |  |
| Standardize formats | Not broken down yet | Not started |  |
| Preserve lineage | Not broken down yet | Not started |  |
| Keep each firm's data separate | Not broken down yet | Not started |  |
| Report on data quality at intake | Not broken down yet | Not started |  |

## M2: AI-assisted mapping and entity matching

**Goal:** Cut the manual effort of figuring out what each column means and which records are the same entity.

| Capability | Delivered by | Status | Notes |
|---|---|---|---|
| Propose a mapping from each source column to the common model | Not broken down yet | Not started |  |
| Propose likely matches between records | Not broken down yet | Not started |  |
| Separate confident from uncertain suggestions | Not broken down yet | Not started |  |
| Never silently merge uncertain records | Not broken down yet | Not started |  |
| Reuse what has been learned | Not broken down yet | Not started |  |
| Keep numeric work out of the model | Not broken down yet | Not started |  |
| Measure suggestion quality | Not broken down yet | Not started |  |
| Degrade gracefully | Not broken down yet | Not started |  |

## M3: Human review and audit trail

**Goal:** Give a person efficient control over every uncertain decision, and keep a permanent record.

| Capability | Delivered by | Status | Notes |
|---|---|---|---|
| Review queue of pending decisions | Not broken down yet | Not started |  |
| Accept, correct, or reject a suggestion | Not broken down yet | Not started |  |
| See the evidence behind a suggestion | Not broken down yet | Not started |  |
| Resolve many similar items at once | Not broken down yet | Not started |  |
| Record every decision | Not broken down yet | Not started |  |
| Undo and revisit decisions | Not broken down yet | Not started |  |
| Handle conflicting decisions | Not broken down yet | Not started |  |
| Track review progress | Not broken down yet | Not started |  |
| Trace any output back to source | Not broken down yet | Not started |  |

## M4: Reconciliation and exceptions

**Goal:** Surface where the sources disagree so problems are found before the client does.

| Capability | Delivered by | Status | Notes |
|---|---|---|---|
| Detect missing records across systems | Not broken down yet | Not started |  |
| Detect value disagreements | Not broken down yet | Not started |  |
| Apply tolerances sensibly | Not broken down yet | Not started |  |
| Classify and prioritize exceptions | Not broken down yet | Not started |  |
| Manage exception resolution | Not broken down yet | Not started |  |
| Define which source wins | Not broken down yet | Not started |  |
| Summarize reconciliation health | Not broken down yet | Not started |  |
| Re-run after corrections | Not broken down yet | Not started |  |

## M5: Client-ready reporting

**Goal:** Deliver output an advisor can open, understand, and act on immediately.

| Capability | Delivered by | Status | Notes |
|---|---|---|---|
| Household summary workbook | Not broken down yet | Not started |  |
| Client-ready minimum | Not broken down yet | Not started |  |
| Exceptions view | Not broken down yet | Not started |  |
| "What changed" view | Not broken down yet | Not started |  |
| Professional presentation | Not broken down yet | Not started |  |
| Firm-specific branding and labels | Not broken down yet | Not started |  |
| Reproducible reports | Not broken down yet | Not started |  |
| Clear status of the data | Not broken down yet | Not started |  |

## M6: Operating at scale and sharing the story

**Goal:** Make the toolkit dependable across many firms and communicate the approach clearly.

| Capability | Delivered by | Status | Notes |
|---|---|---|---|
| Onboard a new firm with configuration, not new code | Not broken down yet | Not started |  |
| Run end to end with minimal setup | Not broken down yet | Not started |  |
| Protect sensitive data | Not broken down yet | Not started |  |
| Monitor and diagnose runs | Not broken down yet | Not started |  |
| Handle larger and repeated loads | Not broken down yet | Not started |  |
| Deployment write-up | Not broken down yet | Not started |  |

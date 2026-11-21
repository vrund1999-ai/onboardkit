# onboardkit

Toolkit for onboarding an advisor firm's messy CSV/Excel exports into one clean, reconciled data model, with AI-assisted column mapping, a human review step, and client-ready Excel output.

> **Status:** early scaffolding. This README describes the intended design; sections marked *planned* are not built yet. All data is synthetic.

## The problem

When an independent advisory firm moves onto a new platform, its data rarely arrives clean. It is spread across exports from a custodian, a CRM, and a hand-maintained Excel "book of business", and those sources disagree:

- Column names and formats differ per source (`Acct #`, `account_number`, `AcctNo`).
- The same client appears under several spellings (`J. Smith`, `John Smith Jr.`).
- Households are duplicated, split, or missing.
- Dates come in multiple formats, and balances do not match across systems.

Each firm is different, so the usual answer is a one-off script per client that nobody can reuse. onboardkit explores a reusable alternative: a mapping and reconciliation engine that adapts to each firm's exports and keeps a person in the loop.

## What it does (planned)

1. **Ingest.** Read messy CSV and Excel files from several simulated sources, each in a different shape.
2. **Map and normalize.** An LLM proposes column mappings and likely entity matches. Low-confidence matches go to a review screen where a person accepts or corrects them. Every decision is logged.
3. **Reconcile.** Compare sources and flag discrepancies, such as an account present at the custodian but missing from the CRM, or balances that differ between systems.
4. **Report.** Produce a formatted Excel workbook for the advisor: a household summary, an exceptions tab, and a "what changed" tab.

## Design principles

- **Human in the loop.** The model suggests; a person decides. Nothing low-confidence is merged silently.
- **Deterministic where it counts.** Numbers, joins, and comparisons are done in code, not by the model.
- **Auditable.** Mapping decisions, merges, and overrides are recorded so any output can be traced back to its source rows.
- **Reusable over one-off.** Per-firm differences live in configuration and learned mappings, not forked scripts.
- **Synthetic data only.** No real client or firm data is used anywhere in this repo.

## Planned stack

Python, FastAPI, PostgreSQL, Streamlit (review UI), openpyxl (Excel output), Claude API, Docker, GitHub Actions.

## Roadmap

| Milestone | Scope |
|---|---|
| M0 | Repo scaffold, CI, synthetic generator for messy multi-source exports |
| M1 | Ingestion and normalization into a Postgres data model |
| M2 | AI-assisted column mapping and entity matching, with confidence scores |
| M3 | Review UI and decision audit log |
| M4 | Reconciliation checks and exception reporting |
| M5 | Client-ready Excel output |
| M6 | Deployment write-up: discovery notes, tradeoffs, debugging story, and what would move into a shared platform |

## Repository layout (planned)

```
src/onboardkit/   ingestion, mapping, matching, reconciliation, reporting
app/              FastAPI service and Streamlit review UI
data/             synthetic data generator (generated files are git-ignored)
tests/            unit and integration tests
docs/             roadmap and deployment write-up
```

## License

To be added.
# touch

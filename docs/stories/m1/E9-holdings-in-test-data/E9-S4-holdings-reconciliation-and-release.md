# E9-S4: Holdings reconciliation check and release

| | |
|---|---|
| **Epic** | [E9: Holdings in the test data](../../../epics/m1-ingestion-epics.md#e9-holdings-in-the-test-data) |
| **Size** | S |
| **Depends on** | E9-S3 |
| **Blocks** | none |

## User story

As a contributor, I want a check that holdings reconcile to balances in every generated dataset, and the documentation brought up to date, so that holdings can be trusted as test data and a newcomer can find them.

## Context

E9-S1 made holdings add up in the truth, and E9-S2 and E9-S3 exported them and recorded them in the answer key. This story closes the epic: it proves the property end to end on the exported files at every mess level, and refreshes the documents that describe the data. It also records the possible later enhancements the M1 decision set aside.

## Scope

**In scope**
- A reconciliation check on the truth: for every exported account, the truth values of its holdings sum to the truth balance.
- Tests that run it for the three presets and both standard datasets.
- Documentation: demo walkthrough, source systems, fictional firm, glossary, README, architecture.
- A short "later enhancements" list for holdings.

**Out of scope**
- Reconciling the noisy exported values (that is M4's job, and ingestion scoring in E16).

## Technical design

- `answer_keys/checks.py` gets a `holdings_reconcile` check, and `onboardkit-gen check` reports it. Mess can change displayed values in the export, so the check runs on truth values, and a second check confirms that for datasets without balance mess the exported positions of an account still sum to the exported market value.
- Walkthrough: a new short subsection in `docs/demo-walkthrough.md` showing the positions file with quoted lines (guarded by the existing quote test), and a line on how holdings appear in the answer key.
- Source systems doc: the positions file, its columns, quirks.
- Later enhancements, written in `docs/fictional-firm.md`: prices over time, cost basis and tax lots, transactions, income, realistic market behavior, holdings in other sources, security name variants and holdings that disagree with balances as new kinds of mess.
- README: mention holdings in the data description if it lists what is generated.

## Files to create or change

- `src/onboardkit/datagen/answer_keys/checks.py`, `cli.py` (output of `check` if it lists checks)
- `docs/demo-walkthrough.md`, `docs/source-systems.md`, `docs/fictional-firm.md`, `docs/glossary.md`, `docs/architecture.md`, `README.md`
- `tests/datagen/answer_keys/test_holdings_reconcile.py`

## Acceptance criteria

- [ ] `onboardkit-gen check` on `clean`, `typical` and `nightmare` sample datasets reports the holdings reconciliation as passing.
- [ ] A dataset whose truth holdings are altered fails the check with a message naming the account.
- [ ] The demo walkthrough shows the positions file, and its quoted lines pass the guard.
- [ ] `docs/source-systems.md` and `docs/fictional-firm.md` describe holdings and list the later enhancements.
- [ ] Same settings still give the same data (determinism tests pass) and the answer key is still separate from the exports.
- [ ] The standard datasets contain holdings that reconcile, confirmed by a real run recorded in the PR.

## Test plan

- Reconciliation tests across presets and both standard datasets (the `demo` size marked `slow`).
- Tampering test for the failure message.
- Existing guards (links, commands, quotes, versions) pass.

## Risks and notes

- This is the story that makes the epic's "Done when" true; the PR evidence should show a generated demo dataset and the passing check output.

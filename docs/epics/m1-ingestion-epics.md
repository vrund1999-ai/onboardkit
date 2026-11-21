# M1: Ingestion and a single clean data model — Epics

This document breaks the M1 milestone from the [roadmap](../../ROADMAP.md) into epics. Like the roadmap, it describes business capabilities and outcomes, not implementation. Stories, with technical detail, are written per epic when work on it is about to start.

All data is synthetic. No real client or firm data is used anywhere.

Epic numbering continues from [M0](m0-foundation-epics.md) (E1 to E7), so every epic and story id is unique across the project.

## Milestone goal

Bring every source into one consistent representation without losing where each value came from.

## What M0 gives us

M1 starts from the datasets M0 produces: three source exports per firm (custodian CSV, CRM CSVs, a book-of-business workbook), each in a different shape and with controlled mess, plus an internal answer key. M1 consumes the exports only; the answer key is used to measure how well M1 did, never as an input.

## Epic overview

| # | Epic | Why it matters | Depends on |
|---|---|---|---|
| E8 | Common data model | One agreed vocabulary is the target every source is converted into | M0 |
| E9 | Holdings in the test data | The model includes holdings, but the M0 datasets contain none | M0 |
| E10 | File intake | Nothing else can happen until a user can submit files and see them loaded | E8 |
| E11 | Real-world file handling | Real exports have title rows, blank rows, several sheets, and odd encodings | E10 |
| E12 | Standardized values | Dates, amounts, identifiers, names, and addresses must look the same everywhere | E8, E11 |
| E13 | Lineage | Every clean value must be traceable to the original cell | E10 |
| E14 | Separate firms | One firm's onboarding must never touch another's | E10 |
| E15 | Intake quality report | A user needs to see what was loaded, skipped, and changed, and why | E11, E12 |
| E16 | Measured against the answer key | Proves the whole milestone works, with numbers instead of impressions | E12, E13, E9 |

E8 and E9 can start immediately and in parallel. E10 is the critical path. E13 and E14 can progress alongside E11 and E12.

---

## E8: Common data model

**Goal:** Define one vocabulary for clients, households, accounts, holdings, and balances, independent of any source.

**Capabilities**
- A written definition of each entity in the model (what it is, which facts it holds, which are required and which optional), in business terms first.
- A clear rule for how the model relates to the source vocabulary already used by the project (the concept catalogue), so each source column has a place to land.
- A clear distinction between facts the model keeps and facts that are source-specific notes.
- Terms added to the glossary.

**Done when**
- A newcomer can read the model definition and say where any column from any of the three sources belongs.
- Every concept in the catalogue maps to a place in the model or is explicitly marked as not carried over.

**Out of scope:** matching variants of the same person (M2); how the model is stored.

---

## E9: Holdings in the test data

**Goal:** Extend the synthetic firm so that holdings (what each account owns) exist in the exports and in the answer key.

**Capabilities**
- Each account in the fictional firm owns a believable set of holdings, with quantities and values that add up to the account balance.
- At least one source exports holdings, in its own style and with its own quirks.
- Holdings are covered by the controllable mess and by the answer key, like every other kind of data.
- The generator version and standard datasets are updated through the existing change process.

**Done when**
- A generated dataset contains holdings that reconcile to the account balances in the truth.
- Existing guarantees still hold: same settings, same data; the answer key stays separate from the exports.

**Out of scope:** realistic market behavior, prices over time, and transactions.

---

## E10: File intake

**Goal:** A user can submit a firm's exports and see them loaded.

**Capabilities**
- Accept CSV and Excel files from several sources in one submission.
- Recognize which source each file comes from, or let the user say so.
- Load each file's content as-is, before any cleaning, so nothing is lost.
- Show what was submitted and the outcome for each file.
- A single entry point that can be run repeatedly on the same submission with the same result.

**Done when**
- The standard demo dataset's `exports/` folder can be submitted and every file is accounted for.
- A file that cannot be read is reported clearly, and the rest of the submission still loads.

**Out of scope:** interpreting what columns mean (M2).

---

## E11: Real-world file handling

**Goal:** Odd layouts and encodings do not break loading.

**Capabilities**
- Find the real header when titles, report dates, or blank rows come first.
- Ignore trailer lines, blank spacer rows, and summary or archive sheets, while reporting that they were ignored.
- Read multiple sheets, including one sheet per advisor.
- Handle households that are named once with blank cells beneath.
- Handle common text encodings and byte-order marks.
- Treat values that merely look like numbers or dates (account numbers with leading zeros, text-formatted balances) with care.

**Done when**
- Every layout feature present in the M0 sources loads correctly, at every mess level.
- Each decision about a row (kept, skipped, treated as header) is recorded with a reason.

**Out of scope:** guessing the layout of sources unlike the three the project simulates.

---

## E12: Standardized values

**Goal:** The same kind of fact looks the same, whatever source it came from.

**Capabilities**
- Dates in one format, with ambiguous forms (such as `03/04/1980`) resolved by a documented rule or flagged, never guessed silently.
- Currency amounts as exact numbers, handling separators, symbols, and rounding.
- Identifiers (account numbers, household and contact keys) in one canonical form.
- Names split into consistent parts, with suffixes and casing handled.
- Addresses and states in one consistent form.
- Every change a standardization makes is recorded.

**Done when**
- All format variants the M0 generator can produce are converted correctly, or flagged as needing review.
- The result is deterministic: the same input always yields the same output.

**Out of scope:** deciding that two differently spelled names are the same person (M2).

---

## E13: Lineage

**Goal:** Every clean value can be traced back to its original file, sheet, and row.

**Capabilities**
- Each clean record and value points to the exact source location it came from.
- A person can ask "where did this come from?" and get file, sheet, row, and original text.
- A person can ask the reverse: "what became of this source row?"
- Lineage survives standardization: the original text is kept next to the clean value.

**Done when**
- For every clean value in the demo dataset, the original cell can be found and matches.

**Out of scope:** a graphical view of lineage.

---

## E14: Separate firms

**Goal:** One firm's onboarding never mixes with another's.

**Capabilities**
- Every submission belongs to one firm, named when it is created.
- Data, lineage, and reports for one firm are not visible to or combined with another's.
- Two firms can be onboarded side by side without interference.

**Done when**
- Two datasets for two fictional firms can be loaded together, and nothing from one appears in the other's results.

**Out of scope:** user accounts, logins, and permissions.

---

## E15: Intake quality report

**Goal:** A user sees what was loaded, what was skipped, and why.

**Capabilities**
- A summary per file and per source: rows read, rows kept, rows skipped, and the reason for each skip.
- A list of values that were standardized, and those that could not be and need attention.
- Obvious data problems called out, such as missing required facts or duplicate keys within a source.
- A report that can be read by a non-technical person and also saved.

**Done when**
- The report for a demo dataset accounts for every row of every file, with no unexplained gaps.

**Out of scope:** cross-source discrepancies (M4).

---

## E16: Measured against the answer key

**Goal:** Know, with numbers, how well M1 did its job.

**Capabilities**
- A check that compares standardized output with the truth and scores it: values correct, values flagged, values wrong, rows lost.
- Scores for each mess level, so improvement and regression are visible.
- Lineage checked against the answer key's record of where each row came from.
- The check is clearly separate from the pipeline: it reads the answer key, the pipeline never does.

**Done when**
- Scores for the standard datasets are recorded and checked by an automated test, so a regression fails the build.
- The score for the `clean` preset is perfect.

**Out of scope:** scoring mapping and matching suggestions (M2).

---

## Suggested order

1. **Start together:** E8 (common model) and E9 (holdings in the test data).
2. **Then:** E10 (intake), the critical path.
3. **Build on E10:** E11 (file handling), E13 (lineage), and E14 (separate firms) can progress in parallel; E12 (standardization) follows E11.
4. **Then:** E15 (quality report).
5. **Finish with:** E16 (measured against the answer key).

## Milestone exit criteria

M1 is complete when:

- The standard demo dataset can be submitted in one step and every file and row is accounted for.
- All layout and format quirks the generator produces load correctly, or are reported.
- Every clean value is expressed in the common model and traces back to its original cell.
- Two firms can be onboarded without mixing.
- The intake report explains what was loaded, skipped, and changed.
- Scores against the answer key are recorded and guarded by automated tests.

## Open questions

These need a decision before the stories are written.

- **Storage.** The README lists PostgreSQL as the planned store. Should M1 start with files or an embedded database and move to PostgreSQL when the API arrives, or use PostgreSQL from the start? This affects E10, E13 and E14.
- **Holdings scope.** How detailed should holdings be (security, quantity, price, value, asset class)? E9 assumes the minimum that reconciles to balances.
- **Ambiguous dates.** Should `03/04/1980` follow a fixed rule per source (the custodian is American), be flagged for a person, or both? E12 assumes a per-source rule plus a flag.
- **Interface.** Is a command line enough for submitting files in M1, with the API and screens left to later milestones? E10 assumes yes.

# E7-S2: Demo dataset walkthrough

| | |
|---|---|
| **Epic** | [E7: Contributor experience](../../../epics/m0-foundation-epics.md#e7-contributor-experience) |
| **Size** | S |
| **Depends on** | E4-S5 |
| **Blocks** | E7-S4 |

## User story

As a newcomer or demo audience member, I want a guided tour of the generated data, so that I can see the mess, find it in the files, and understand how it is controlled.

## Context

The generated data is the product of M0, and its value is easy to miss unless someone points at it: which file holds which facts, where the README's examples of mess actually appear, and how the truth relates to the exports. The walkthrough is also the script for demonstrating M0 to others.

## Scope

**In scope**
- `docs/demo-walkthrough.md`.
- A short "find the mess" checklist tied to the README's problem list.

**Out of scope**
- Screenshots or videos (they go stale; the commands are the source of truth).
- Building any viewer tool.

## Technical design

Sections:

1. **Generate the demo dataset.** Both standard datasets (`sample` and `demo`) from E4-S5, with their commands.
2. **Tour the exports.** For each file: what it is, its first rows (quoted from the sample dataset at the documented version), and what to notice.
   - Custodian: preamble and trailer lines, upper case, `Acct #`, American dates, balances with separators.
   - CRM: snake case headers, ISO dates, reserved-domain emails, `account_number`.
   - Book of business: title rows, one sheet per advisor, blank spacer rows, `AcctNo`, rounded balances.
3. **Find the mess.** A table mapping each README problem to where to find it:

   | README problem | Where to look | How to spot it |
   |---|---|---|
   | Column names differ | Account number headers in all three sources | `Acct #`, `account_number`, `AcctNo` |
   | Same client, several spellings | CRM contacts versus custodian owners | Nicknames, initials, suffixes |
   | Duplicated, split, or missing households | CRM household columns | Two households with the same members |
   | Multiple date formats | CRM date of birth column | ISO versus `03/04/1980` |
   | Balances do not match | Custodian versus book of business | Same account, different value |
4. **Look behind the curtain.** Open `truth/`: what each file is, how `entity_matches.csv` answers "who is the same person", with the same example followed from the exports into the key. State plainly that `truth/` is internal.
5. **Turn the dial.** Generate the same seed with `clean`, `typical`, and `nightmare`, then diff row counts or a chosen column. Show a per-type override such as `--mess names=heavy`.
6. **Verify and reproduce.** Run `verify` and `check`; regenerate and show identical output.

Specific examples quoted in the document are taken from the `sample` dataset at seed 42 for the current generator version. The guard test (E6-S3) checks that the commands run; a second check asserts that quoted example values still occur in a freshly generated sample, so stale quotes fail the build.

## Files to create or change

- `docs/demo-walkthrough.md`
- `tests/guards/test_walkthrough_examples.py` (quoted values still present)

## Acceptance criteria

- [ ] A reader can run every command in order and reach the end without errors.
- [ ] Each problem in the README's list has a row in the "find the mess" table with a concrete location.
- [ ] Quoted example rows exist in a freshly generated `sample` dataset at the documented version.
- [ ] The walkthrough clearly labels `truth/` as internal.
- [ ] It can be presented in about 15 minutes.

## Test plan

- Guard tests in CI.
- Live read-through by someone who did not write it.

## Risks and notes

- Any generator change that alters output can stale the quoted examples. The guard test turns that into a build failure with a pointer to the document, which is the intent.

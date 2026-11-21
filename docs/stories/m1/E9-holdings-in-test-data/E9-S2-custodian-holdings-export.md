# E9-S2: Custodian holdings export

| | |
|---|---|
| **Epic** | [E9: Holdings in the test data](../../../epics/m1-ingestion-epics.md#e9-holdings-in-the-test-data) |
| **Size** | M |
| **Depends on** | E9-S1 |
| **Blocks** | E9-S3 |

## User story

As a contributor, I want the custodian to export a positions file in its own style, so that datasets contain holdings the way a custodian really delivers them.

## Context

The custodian is the system of record for money data, holdings included. A real custodian sends positions as a second file beside the account master: one row per account per security, rigid and upper case, with its own quirks. This story adds that file and bumps the generator to 0.3.0, because new files change every dataset's contents and checksums.

## Scope

**In scope**
- New concepts in the catalogue for holdings.
- A custodian positions exporter and file.
- Coverage: positions exist only for accounts the custodian exports.
- Generator version bump, changelog, new standard dataset checksums.

**Out of scope**
- Holdings in the CRM or the book of business.
- Answer keys and mess for holdings (E9-S3).

## Technical design

### Concepts to add (`concepts.yaml`)

| Concept | Type |
|---|---|
| `holding.account_number` | string |
| `holding.security_symbol` | string |
| `holding.security_name` | string |
| `holding.asset_class` | string |
| `holding.quantity` | decimal |
| `holding.price` | decimal |
| `holding.value` | decimal |
| `holding.as_of` | date |

### File

`custodian_positions.csv`, under `exports/custodian/`, in the same style as the account master: UTF-8 with BOM, `\r\n`, all fields quoted.

| Line | Content |
|---|---|
| 1 | `MERIDIAN CUSTODY SERVICES - POSITION REPORT` |
| 2 | `Report date: 12/31/2025` |
| 3 | Header row |
| 4..N | One row per holding |
| N+1 | `Total positions: <count>` |

| Header | Concept | Formatter |
|---|---|---|
| `Acct #` | `holding.account_number` | passthrough |
| `Symbol` | `holding.security_symbol` | upper |
| `Security Description` | `holding.security_name` | upper |
| `Asset Class` | `holding.asset_class` | custodian code map (`EQ`, `FI`, `CASH`, `FUND`) |
| `Quantity` | `holding.quantity` | plain with thousands separators, four decimals |
| `Price` | `holding.price` | four decimals |
| `Market Value` | `holding.value` | plain with thousands separators, two decimals |
| `Price Date` | `holding.as_of` | `%Y%m%d` |

Rows are sorted by account number, then symbol. Account numbers use the same display form as the account master (mess may alter them later, E9-S3).

### Projection and coverage

One `SourceRow` per `TruthHolding` of an account that appears in the custodian's account master after coverage. `refs` carries `holding_id`, `account_id`, `security_id`. If coverage removes an account from the custodian, its positions go too, and the coverage event covers both.

### Release

Bump `GENERATOR_VERSION` to `0.3.0`, add the changelog entry (new file, new concepts, new dataset ids), refresh the checksums (`python scripts/update_expected_checksums.py`), and update the documented sample dataset id in the walkthrough if it changes.

## Files to create or change

- `src/onboardkit/datagen/sources/concepts.yaml`, `custodian_positions.py` (new), `custodian.py` (register), `pipeline.py` as needed
- `src/onboardkit/datagen/__init__.py` (version), `docs/datagen-changelog.md`, `tests/datagen/expected/standard_datasets.json`
- `docs/source-systems.md`, `docs/demo-walkthrough.md` (a short positions section and quoted lines, only if the ids change or a quote is added), `docs/mess-catalogue.md` only if regenerated
- `tests/datagen/sources/test_custodian_positions.py`

## Acceptance criteria

- [ ] `exports/custodian/custodian_positions.csv` exists in a generated dataset with the preamble, header, and trailer above, and the trailer count equals the data rows.
- [ ] Position values for each account sum to that account's balance in the custodian account master (before mess).
- [ ] Quantities, prices, values, and dates appear in the formats in the table.
- [ ] Every column's concept is in the catalogue and documented in `docs/source-systems.md`.
- [ ] Removing an account from the custodian removes its positions.
- [ ] The generator version is 0.3.0, the changelog entry exists, and the standard dataset checksum test passes.
- [ ] `onboardkit-gen check` passes on a generated dataset.

## Test plan

- Snapshot of the first lines for the sample dataset at seed 42.
- Reconciliation test per account (positions sum to the master's market value).
- Coverage test with an uncovered account.
- Determinism and manifest tests from M0 still pass.

## Risks and notes

- The positions file changes every dataset id and checksum; update every doc that quotes an id (a test names stale ids).
- Account number mess (E9-S3) must not break the join; the answer key must record the account each row belongs to.

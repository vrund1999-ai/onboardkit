# E9-S1: Securities and holdings in the truth firm

| | |
|---|---|
| **Epic** | [E9: Holdings in the test data](../../../epics/m1-ingestion-epics.md#e9-holdings-in-the-test-data) |
| **Size** | L |
| **Depends on** | none |
| **Blocks** | E9-S2 |

## User story

As a contributor, I want every account in the fictional firm to own a believable set of holdings that add up to its balance, so that the product has holdings to ingest and reconcile.

## Context

The M0 truth firm has accounts with a balance but nothing inside them. The common model (E8) includes holdings, and the roadmap names the custodian as the authority for them. Per the M1 decision, holdings stay minimal: security, quantity, value, asset class. Prices over time, cost basis, transactions, and income are deliberately left for later.

## Scope

**In scope**
- A small fictional security master (synthetic names and identifiers, with asset classes).
- Holdings per account: quantities and values that sum exactly to the account balance.
- Profile settings for how holdings are generated (number per account, asset class mix by account type).
- Validation that holdings reconcile to balances.

**Out of scope**
- Any export of holdings (E9-S2) and answer keys (E9-S3).
- Prices over time, cost basis, tax lots, transactions, income, realistic market behavior.
- Real tickers or real CUSIP numbers.

## Technical design

### Model

Add to `truth/model.py`:

- `TruthSecurity`: `security_id` (`SEC-001`), `symbol`, `name`, `asset_class` (`equity`, `fixed_income`, `cash`, `fund`), `price` (`Decimal`, 4 places, one fixed price as of the as-of date).
- `TruthHolding`: `holding_id` (`HOLD-000001`), `account_id`, `security_id`, `quantity` (`Decimal`, 4 places), `value` (`Decimal`, 2 places).
- `TruthFirm` gains `securities` and `holdings` tuples, defaulting to empty so older code paths keep working.

### Security master

About 40 fictional securities generated from word lists in `firm_profile.yaml` (fictional company and fund names, invented symbols such as `LNTR`, `MRDN`; a check forbids symbols that are well-known real tickers via a short denylist in the profile). A `cash` security (`CASH`, price 1.0000) is always present.

### Building holdings

For each open or restricted account (closed accounts hold only cash, or nothing if the profile says so):

1. Draw the number of holdings from the profile (for example 3 to 12; fewer for small accounts).
2. Draw an asset class mix by account type (for example a Roth IRA leans equity, a 529 leans fund, the profile gives weights).
3. Choose distinct securities, draw weights, and allocate the balance by weight.
4. Value is `quantity x price`, so quantity is computed as `value / price` rounded to 4 places, then the value is recomputed as `round(quantity x price, 2)`.
5. **Absorb the remainder in the cash holding (or the largest holding if there is no cash)** so the sum equals the balance exactly, to the cent.

All randomness uses named streams: `derive_rng(seed, "holdings", account_id)`. A new stream label means existing streams, and therefore existing generated data, do not change.

### Validation

`truth/validate.py` gains: holdings reference known accounts and securities; no account holds the same security twice; **sum of holding values equals the account balance for every account**; quantities positive; values positive.

## Files to create or change

- `src/onboardkit/datagen/truth/model.py`, `profile.py`, `builder.py`, `validate.py`, `firm_profile.yaml`
- `docs/fictional-firm.md` (new section on securities and holdings, numbers match the profile)
- `tests/datagen/truth/test_holdings.py`

## Acceptance criteria

- [x] Every account has at least one holding, and the holding values sum exactly to the account balance.
- [x] The same configuration produces identical securities and holdings on every run.
- [x] Holdings generation does not change any existing generated file: the `exports/` and `truth/` bytes of the standard datasets are unchanged at this point (holdings are not yet written).
- [x] Validation rejects a firm whose holdings do not sum to the balance, references an unknown security, or repeats a security in an account.
- [x] No security symbol or identifier is on the real-ticker denylist.
- [x] `docs/fictional-firm.md` describes the numbers in the profile.

## Test plan

- Property tests over several seeds and both sizes: sum equals balance, quantities positive, distinct securities per account.
- Isolation test: the standard dataset checksums recorded for 0.2.0 still match.
- Negative tests for each validation rule.
- Determinism test across two builds.

## Risks and notes

- Rounding is the whole difficulty. Keep the remainder rule simple and tested at the extremes (a tiny balance, a huge one).
- The `docs/fictional-firm.md` numbers are guarded together with the profile, so change both in this story.

## Notes

- Code lives in `truth/holdings.py`; the numbers are the `holdings` section of `firm_profile.yaml` and section 10 of `docs/fictional-firm.md`. `TruthFirm` gained `securities` and `holdings` (default empty). Holdings are drawn from streams named `holdings/securities` and `holdings/account/<account id>`, built after all accounts, so existing streams are untouched.
- Truth validation (`find_problems`) checks holdings only when a firm has securities or holdings, so a firm built by hand without them still validates.
- To keep existing generated bytes unchanged, `truth/firm.json` excludes `securities` and `holdings` for now (see `answer_keys/truth_files.py`); E9-S3 decides how they enter the answer key.
- Security names and symbols are invented; coincidence of a four-letter symbol with an obscure real ticker is possible and harmless. A denylist of famous real tickers is enforced in the builder test and in validation.
- Closed accounts hold only cash (their balance is still positive). Cash is `SEC-001` and absorbs the rounding remainder.
- Real-run check: 15 households give 43 accounts and 337 holdings; 300 households give 755 accounts and 5,902 holdings. Both reconcile exactly. The sample dataset's 16 files hash the same as the recorded 0.2.0 checksums.

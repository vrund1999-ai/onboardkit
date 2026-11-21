# E1-S4: Truth model and firm population builder

| | |
|---|---|
| **Epic** | [E1: Fictional firm and shared vocabulary](../../../epics/m0-foundation-epics.md#e1-fictional-firm-and-shared-vocabulary) |
| **Size** | L |
| **Depends on** | E1-S1, E6-S1 |
| **Blocks** | E2-S1, E4-S1 |

## User story

As a contributor, I want a deterministic builder that creates the complete, clean fictional firm (people, households, accounts, balances), so that every source export and answer key derives from one internally consistent truth.

## Context

Everything downstream is a projection of this truth: exports are views of it with deliberate omissions and mess, and answer keys describe how exported rows relate back to it. The truth model is internal to the generator. It is **not** the M1 canonical data model, and the two may differ.

## Scope

**In scope**
- Truth entity models: person, household, account, with ownership and beneficiary relationships.
- A firm profile configuration transcribing the numbers from E1-S1.
- A deterministic builder producing a population of a requested number of households.
- The random stream utility (`rng.py`) used by the whole generator.

**Out of scope**
- Holdings and transactions (not needed in M0).
- Mess, coverage, or file output.
- Edge cases deferred from M0 (trusts, business accounts, deceased clients).

## Technical design

### Random streams (`rng.py`)

```python
def derive_rng(root_seed: int, *labels: str) -> random.Random: ...
```

Hash `f"{root_seed}:" + ":".join(labels)` with SHA-256, take the first 8 bytes as an integer seed for a `random.Random`. Never use Python's built-in `hash()` (salted per process). Each component asks for its own named stream (`"people"`, `"households"`, `"accounts"`, `"balances"`), so adding a new consumer does not change existing output. A companion `faker_for(root_seed, label)` returns a `Faker("en_US")` instance seeded with `Faker.seed_instance`.

### Models (Pydantic, frozen)

- `TruthPerson`: `person_id` (`P-00001`), `first_name`, `middle_initial` (optional), `last_name`, `suffix` (optional), `date_of_birth`, `email`, `phone`, address fields, `tax_id_last4`, `household_id`, `household_role` (`primary`, `spouse`, `dependent`).
- `TruthHousehold`: `household_id` (`HH-0001`), `display_name`, `advisor`, `client_since`, `member_ids`.
- `TruthAccount`: `account_id` (`ACCT-000001`), `account_number` (synthetic, fixed width, fictional prefix), `account_type` (enum), `owner_ids`, `beneficiary_id` (529 only), `registration_title`, `status`, `open_date`, `balance` (`Decimal`), `balance_as_of`, `household_id`.
- `TruthFirm`: lists of the above plus the profile used, with lookup helpers.

### Builder (`truth/builder.py`)

`build_firm(profile, n_households, root_seed, as_of_date) -> TruthFirm`:

0. Give every household its own stream, `derive_rng(root_seed, "household", str(index))`, so that household `i` is identical regardless of how many households are built. This is what makes the 15-household sample a true prefix of the 300-household default.
1. Pick each household's archetype by weighted draw (E1-S1 shares).
2. Create members: shared last name for couples (some couples with different surnames), ages and dates of birth by role, children younger than parents by at least 18 years.
3. Assign advisor (weighted), client-since date after the primary's 21st birthday and before `as_of_date`.
4. Draw account count from the profile distribution, then types subject to rules: IRAs single owner and owner must be an adult; joint needs two adults; 529 owner is an adult, beneficiary a dependent.
5. Draw balances (log-normal, clamped, rounded to cents), `Decimal` only.
6. Generate registration titles from owners and type, for example `JOHN A SMITH & JANE B SMITH JTWROS`.
7. Assign sequential identifiers in creation order.

### Invariants checked by a `validate_firm` function

Unique identifiers; every member id resolves; every owner belongs to the account's household; no balance at or below zero; account open date not before the oldest owner turned 18 (children's 529 excepted); `balance_as_of == as_of_date`.

### Configuration

`src/onboardkit/datagen/truth/firm_profile.yaml` holds archetype shares, account-count distribution, type weights, balance parameters, advisors, and date ranges. A `FirmProfile` Pydantic model validates it, including that shares sum to 1.

## Files to create or change

- `src/onboardkit/datagen/rng.py`
- `src/onboardkit/datagen/truth/model.py`
- `src/onboardkit/datagen/truth/profile.py` and `firm_profile.yaml`
- `src/onboardkit/datagen/truth/builder.py`, `validate.py`
- `tests/datagen/truth/`

## Acceptance criteria

- [ ] `build_firm(..., n_households=15)` and `n_households=300` both succeed and pass `validate_firm`.
- [ ] Two calls with identical arguments return equal `TruthFirm` objects.
- [ ] Changing the root seed changes the output; changing the household count does not change the first 15 households' people attributes (stream independence is documented and tested where promised).
- [ ] Archetype shares in a 300-household build are within 5 percentage points of the profile.
- [ ] All ownership rules from E1-S1 hold for every account.
- [ ] No `float` is used for money; all balances are `Decimal` with two decimal places.
- [ ] Module imports nothing that reads the clock or global random state.

## Test plan

- Unit tests per rule (IRA single owner, joint needs two adults, 529 beneficiary a dependent).
- Property-style test over several seeds asserting `validate_firm` passes.
- Determinism test: build twice, compare via `model_dump_json`.
- Statistical tolerance test on archetype and account-count shares for 300 households.
- Regression test pinning the first person of seed 42 so unintended Faker upgrades surface.

## Risks and notes

- Faker output can change across versions. The lockfile pins it, and the manifest (E4-S3) records the version.
- Keep the truth model minimal. If a field is not exported by some source, it does not belong here.

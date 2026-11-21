# E8-S4: Model schema and migrations

| | |
|---|---|
| **Epic** | [E8: Common data model](../../../epics/m1-ingestion-epics.md#e8-common-data-model) |
| **Size** | L |
| **Depends on** | E8-S1, E8-S2, E8-S3 |
| **Blocks** | the E10, E13 and E14 stories |

## User story

As a contributor, I want the common model created in PostgreSQL by versioned migrations, so that every later story stores clean data in one agreed shape and database changes are reviewable.

## Context

E8-S1 defined the model in business terms and E8-S2 tied the catalogue to it. This story turns it into tables. Firm separation (E14) and lineage (E13) shape the layout, so the keys they need exist from the start even though those epics add behavior later.

## Scope

**In scope**
- Alembic set up with a first migration creating the model tables.
- SQLAlchemy table definitions that match.
- Every table carries the firm it belongs to.
- Space for original values and source record references, used by E13.
- A command to bring a database to the latest version.

**Out of scope**
- Loading data (E10), standardization (E12), lineage behavior (E13), and enforcement of firm isolation beyond the keys (E14).
- Deduplication of people or accounts (M2).

## Technical design

### Tables (names indicative; follow E8-S1)

| Table | Notes |
|---|---|
| `firm` | id, name (unique) |
| `source_system` | id, firm_id, kind (`custodian`, `crm`, `book_of_business`), name |
| `household` | id, firm_id, name, advisor |
| `client` | id, firm_id, household_id nullable, name parts, suffix, date_of_birth, email, phone, address fields, tax_id_last4, household_role, client_since |
| `account` | id, firm_id, account_number, type, registration, status, open_date |
| `account_owner` | account_id, client_id (many to many) |
| `balance` | id, firm_id, account_id, source_system_id, amount `NUMERIC(18,2)`, as_of_date |
| `security` | id, firm_id, identifier, description, asset_class |
| `holding` | id, firm_id, account_id, security_id, source_system_id, quantity `NUMERIC(18,6)`, value `NUMERIC(18,2)`, as_of_date |
| `source_record` | id, firm_id, source_system_id, file, sheet nullable, row_number, raw_text (the lineage anchor) |
| `alias` | entity kind, entity id, source_system_id, source key (each source's own identifier) |

- Primary keys are `BIGINT` identity columns. Foreign keys are real constraints with `ON DELETE RESTRICT`.
- Accounts are unique on `(firm_id, account_number)`; other natural keys are not unique because sources contain duplicates (M2 resolves them).
- `firm_id` on every table is `NOT NULL`, indexed, and part of the foreign keys (composite foreign keys where practical) so one firm cannot reference another's rows.
- Tables are plain SQLAlchemy 2 `Table` objects in `onboardkit.model.tables`. `entities.py` (E8-S2) is checked against them by a test, so the map, the document, and the schema cannot drift.
- Alembic environment under `src/onboardkit/db/migrations/`; one linear history; first revision `0001_initial_model`.
- `onboardkit db upgrade` (new Typer command line) brings the database to the latest version; `onboardkit db current` prints the version. Logic lives in `onboardkit.db.migrate`; the command only calls it.

## Files to create or change

- `src/onboardkit/model/tables.py`
- `src/onboardkit/db/migrate.py`, `src/onboardkit/db/migrations/` (environment and first revision)
- `src/onboardkit/cli.py`, `pyproject.toml` (console script `onboardkit`)
- `tests/model/test_schema.py`, `tests/db/test_migrations.py`
- `docs/data-model.md` (link to the schema), `docs/architecture.md` (module map rows for `db/` and `model/`; the architecture guard checks them), `docs/getting-started.md`

## Acceptance criteria

- [ ] `onboardkit db upgrade` on an empty database creates every table above, and running it twice changes nothing.
- [ ] Every table except `firm` has a non-null `firm_id`.
- [ ] Money and quantities are `NUMERIC`, never floating point.
- [ ] Inserting a row that references another firm's account is rejected by the database.
- [ ] The tables in code match the entity list used by the concept map (a test fails on drift).
- [ ] A downgrade and upgrade round trip succeeds.
- [ ] The architecture module map lists the new packages and the guard passes.

## Test plan

- `db` tests: upgrade from empty, idempotence, downgrade round trip, constraint rejections (cross-firm reference, orphan holding).
- Pure test: table definitions versus `entities.py` and `concept_map.yaml`.

## Risks and notes

- Composite firm-scoped foreign keys make queries more verbose but give E14 a real guarantee; keep helper functions for common joins.
- Keep the first migration reviewable: one file, no data.
- If SQLAlchemy plus Alembic feels heavy, record the reason in the PR before changing the choice; the story assumes them.

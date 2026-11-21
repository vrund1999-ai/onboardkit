# E8-S3: Local PostgreSQL and test database

| | |
|---|---|
| **Epic** | [E8: Common data model](../../../epics/m1-ingestion-epics.md#e8-common-data-model) |
| **Size** | M |
| **Depends on** | none |
| **Blocks** | E8-S4 |

## User story

As a contributor, I want a PostgreSQL database that starts with one command, and tests that use a real database safely, so that everything built in M1 runs against the store the product will use.

## Context

The M1 decision is PostgreSQL from the start. That brings three needs: start it locally without installing anything beyond Docker, let tests use a real database without risking a developer's data, and run those tests in CI. Windows CI jobs cannot run service containers, so database tests run on Linux only.

## Scope

**In scope**
- A Docker Compose file with PostgreSQL 16 for local development.
- Connection settings read from the environment, with a documented local default.
- A `db` pytest marker and fixtures that create and drop a throwaway database per test session.
- A CI service container so the `db` tests run on Linux.
- Documentation in the getting started guide.

**Out of scope**
- Any tables (E8-S4).
- Production deployment or hosting.

## Technical design

- `compose.yaml` at the repository root: service `db`, image `postgres:16`, port `5432`, a named volume, a healthcheck, and credentials that are obviously local (`onboardkit` / `onboardkit`).
- `onboardkit.db.settings`: `database_url()` reads `ONBOARDKIT_DATABASE_URL`, defaulting to the local compose database. The password is never logged.
- `onboardkit.db.engine`: create a SQLAlchemy engine from the URL.
- Test fixtures in `tests/db/conftest.py`:
  - a session fixture creates a database named `onboardkit_test_<random>` on the server, yields its URL, and drops it afterwards;
  - a function fixture isolates each test (rolled-back transaction or truncation);
  - a guard refuses to run if the URL's database name does not start with `onboardkit_test_`.
- Marker `db` registered in `pyproject.toml`. When no server is reachable the `db` tests are skipped locally with a clear reason, but fail when `CI=true`, so a missing database cannot hide.
- CI: a `services: postgres` block on the ubuntu test job only; the windows job runs `-m "not db"`.
- `onboardkit-gen` is unaffected.

## Files to create or change

- `compose.yaml`
- `src/onboardkit/db/__init__.py`, `settings.py`, `engine.py`
- `tests/db/conftest.py`, `tests/db/test_connection.py`
- `pyproject.toml` (dependencies `sqlalchemy`, `psycopg[binary]`, `alembic`; the marker)
- `.github/workflows/ci.yml`
- `docs/getting-started.md`, `docs/testing.md`; `.gitleaks.toml` only if the local default credentials are flagged.

## Acceptance criteria

- [ ] `docker compose up -d db` starts PostgreSQL 16 and the healthcheck reports healthy.
- [ ] `database_url()` uses `ONBOARDKIT_DATABASE_URL` when set, and the local default otherwise.
- [ ] The `db` fixtures create a throwaway database and drop it when the session ends.
- [ ] A test refuses to run against a database whose name is not a test database.
- [ ] Without a reachable server, `db` tests are skipped locally and fail under `CI=true`.
- [ ] CI runs the `db` tests on ubuntu with a PostgreSQL service, and the windows job skips them.
- [ ] The getting started guide explains starting the database.

## Test plan

- Connection test using the fixtures (`SELECT 1`, and the database name check).
- Test of the skip-versus-fail rule with the environment variable simulated.
- Test of the refusal guard with a bad URL.

## Risks and notes

- Coverage threshold: the `db` tests must be included in the coverage run on ubuntu; the windows job cannot reach the threshold alone, so the threshold is enforced on the ubuntu job. Decide and document in `docs/testing.md`.
- Docker becomes a local requirement for the database tests only; generator work still needs nothing beyond Python.

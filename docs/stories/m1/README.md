# M1 Stories

Implementation-ready stories for the epics in [M1: Ingestion and a single clean data model](../../epics/m1-ingestion-epics.md). Each story is its own file and carries the technical detail needed to build it.

Stories are written per epic when work on it is about to start, so this index grows over time. Written so far: E8 and E9. E10 to E16 are not written yet; their scope is in the epics document.

## Story index

| Story | Title | Size | Depends on |
|---|---|---|---|
| **E8: Common data model** | | | |
| [E8-S1](E8-common-data-model/E8-S1-model-definition.md) | Model definition and glossary terms | M | none |
| [E8-S2](E8-common-data-model/E8-S2-catalogue-to-model-mapping.md) | Catalogue to model mapping | M | E8-S1 |
| [E8-S3](E8-common-data-model/E8-S3-local-database-and-test-database.md) | Local PostgreSQL and test database | M | none |
| [E8-S4](E8-common-data-model/E8-S4-model-schema-and-migrations.md) | Model schema and migrations | L | E8-S1, E8-S2, E8-S3 |
| **E9: Holdings in the test data** | | | |
| [E9-S1](E9-holdings-in-test-data/E9-S1-securities-and-holdings-in-truth.md) | Securities and holdings in the truth firm | L | none |
| [E9-S2](E9-holdings-in-test-data/E9-S2-custodian-holdings-export.md) | Custodian holdings export | M | E9-S1 |
| [E9-S3](E9-holdings-in-test-data/E9-S3-holdings-answer-keys-and-mess.md) | Holdings in the answer keys and mess | M | E9-S2 |
| [E9-S4](E9-holdings-in-test-data/E9-S4-holdings-reconciliation-and-release.md) | Holdings reconciliation check and release | S | E9-S3 |

Sizes are relative: S is roughly half a day, M one to two days, L three days or more.

## Suggested build order

1. **Start together:** E8-S1 (model definition), E8-S3 (database), E9-S1 (holdings in the truth).
2. E8-S2 (mapping), E9-S2 (holdings export).
3. E8-S4 (schema), E9-S3, then E9-S4.

## Technical conventions (apply to every M1 story)

M0 conventions in the [M0 story README](../m0/README.md) still apply (tooling, determinism, money as `Decimal`, synthetic data only). M1 adds the following.

### Decisions already made

These come from the [M1 decisions](../../epics/m1-ingestion-epics.md#decisions).

| Concern | Choice |
|---|---|
| Storage | PostgreSQL from the start |
| Interface | Command line only; API and screens come later (see the [roadmap](../../../ROADMAP.md#interface-by-milestone)) |
| Holdings detail | Minimum that reconciles to balances: security, quantity, value, asset class |
| Ambiguous dates | A documented per-source rule, plus a flag for a person |

### Tooling additions

| Concern | Choice |
|---|---|
| Database | PostgreSQL 16, run locally with Docker Compose |
| Driver and access | `psycopg` 3 with SQLAlchemy 2 |
| Migrations | Alembic, one linear history |
| Product command line | Typer; console script `onboardkit` (separate from the generator's `onboardkit-gen`) |

### Package layout

```
src/onboardkit/
  datagen/             the generator (M0), unchanged in structure
  db/                  connection settings, engine, migration runner
  model/               the common data model: entity definitions and table layout
  ingest/              file intake and standardization (E10 onward)
  cli.py               the product command line; calls into the packages above only
tests/                 mirrors the package layout
docs/data-model.md     the model in business terms (E8-S1)
```

### Cross-cutting rules

- **Logic is separate from the command line.** Anything the command line does is a function in a package; the command only parses arguments and prints. This is what lets a later API call the same code.
- **The pipeline never reads `truth/`.** Ingestion consumes `exports/` only. Only evaluation code (E16) reads the answer key.
- **Tests that need a database** use the marker `db`, run against a throwaway database, and never touch a developer's own data. See E8-S3.
- **Every schema change is a migration.** No table is created or altered outside Alembic.
- **Money** is `Decimal` in code and `NUMERIC` in the database; quantities are `NUMERIC` too. Never floats.

## Story template

Same as M0: header table, user story, context, scope (with out-of-scope), technical design, files to create or change, acceptance criteria as a checklist, test plan, risks and notes.

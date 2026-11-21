# Architecture

How the dataset generator is put together. This describes what exists today (milestone M0); the [roadmap](../ROADMAP.md) covers what is planned.

## Pipeline

```
config -> truth firm -> per-source rows -> coverage -> mess -> exports
                                    \                      \
                                     +---- events ----------+--> answer keys (truth/)
```

1. **Config.** A preset (how messy), a size, a seed and an as-of date resolve to one validated configuration (`config.py`, `presets/`).
2. **Truth firm.** A clean fictional firm of households, people and accounts is built from `truth/firm_profile.yaml` using named random streams (`truth/`).
3. **Per-source rows.** Each source system projects its own view of the truth, with its own headers, formats and quirks (`sources/`).
4. **Coverage.** Each source leaves some entities out and may add stale extras, so no source is complete. Each omission is a `CoverageEvent`.
5. **Mess.** Pluggable mess types (names, households, formats, balances) alter the rows. Every change is a `MessEvent` carrying before and after values (`mess/`).
6. **Exports.** The rows are written as CSV and Excel files under `exports/`.
7. **Answer keys.** From the truth, the rows and the events, the generator writes `truth/`: which rows are the same entity, what was changed, what each column means, and which values disagree (`answer_keys/`). A `manifest.json` then lists every file with its checksum.

## Module map

Everything is under `src/onboardkit/datagen/`.

| Path | Purpose |
|---|---|
| `answer_keys/` | Writers for the internal answer key in `truth/`, plus the consistency and separation checks |
| `mess/` | The mess contract, registry and engine, and the four mess types |
| `presets/` | The `clean`, `typical` and `nightmare` preset files |
| `sources/` | The concept catalogue, source profiles and exporters (custodian, CRM, book of business), formatters, writers, coverage |
| `truth/` | The clean fictional firm: model, profile, builder, validation |
| `cli.py` | The `onboardkit-gen` command line (`generate`, `presets`, `verify`, `check`, `show`) |
| `config.py` | Configuration models and preset resolution |
| `manifest.py` | The manifest: checksums for every file, and verification |
| `pipeline.py` | Runs the stages in order and publishes the dataset atomically |
| `rng.py` | Named, stable random streams |
| `standard.py` | The two standard datasets, `sample` and `demo`, and their checksums |

## Core types

- `TruthFirm` (with `TruthHousehold`, `TruthPerson`, `TruthAccount`): the clean facts. Internal to the generator.
- `SourceRow`: one row of one source table, with its values, a stable `row_uid` and references back to the truth entities it came from.
- `MessEvent`: one deliberate change: type, subtype, rows affected, concept, before and after values, effect (`entity_variant`, `format_variant`, `value_conflict`, `structural`), and severity or ambiguity where relevant.
- `CoverageEvent`: one entity left out of a source, or one stale extra row added.

## Determinism

The same configuration produces byte-identical files.

- **Named streams.** Every component draws from its own stream, `derive_rng(seed, "label", ...)`, derived with SHA-256. Adding a new consumer never changes the output of existing ones. Python's salted `hash()` is never used.
- **Fixed clock.** Nothing reads the current time. Dates come from the as-of date, and Excel workbooks carry a fixed timestamp and are written deterministically.
- **Stable order.** Mess types run in a fixed order, and collections are sorted before they are written.

A test compares two runs, runs in separate processes with different hash seeds, and the recorded checksums of the standard datasets.

## Truth versus exports

`exports/` is what a real firm would deliver. `truth/` is how a product's answers are scored, and it is internal.

The boundary is enforced in three ways: code that builds or writes exports cannot import `answer_keys` (`tests/datagen/test_import_boundary.py`), no truth identifier may appear in an export (`onboardkit-gen check`), and `truth/README.txt` states the rule in the folder itself.

## Extension points

- **Add a mess type** or **add a source column**: step-by-step recipes are in [CONTRIBUTING.md](../CONTRIBUTING.md).
- **The common data model** that ingestion converts into is described in [data-model.md](data-model.md).
- **Later milestones.** Ingestion (M1 onward) consumes `exports/` only. Evaluation consumes `truth/`. Neither reaches into the generator's internals.

## Decisions

| Decision | Why |
|---|---|
| `src/` layout, with the generator in a package | The product code will grow beside it, and installed code is what tests import |
| Generated data in `data/generated/`, git-ignored | Datasets are reproducible from a seed, so they are never committed |
| YAML plus Pydantic for configuration and profiles | Humans edit YAML; Pydantic rejects mistakes with clear messages |
| Typer for the command line | Typed arguments give help text and validation for free |
| Concept ids separate from column headers | Sources name the same fact differently; answer keys and tests need one stable name |
| Mess recorded as events | A score needs to know exactly what was changed, not just that something was |
| `Decimal` for money | Floats cannot represent cents exactly |

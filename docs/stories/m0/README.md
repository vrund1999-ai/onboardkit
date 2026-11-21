# M0 Stories

Implementation-ready stories for the seven epics in [M0: Foundation and realistic test data](../../epics/m0-foundation-epics.md). Each story is its own file and carries the technical detail needed to build it.

## Story index

| Story | Title | Size | Depends on |
|---|---|---|---|
| **E1: Fictional firm and shared vocabulary** | | | |
| [E1-S1](E1-fictional-firm/E1-S1-firm-profile.md) | Fictional firm profile | S | none |
| [E1-S2](E1-fictional-firm/E1-S2-glossary.md) | Business glossary | S | none |
| [E1-S3](E1-fictional-firm/E1-S3-source-system-catalogue.md) | Source system and concept catalogue | M | E1-S1, E1-S2 |
| [E1-S4](E1-fictional-firm/E1-S4-truth-model-and-population.md) | Truth model and firm population builder | L | E1-S1, E6-S1 |
| **E2: Multi-source messy exports** | | | |
| [E2-S1](E2-source-exports/E2-S1-exporter-framework.md) | Source exporter framework | M | E1-S4 |
| [E2-S2](E2-source-exports/E2-S2-custodian-export.md) | Custodian export | M | E2-S1, E1-S3 |
| [E2-S3](E2-source-exports/E2-S3-crm-export.md) | CRM export | M | E2-S1, E1-S3 |
| [E2-S4](E2-source-exports/E2-S4-book-of-business-export.md) | Book of business workbook | L | E2-S1, E1-S3 |
| [E2-S5](E2-source-exports/E2-S5-source-coverage-and-overlap.md) | Source coverage and overlap | M | E2-S2, E2-S3, E2-S4 |
| **E3: Controllable mess** | | | |
| [E3-S1](E3-controllable-mess/E3-S1-mess-engine.md) | Mess engine and event log | M | E2-S1 |
| [E3-S2](E3-controllable-mess/E3-S2-mess-settings-and-intensity.md) | Mess settings and intensity model | S | E3-S1, E4-S1 |
| [E3-S3](E3-controllable-mess/E3-S3-name-mess.md) | Name mess | M | E3-S1, E3-S2 |
| [E3-S4](E3-controllable-mess/E3-S4-household-mess.md) | Household mess | L | E3-S1, E3-S2 |
| [E3-S5](E3-controllable-mess/E3-S5-format-and-identifier-mess.md) | Format and identifier mess | M | E3-S1, E3-S2 |
| [E3-S6](E3-controllable-mess/E3-S6-balance-mismatch-mess.md) | Balance mismatch mess | M | E3-S1, E3-S2 |
| [E3-S7](E3-controllable-mess/E3-S7-presets-and-coverage.md) | Presets and mess coverage | M | E3-S3 to E3-S6 |
| **E4: Reproducible datasets** | | | |
| [E4-S1](E4-reproducible-datasets/E4-S1-dataset-config-and-seeding.md) | Dataset configuration and seeding | M | E1-S4 |
| [E4-S2](E4-reproducible-datasets/E4-S2-pipeline-and-output-layout.md) | Generation pipeline and output layout | M | E2-S5, E4-S1 |
| [E4-S3](E4-reproducible-datasets/E4-S3-manifest-and-versioning.md) | Dataset manifest and versioning | S | E4-S2 |
| [E4-S4](E4-reproducible-datasets/E4-S4-cli.md) | Generator command line | M | E4-S2, E4-S3 |
| [E4-S5](E4-reproducible-datasets/E4-S5-determinism-and-standard-datasets.md) | Determinism guarantee and standard datasets | M | E4-S4, E3-S7 |
| **E5: Ground truth** | | | |
| [E5-S1](E5-ground-truth/E5-S1-provenance-and-row-locators.md) | Row provenance and locators | M | E2-S1 |
| [E5-S2](E5-ground-truth/E5-S2-entity-match-answer-key.md) | Entity match answer key | M | E5-S1 |
| [E5-S3](E5-ground-truth/E5-S3-column-mapping-answer-key.md) | Column mapping answer key | S | E1-S3, E2-S1 |
| [E5-S4](E5-ground-truth/E5-S4-discrepancy-answer-key.md) | Discrepancy answer key | M | E5-S1, E3-S1 |
| [E5-S5](E5-ground-truth/E5-S5-truth-separation-and-consistency.md) | Truth separation and consistency checks | M | E5-S2 to E5-S4 |
| **E6: Automated quality gate** | | | |
| [E6-S1](E6-quality-gate/E6-S1-project-scaffold.md) | Project scaffold and tooling | M | none |
| [E6-S2](E6-quality-gate/E6-S2-ci-workflow.md) | Continuous integration workflow | S | E6-S1 |
| [E6-S3](E6-quality-gate/E6-S3-test-strategy-and-generation-guards.md) | Test strategy and generation guards | M | E6-S1, E4-S2 |
| [E6-S4](E6-quality-gate/E6-S4-repository-hygiene-guards.md) | Repository hygiene guards | S | E6-S2, E6-S3 |
| [E6-S5](E6-quality-gate/E6-S5-branch-protection-and-pr-template.md) | Branch protection and PR template | S | E6-S2, E6-S4 |
| **E7: Contributor experience** | | | |
| [E7-S1](E7-contributor-experience/E7-S1-getting-started-guide.md) | Getting started guide | S | E6-S1, E4-S4 |
| [E7-S2](E7-contributor-experience/E7-S2-demo-walkthrough.md) | Demo dataset walkthrough | S | E4-S5 |
| [E7-S3](E7-contributor-experience/E7-S3-contributing-and-architecture.md) | Contributing guide and architecture overview | M | E6-S5 |
| [E7-S4](E7-contributor-experience/E7-S4-readme-roadmap-refresh-and-clean-room-test.md) | README and roadmap refresh, clean-room test | S | all others |

Sizes are relative: S is roughly half a day, M one to two days, L three days or more.

## Suggested build order

1. **Day-one parallel work:** E6-S1 (scaffold), E1-S1, E1-S2 (documents).
2. E6-S2 (CI), E1-S3 (catalogue), E1-S4 (truth model).
3. E2-S1, then E2-S2 / E2-S3 / E2-S4 in parallel, then E2-S5.
4. E4-S1 early (it is needed by E3-S2), then E3-S1 and E5-S1.
5. E3-S2 to E3-S6 and E5-S2 to E5-S4 in parallel, then E3-S7 and E5-S5.
6. E4-S2 to E4-S5, E6-S3 to E6-S5.
7. E7 last.

E4-S1 sits in a later epic than its dependents. It is deliberately pulled forward because mess settings are part of the dataset configuration.

## Technical conventions (apply to every story)

These decisions are made once here so individual stories do not repeat them.

### Tooling

| Concern | Choice |
|---|---|
| Language | Python 3.12 |
| Dependency management | `uv`, with `uv.lock` committed |
| Lint and format | `ruff` (both `ruff check` and `ruff format`) |
| Type checking | `mypy` in strict mode for `src/` |
| Tests | `pytest`, with `pytest-cov` |
| Models and validation | `pydantic` v2 |
| Settings files | YAML, loaded with `PyYAML` and validated by Pydantic |
| CLI | `typer`; console script `onboardkit-gen` |
| Excel | `openpyxl` |
| Fake people and addresses | `Faker`, pinned through `uv.lock` |
| CI | GitHub Actions |

### Package layout

The README's planned layout put the generator under `data/`. We keep code in `src/` instead, and keep `data/generated/` only for output (already git-ignored). E7-S4 updates the README to match.

```
src/onboardkit/datagen/
  rng.py                 deterministic random streams
  config.py              DatasetConfig, SizeConfig, MessConfig
  presets/               clean.yaml, typical.yaml, nightmare.yaml (package data)
  truth/                 truth model and firm builder
  sources/               exporter framework, custodian, crm, book_of_business, coverage
  mess/                  engine, registry, one module per mess family
  answer_keys/           entity matches, column mappings, discrepancies, writer
  manifest.py
  pipeline.py            build -> project -> cover -> mess -> write -> answer keys
  cli.py
tests/datagen/           mirrors the package layout
docs/                    glossary, fictional firm, source catalogue, guides
data/generated/<dataset_id>/{exports,truth,manifest.json}
```

### Cross-cutting rules

- **Determinism.** No call to the global `random`, `numpy.random`, `uuid4`, `datetime.now`, or `Faker()` without an explicit seed. All randomness comes from named streams in `rng.py` (E1-S4). Iteration over sets and unordered dicts must be sorted before it influences output.
- **Fixed clock.** Every dataset has an `as_of_date` in its configuration. Nothing reads today's date.
- **Money.** `decimal.Decimal`, quantized to cents, never `float`. Written to files as text.
- **Identifiers.** Truth identifiers are stable strings: `P-00001` (person), `HH-0001` (household), `ACCT-000001` (account).
- **Pipeline order.** Build truth, project to per-source rows, apply coverage, apply mess, write files, write answer keys. Mess operates on in-memory typed rows, not on files.
- **Truth stays internal.** Truth identifiers never appear in the exports. They exist only in `truth/` files and in-memory provenance.
- **Synthetic only.** No real names lists from real clients, no real SSNs, account numbers, or addresses. Generated identifiers use obviously fictional ranges.

## Story template

Every story file uses the same sections:

1. Header table: epic, size, depends on, blocks.
2. User story.
3. Context.
4. Scope, with explicit out-of-scope items.
5. Technical design.
6. Files to create or change.
7. Acceptance criteria, as a checklist.
8. Test plan.
9. Risks and notes.

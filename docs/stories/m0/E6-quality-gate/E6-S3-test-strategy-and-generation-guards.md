# E6-S3: Test strategy and generation guards

| | |
|---|---|
| **Epic** | [E6: Automated quality gate](../../../epics/m0-foundation-epics.md#e6-automated-quality-gate) |
| **Size** | M |
| **Depends on** | E6-S1, E4-S2 |
| **Blocks** | none |

## User story

As a contributor, I want a documented testing approach and tests that keep the documentation and the generator in step, so that "data generation still behaves as documented" is checked automatically.

## Context

The epic requires checks that cover code style, correctness tests, and that data generation behaves as documented. Style and correctness come from E6-S1 and E6-S2. This story adds the shared testing conventions and the guards that compare documentation with reality: concept catalogue versus exporters, documented commands versus the real CLI, and generated reference documents versus their sources.

## Scope

**In scope**
- `docs/testing.md` describing levels and conventions.
- Shared fixtures and markers.
- Documentation-versus-code guard tests.
- A coverage threshold.

**Out of scope**
- Performance benchmarking.
- Mutation testing.

## Technical design

### Test levels

| Level | Purpose | Location | Speed |
|---|---|---|---|
| Unit | Single function or class | `tests/datagen/<package>/` | Milliseconds |
| Integration | Stages wired together, `sample` size | `tests/datagen/test_pipeline.py` etc. | Seconds |
| Guard | Docs, hygiene, determinism | `tests/guards/` and E4-S5 files | Seconds |
| Slow | `default` size, cross-process runs | marked `@pytest.mark.slow` | Tens of seconds |

CI runs everything. Developers run `pytest -m "not slow"` while iterating.

### Shared fixtures (`tests/conftest.py`)

- `sample_dataset` (session scoped): generates the `typical` preset at `sample` size, seed 42, into a temporary directory, once per test session.
- `clean_dataset`: same with the `clean` preset.
- `tmp_out_root`: a temporary output root.
- A fixture that fails any test that touches `data/generated` in the repository by mistake.

### Guard tests (`tests/guards/`)

1. **Catalogue guard.** Every column in every source profile has a concept in `concepts.yaml`, and every concept in the catalogue is used by at least one profile or listed as intentionally unused.
2. **Documentation commands.** Parse fenced code blocks tagged `bash` or `powershell` in `docs/getting-started.md` and `docs/demo-walkthrough.md`; for each `onboardkit-gen` invocation, run `--help` parsing (or the actual command with `--size sample` and a temp output) and assert it is valid. This catches renamed flags.
3. **Generated reference docs.** `docs/mess-catalogue.md` equals the regenerated output (E3-S7).
4. **Glossary links.** Relative links in `docs/` resolve to existing files and anchors.
5. **Story index and progress.** Every story file in `docs/stories/m0/` appears in the index in its README and as a row in `docs/progress/stories/m0.md`, and vice versa. Story counts in `docs/progress/epics.md` equal the number of rows per epic, and the `Done` count in each progress table matches the number of rows with status `Done`. Statuses must come from the allowed list.
6. **Version guard.** If the sample checksums changed (E4-S5), the generator version differs from the last changelog entry.

### Coverage

`pytest-cov` with `--cov-fail-under=85` for `src/onboardkit`. The threshold is stated in `pyproject.toml` and recorded in `docs/testing.md`; raise it deliberately, never lower it silently.

## Files to create or change

- `docs/testing.md`
- `tests/conftest.py`
- `tests/guards/test_catalogue.py`, `test_doc_commands.py`, `test_links.py`, `test_story_index.py`
- `pyproject.toml` (coverage threshold, markers)

## Acceptance criteria

- [ ] `docs/testing.md` explains the levels, markers, and fixtures.
- [ ] `sample_dataset` is generated once per session and reused.
- [ ] Renaming a CLI flag without updating the docs fails a guard test.
- [ ] Removing a concept that a profile uses fails a guard test.
- [ ] A broken relative link in `docs/` fails a guard test.
- [ ] The story index guard fails if a story file is added without an index entry.
- [ ] Coverage under 85 percent fails the build.

## Test plan

- Each guard is demonstrated once by temporarily breaking the thing it guards, recorded in the PR description.

## Risks and notes

- Guards that parse markdown should stay simple (fenced blocks and links only). Over-clever parsing makes them brittle.
- Do not let guards reach the network.

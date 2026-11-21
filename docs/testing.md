# Testing

How tests are organised, what runs where, and which tests keep the documentation honest. All commands run from the repository root.

## Levels

| Level | Purpose | Location | Speed |
|---|---|---|---|
| Unit | One function or class | `tests/datagen/<package>/` | Milliseconds |
| Integration | Stages wired together, `sample` size | `tests/datagen/test_pipeline.py` and similar | Seconds |
| Guard | Documentation, determinism, and repository rules stay true | `tests/guards/`, `tests/datagen/test_determinism.py`, `tests/datagen/test_standard_datasets.py`, `tests/datagen/test_mess_catalogue.py` | Seconds |
| Slow | `default` size datasets and cross-process runs | marked `@pytest.mark.slow` | Seconds to tens of seconds |

CI runs everything. While iterating, skip the slow tests:

```bash
python -m uv run pytest -m "not slow"
```

Run the whole suite with coverage the way CI does:

```bash
python -m uv run pytest --cov
```

## Markers

| Marker | Meaning |
|---|---|
| `slow` | Takes noticeably long (default-size datasets, separate processes). Declared in `pyproject.toml`; unknown markers are errors (`--strict-markers`). |

## Shared fixtures (`tests/conftest.py`)

| Fixture | Scope | What it gives you |
|---|---|---|
| `sample_dataset` | session | The `typical` preset at `sample` size, seed 42, generated once per run and reused. Do not modify its files; copy them first (`shutil.copytree`). |
| `clean_dataset` | session | The same with the `clean` preset. |
| `tmp_out_root` | function | An empty output root for tests that generate their own datasets. |
| `never_touch_repository_data` | every test (automatic) | Fails any test that creates or removes anything under `data/generated` in the repository. Write to `tmp_path` instead. |

Tests that need a different preset, size, or seed generate their own dataset into `tmp_path`.

## Guard tests

Guards compare what the documents say with what the code does. When one fails, fix whichever side is wrong.

| Guard | Fails when |
|---|---|
| `tests/guards/test_catalogue.py` | A source profile column uses a concept missing from `concepts.yaml`, or a concept is used by no profile (unless listed as intentionally unused in the test). |
| `tests/guards/test_doc_commands.py` | A fenced `bash` or `powershell` block in the README or `docs/` contains an `onboardkit-gen` command the CLI would reject, for example a renamed flag. |
| `tests/guards/test_links.py` | A relative link or heading anchor in a markdown document does not resolve. Links to websites are never followed. |
| `tests/guards/test_story_index.py` | A story file is missing from the story index or the progress table (or the reverse), a status is not in the allowed list, or the done counts and epic roll-ups in `docs/progress/` do not match the rows. |
| `tests/guards/test_versions_and_fixtures.py` | The generator version is not the newest changelog entry, checksums are missing for it, or the coverage threshold is lowered. |
| `tests/datagen/test_mess_catalogue.py` | `docs/mess-catalogue.md` differs from the output of `scripts/mess_catalogue.py`. |
| `tests/datagen/test_standard_datasets.py` | The standard datasets no longer match the recorded checksums (see `docs/datagen-changelog.md` for the procedure). |

Keep guards simple: they read fenced blocks, headings, and links only. A guard that needs clever parsing will break for the wrong reasons.

## Coverage

`pytest --cov` reports coverage for `src/onboardkit` and fails the run below **85 percent** (`fail_under` in `pyproject.toml`). Raise the number deliberately when coverage allows; never lower it silently. The guard in `tests/guards/test_versions_and_fixtures.py` checks that this page names the same number.

## Conventions

- Synthetic data only. Tests must never read or write real client data.
- Tests must not touch the network.
- Determinism: a test that generates data uses a fixed seed and asserts on content, not on the time it ran.
- Name tests after the behavior (`test_a_broken_anchor_is_reported...`), and show a guard failing once by breaking the thing it guards (see the PR that introduced it).

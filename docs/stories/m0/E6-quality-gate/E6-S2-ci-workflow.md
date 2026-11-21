# E6-S2: Continuous integration workflow

| | |
|---|---|
| **Epic** | [E6: Automated quality gate](../../../epics/m0-foundation-epics.md#e6-automated-quality-gate) |
| **Size** | S |
| **Depends on** | E6-S1 |
| **Blocks** | E6-S4, E6-S5 |

## User story

As a contributor, I want every proposed change checked automatically for style, types, and tests on Linux and Windows, so that problems are caught before review.

## Context

The project is developed on Windows but data generation must be reproducible across operating systems (E4-S5), so CI runs on both. Results must be visible on the pull request.

## Scope

**In scope**
- A GitHub Actions workflow `ci.yml`.
- Caching, concurrency, and least-privilege settings.
- Coverage artifact upload.

**Out of scope**
- Deployment, releases, scheduled jobs.
- Branch protection (E6-S5).

## Technical design

### Triggers

`pull_request` (all branches targeting `main`) and `push` to `main`.

### Jobs

| Job | Runs on | Steps |
|---|---|---|
| `lint` | ubuntu-latest | checkout, setup uv, `uv sync --locked`, `ruff check .`, `ruff format --check .` |
| `typecheck` | ubuntu-latest | same setup, `mypy` |
| `test` | matrix: ubuntu-latest, windows-latest | same setup, `pytest --cov --cov-report=xml`, upload coverage on Linux |

Job ids and display names are stable (`lint`, `typecheck`, `test (ubuntu-latest)`, `test (windows-latest)`) because branch protection (E6-S5) refers to them.

### Settings

- `permissions: contents: read` at workflow level.
- `concurrency: group: ci-${{ github.ref }}`, `cancel-in-progress: true`.
- `timeout-minutes: 15` per job.
- `astral-sh/setup-uv` with caching enabled, Python version from `.python-version`.
- Third-party actions pinned to a full commit SHA with a comment naming the version; Dependabot (E6-S4) keeps them current.
- Environment: `PYTHONHASHSEED` unset by default; determinism tests set it explicitly.
- Set `UV_LOCKED=1` so a stale lockfile fails the build.

### Output visibility

Failed steps show in the PR checks list. Coverage summary written to the job summary via `$GITHUB_STEP_SUMMARY`.

## Files to create or change

- `.github/workflows/ci.yml`

## Acceptance criteria

- [x] Opening a pull request runs all four checks.
- [x] A deliberately failing lint, type error, and failing test each turn the right check red (verified once on a throwaway branch).
- [x] A good change goes green with no manual steps.
- [x] Windows and Linux test jobs both run.
- [x] A change that edits `pyproject.toml` without updating `uv.lock` fails.
- [x] Workflow permissions are read-only for contents.
- [x] A second push to the same pull request cancels the earlier run.

## Test plan

- Throwaway-branch experiments listed above, with links recorded in the PR description.
- Re-run on both operating systems to confirm cache behavior.

## Risks and notes

- Windows jobs are slower; keep slow tests behind the `slow` marker and decide which run in CI as the suite grows.
- Pin actions by SHA to limit supply chain risk; unpinned tags can change underneath you.
- Cache hit behavior on a second run was not confirmed from the logs; caching is enabled with `uv.lock` as the key. Re-check when runs become slow.
- Verification used a throwaway pull request (closed, branch deleted); results are recorded in the E6-S2 pull request description.

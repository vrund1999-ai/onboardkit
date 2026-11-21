# E6-S4: Repository hygiene guards

| | |
|---|---|
| **Epic** | [E6: Automated quality gate](../../../m0-foundation-epics.md#e6-automated-quality-gate) |
| **Size** | S |
| **Depends on** | E6-S2, E6-S3 (uses the `sample_dataset` fixture) |
| **Blocks** | none |

## User story

As a contributor, I want automatic protection against committing generated data, secrets, or anything that looks like real personal data, so that the "synthetic data only" promise cannot be broken by accident.

## Context

The README states that no real client or firm data is used anywhere and that generated files are git-ignored. Those are promises that nothing yet enforces. The risk is two-sided: someone commits `data/generated/` output, or a future contributor pastes in a real export while experimenting.

## Scope

**In scope**
- Tests that fail on tracked generated data and on suspicious data patterns.
- Secret scanning in CI.
- Dependency and action update automation.
- A size limit on tracked files.

**Out of scope**
- Full security review of dependencies.
- Pre-commit hooks (optional later; CI is the enforcement point).

## Technical design

### Tracked-file checks (`tests/guards/test_repo_hygiene.py`)

Use `git ls-files` to list tracked files (skip the test if not in a git checkout).

1. **No generated data tracked.** Nothing tracked under `data/generated/` or `output/`.
2. **Gitignore intact.** `.gitignore` still contains the required entries (`data/generated/`, `.env`, `.env.*`, `output/`).
3. **File size.** No tracked file larger than 1 MB, except an allow-list in the test (for example `uv.lock`).
4. **Forbidden extensions.** No tracked `.xlsx`, `.xls`, or `.csv` outside `tests/**/fixtures/` or `tests/**/expected/`, with an explicit allow-list.
5. **No environment files.** No tracked `.env` (only `.env.example`).

### Synthetic-data check (`tests/guards/test_synthetic_only.py`)

Scan every file in the `sample_dataset` fixture:

- Emails use only `example.com` or `example.test`.
- Phone numbers match the fictional `555-01XX` pattern.
- No value matches a nine-digit tax identifier pattern (`\d{3}-?\d{2}-?\d{4}`); only last four digits exist.
- Account numbers all start with the documented fictional prefix.
- Fictional firm names do not match a small deny list of real firm names (kept in a test data file, easy to extend).

### CI additions

- `gitleaks/gitleaks-action` (pinned by SHA) on pull requests, scanning the diff. Add a minimal `.gitleaks.toml` allowing the fictional patterns used in tests.
- `.github/dependabot.yml` for two ecosystems: `uv` (weekly) and `github-actions` (weekly), with grouped minor and patch updates.

## Files to create or change

- `tests/guards/test_repo_hygiene.py`, `tests/guards/test_synthetic_only.py`
- `tests/guards/data/real_firm_denylist.txt`
- `.github/workflows/ci.yml` (add secrets scan job)
- `.github/dependabot.yml`, `.gitleaks.toml`

## Acceptance criteria

- [ ] Staging a file under `data/generated/` makes the hygiene test fail (verified once, then reverted).
- [ ] Adding a 2 MB file makes the size test fail.
- [ ] A real-looking email, phone, or nine-digit tax id in generated output makes the synthetic test fail.
- [ ] The secrets scan runs on pull requests and passes on the current repository.
- [ ] Dependabot opens update pull requests for `uv` and `github-actions`.
- [ ] The allow-lists are short, commented, and live in the tests that use them.

## Test plan

- Temporary negative experiments for each rule, recorded in the PR.
- Run the guards on Windows and Linux.

## Risks and notes

- The deny list is a courtesy check, not a guarantee. The real protection is that the generator only produces values from controlled ranges.
- Keep allow-lists tight; every entry should have a reason.

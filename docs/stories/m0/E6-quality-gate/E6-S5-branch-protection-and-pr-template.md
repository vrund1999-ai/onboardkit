# E6-S5: Branch protection and PR template

| | |
|---|---|
| **Epic** | [E6: Automated quality gate](../../../epics/m0-foundation-epics.md#e6-automated-quality-gate) |
| **Size** | S |
| **Depends on** | E6-S2, E6-S4 (the `secrets-scan` check must exist before it can be required) |
| **Blocks** | E7-S3 |

## User story

As a maintainer, I want failing checks to block merging and every pull request to follow a short template, so that "a failing check blocks acceptance of a change" is true in practice.

## Context

CI results only matter if they gate merging. That depends on repository settings, which are not stored in the repo, so this story pairs a documented, repeatable settings procedure with files that live in the repo. The project currently merges its own pull requests; protection should still require checks to pass.

## Scope

**In scope**
- Branch protection (or a ruleset) on `main`.
- A pull request template.
- A short settings document with the exact commands used, so it can be reapplied.

**Out of scope**
- Required human reviewers (single maintainer for now; revisit when others contribute).
- Issue templates.

## Technical design

### Settings for `main`

| Setting | Value |
|---|---|
| Require a pull request before merging | on |
| Required approving reviews | 0 (single maintainer), documented as a future change |
| Require status checks to pass | `lint`, `typecheck`, `test (ubuntu-latest)`, `test (windows-latest)`, `secrets-scan` |
| Require branches to be up to date | on |
| Allow force pushes | off |
| Allow deletions | off |
| Require linear history | off (merge commits are used today) |
| Do not allow bypassing | off for administrators initially, with a note to turn on once stable |

Applied with the GitHub CLI so it is reproducible. The commands go in `docs/repo-settings.md`, for example a `gh api` call to the branch protection endpoint with the required contexts list. Check names must match the job names from E6-S2 exactly.

### Pull request template (`.github/pull_request_template.md`)

Sections:

1. **Summary.** What and why, in a few sentences.
2. **Related story.** Link to a story file, for example `docs/stories/m0/E2-source-exports/E2-S2-custodian-export.md`.
3. **Checklist.**
   - Acceptance criteria in the story are met.
   - Tests added or updated.
   - If generated output changed: generator version bumped and changelog updated.
   - Docs updated, including the glossary or catalogue if terms or columns changed.
   - No real data included.
4. **E2E Local Testing Evidence.** Required section, as defined in the project `CLAUDE.md`: real commands, requests, logs, or screenshots mapped to the story's acceptance criteria. Unit test output does not count.
5. **How tested.** Short note on automated tests added or updated.

### Verification

After applying, open a pull request with a deliberate failing check and confirm the merge button is blocked, then close it.

## Files to create or change

- `.github/pull_request_template.md`
- `docs/repo-settings.md` (settings table and the commands)

## Acceptance criteria

- [x] A pull request with a failing required check cannot be merged.
- [x] A pull request with all checks passing can be merged.
- [x] Direct pushes to `main` are rejected.
- [x] Force pushes and branch deletion on `main` are disabled.
- [x] The template appears automatically on new pull requests.
- [x] `docs/repo-settings.md` lets someone else reapply the settings exactly.

## Test plan

- The deliberate-failure experiment above, with a screenshot or log noted in the PR.
- Re-run the documented commands against a scratch repository to confirm they work.

## Risks and notes

- This is a repository setting change that affects everyone with access. Confirm with the maintainer before applying, and apply it only after CI is stable, or merges will block on flaky checks.
- Required check names are strings; renaming a CI job silently disables its protection until the settings are updated. The CI story notes that job names are stable for this reason.

## Notes

- Applied on 2026-11-21 with the commands in `docs/repo-settings.md`, after the maintainer approved. Read back: required checks `lint`, `typecheck`, `test (ubuntu-latest)`, `test (windows-latest)`, `secrets scan`; strict (up to date) on; force pushes off; deletions off; administrators not enforced.
- Verified with a deliberately failing pull request (#42, closed): three required checks failed and the merge state was `BLOCKED`; `gh pr merge` refused. All-green pull requests (#35 to #41) merged normally. Force pushes and deletion are covered by the read-back of the settings; I did not attempt them against `main`.
- Because administrators are not enforced, the repository owner can still bypass protection (`--admin`, or a direct push). So "direct pushes to `main` are rejected" holds for everyone else, not for the owner; turn on `enforce_admins` once stable.
- The secrets job is named `secrets scan` (with a space) in CI, and that is the name used in the required check list.


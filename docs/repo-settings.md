# Repository settings

Settings that live in GitHub rather than in the repository, with the exact commands to apply them. Run them as a repository admin with the GitHub CLI (`gh auth login` first). Replace `OWNER/REPO` with the repository.

Not applied automatically: they affect everyone with access, so the maintainer applies them once CI is stable.

## Branch protection for `main`

| Setting | Value |
|---|---|
| Require a pull request before merging | on |
| Required approving reviews | 0 (single maintainer; revisit when others contribute) |
| Required status checks | `lint`, `typecheck`, `test (ubuntu-latest)`, `test (windows-latest)`, `secrets scan` |
| Require branches to be up to date | on |
| Allow force pushes | off |
| Allow deletions | off |
| Require linear history | off (merge commits are used) |
| Enforce for administrators | off for now; turn on once stable |

The check names must match the job names in `.github/workflows/ci.yml` exactly. Renaming a job silently disables its protection until this table and the command below are updated. The `secrets scan` job only runs on pull requests, which is when it is required.

### Apply

```bash
gh api -X PUT repos/OWNER/REPO/branches/main/protection --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["lint", "typecheck", "test (ubuntu-latest)", "test (windows-latest)", "secrets scan"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {"required_approving_review_count": 0},
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": false
}
JSON
```

### Check

```bash
gh api repos/OWNER/REPO/branches/main/protection --jq '{checks: .required_status_checks.contexts, strict: .required_status_checks.strict, force: .allow_force_pushes.enabled, delete: .allow_deletions.enabled}'
```

### Remove

```bash
gh api -X DELETE repos/OWNER/REPO/branches/main/protection
```

### Verify the protection works

1. Open a pull request with a deliberately failing test; the merge button must be blocked.
2. Close it without merging.
3. `git push origin HEAD:main` from a feature branch must be rejected.

## Pull request template

`.github/pull_request_template.md` is applied automatically to new pull requests. It includes the required **E2E Local Testing Evidence** section.

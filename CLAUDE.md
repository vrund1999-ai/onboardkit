# onboardkit

Toolkit for onboarding an advisor firm's messy CSV/Excel exports into one clean, reconciled data model, with AI-assisted mapping, human review, and client-ready Excel output. All data is synthetic. See [README.md](README.md).

## Where things are

| What | Where |
|---|---|
| Vision and capabilities by milestone (M0 to M6) | [ROADMAP.md](ROADMAP.md) |
| Epics | [docs/epics/](docs/epics/) |
| Stories (one file each, with technical detail) | [docs/stories/](docs/stories/), indexed in each milestone's `README.md` |
| **Progress at every level** | [docs/progress/](docs/progress/), start with its [README](docs/progress/README.md) |

## Keep progress up to date (required)

Progress is tracked at three levels: **capability/milestone**, **epic**, and **story**. Status lives only in `docs/progress/`; planning documents never carry a status.

Whenever you start, finish, block, or drop work, update the progress files **in the same change**:

1. Set the story's status in `docs/progress/stories/mN.md` (and its PR number when there is one).
2. Recompute the epic's row in `docs/progress/epics.md` (status and `Stories done` count).
3. Recompute the affected capability and milestone rows in `docs/progress/capabilities.md`.
4. Update the `Last updated` date in each file touched, and the `Overall` count in `stories/mN.md`.

Rules:

- Use only these statuses: `Not started`, `In progress`, `Blocked`, `Done`, `Dropped`. The roll-up rules are in `docs/progress/README.md`.
- Mark a story `Done` only when every acceptance criterion in its story file is met and the work is merged to `main`. Until merged, it is `In progress`.
- Never delete rows. Put the reason for `Blocked` or `Dropped` in Notes.
- When adding a story, epic, or capability, add it to the planning document **and** the progress files (see "Adding things" in the progress README).
- If you finish work and did not touch `docs/progress/`, say so and why in the PR description.
- After a task that changes status, mention in your reply which progress rows you updated.

## Documentation conventions

- `ROADMAP.md`, epics, and stories describe capabilities and outcomes first. Technical detail belongs in story files only.
- Do not change a story's scope silently: edit the story file, and note the change in the PR.
- When moving or renaming a document, fix every relative link to it (search the repo for the old name).
- Story ids look like `E2-S2`; use them in branch names, commit messages, and PR descriptions where a story is involved.

## Pull requests: E2E Local Testing Evidence (required)

Every PR you open must contain a section titled **E2E Local Testing Evidence**. It shows that the story was implemented as specified, by running the real thing locally. Unit tests do not count as this evidence: they run in CI anyway. Do not paste pytest output as the evidence.

What to include depends on the change:

| Change type | Acceptable evidence |
|---|---|
| CLI or generator (`onboardkit-gen`, pipeline) | The exact commands run and their real output, plus excerpts of the files produced (first rows of an export, a few lines of an answer key, the manifest) |
| Backend API (FastAPI, later milestones) | The REST calls made (for example `curl` commands) and the actual responses, including status codes and at least one error case |
| UI (Streamlit review screen) | Screenshots of the relevant states, with a one-line caption saying what each shows |
| Excel or other file output | A screenshot or a described cell-level excerpt of the opened file |
| Logging, audit trail, or error handling | Log output captured during the run showing the behavior, including a failure path |
| Reproducibility or determinism | Two runs and a hash or diff comparison showing the result |
| Docs-only or config-only | State that no runtime behavior changed, and show the check that applies (for example the link check output, or the CI-equivalent command run locally) |

Rules:

- Map the evidence to the story's acceptance criteria. For each criterion, say what evidence demonstrates it, or say it is covered only by unit tests and why.
- Run it for real, on the branch being submitted, after your final code change. Never fabricate, paraphrase, or hand-edit output. If something could not be run locally, say so and why rather than implying it was.
- Include the environment used (OS, Python version, command working directory) and the dataset id or seed when data was generated.
- Show a negative case where the story defines one (invalid input, unknown preset, tampered file, expected exit code).
- Keep it readable: trim long output to the relevant lines and say where it was trimmed. Put images in the PR itself, not in the repository.
- Evidence involves synthetic data only. Do not include real data, secrets, or absolute paths from the user's machine beyond what is needed.
- If a PR touches several stories, give evidence per story.

Suggested layout inside the PR description:

```
## E2E Local Testing Evidence

**Environment:** Windows 11, Python 3.12, run from repo root on branch <branch>

### <Story id>: <criterion or behavior>
Command / request:
    <command or curl>
Output / response:
    <trimmed real output>
Shows: <one line linking it to the acceptance criterion>
```

## Project rules

- Synthetic data only. Never add real client, firm, or personal data anywhere in the repo.
- Branch names: `docs/<topic>`, `feat/<story-id>-<slug>`, `fix/<slug>`. Open pull requests into `main`.
- Generated datasets go in `data/generated/` and are git-ignored; do not commit them.
- Technical conventions for M0 (tooling, package layout, determinism rules) are in [docs/stories/m0/README.md](docs/stories/m0/README.md).

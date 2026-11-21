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

## Project rules

- Synthetic data only. Never add real client, firm, or personal data anywhere in the repo.
- Branch names: `docs/<topic>`, `feat/<story-id>-<slug>`, `fix/<slug>`. Open pull requests into `main`.
- Generated datasets go in `data/generated/` and are git-ignored; do not commit them.
- Technical conventions for M0 (tooling, package layout, determinism rules) are in [docs/stories/m0/README.md](docs/stories/m0/README.md).

# E7-S4: README and roadmap refresh, clean-room test

| | |
|---|---|
| **Epic** | [E7: Contributor experience](../../../epics/m0-foundation-epics.md#e7-contributor-experience) |
| **Size** | S |
| **Depends on** | E7-S1, E7-S2, E7-S3 (and all other M0 stories) |
| **Blocks** | none |

## User story

As a newcomer, I want the README and roadmap to describe what exists, and I want proof that the documented path really works on a fresh machine, so that M0 can be declared delivered.

## Context

The README still says "early scaffolding" and describes the generator under `data/`. The roadmap lists M0 as planned. This is the closing story: it brings the top-level documents in line with reality and runs the final check of the epic's promise, that a newcomer can get started from the docs alone.

## Scope

**In scope**
- README updates.
- Roadmap and epic document status updates.
- A clean-room run and a recorded exit-criteria checklist.

**Out of scope**
- Any planning for M1 beyond a link.

## Technical design

### README changes

- Replace the status note with a statement of what exists (a reproducible synthetic data generator with ground truth and a quality gate) and what is still planned.
- Add a **Quick start** section: install `uv`, clone, `uv sync`, `uv run onboardkit-gen generate --preset typical --size sample`.
- Update **Repository layout** to the real one (`src/onboardkit/datagen/`, `tests/`, `docs/`, generated output under `data/generated/`).
- Link to the roadmap, glossary, fictional firm profile, getting started guide, walkthrough, contributing guide, and architecture.
- Mark `sections marked planned` correctly: remove the marker from what is now built.
- Add a license decision if one has been made; otherwise keep "To be added".

### Roadmap and epic documents

- `ROADMAP.md`: mark M0 as delivered with the date and a link to the epic document; note any scope changes made during delivery.
- `docs/epics/m0-foundation-epics.md`: add a status line per epic and tick the exit criteria.
- `docs/stories/m0/README.md`: add a status column to the story index.

### Clean-room test

Perform on a machine or environment that has never had the project (for example Windows Sandbox, a fresh virtual machine, or a clean container):

1. Install only Git and `uv`.
2. Clone the repository.
3. Follow `docs/getting-started.md` literally, in order, without improvising.
4. Follow `docs/demo-walkthrough.md` up to the "turn the dial" section.
5. Record elapsed time, every deviation from the text, and every question you had to answer yourself.
6. Fix the documentation for each gap, then repeat steps 3 to 5 on a fresh environment until a run passes with no deviations.

Record the result in `docs/stories/m0/clean-room-log.md`: environment, date, generator version, time taken, issues, and outcome.

### Exit criteria checklist

For each exit criterion in the epics document, record the evidence in the log: command or test name and result.

## Files to create or change

- `README.md`, `ROADMAP.md`, `docs/epics/m0-foundation-epics.md`, `docs/stories/m0/README.md`
- `docs/stories/m0/clean-room-log.md`

## Acceptance criteria

- [x] README no longer describes the project as scaffolding only.
- [x] README layout matches the real layout and all of its links resolve.
- [ ] Roadmap shows M0 as delivered and links the epics document.
- [ ] A clean-room run follows the guide with no deviations and finishes within 30 minutes.
- [x] The log lists evidence for every M0 exit criterion.
- [x] Link guard and story index guard pass.

## Test plan

- The clean-room procedure above; repeated until clean.
- CI green on the pull request.

## Risks and notes

- Do the clean-room run last, after the other stories merge, otherwise it tests a moving target.
- Someone other than the author running it gives a more honest result; if unavailable, follow the text exactly rather than from memory.

## Notes

- **Not finished.** Two criteria stay open: "Roadmap shows M0 as delivered" and "A clean-room run ... with no deviations". M0 is not declared delivered because branch protection (E6-S5) is not applied and the clean-room run has only been done by the author on the author's machine, not on a fresh machine by someone else. `docs/stories/m0/clean-room-log.md` records Run 1 and what remains.
- **Scope change.** The story asks for status lines in the roadmap, the epics document, and a status column in the story index. The project rules (`CLAUDE.md`) keep status only in `docs/progress/`, so none were added; the README now points to the progress files instead. The roadmap needs no edit until M0 is delivered, because it carries no status.
- README links to the getting started guide, walkthrough, contributing guide, architecture, testing, glossary, fictional firm profile and source systems; the link guard checks them.


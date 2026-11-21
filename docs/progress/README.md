# Progress tracking

How onboardkit tracks what is done. Progress is tracked at three levels, each with its own file.

| Level | What it is | Defined in | Tracked in |
|---|---|---|---|
| Capability (and milestone) | Something the product can do, grouped into milestones M0 to M6 | [ROADMAP.md](../../ROADMAP.md) | [capabilities.md](capabilities.md) |
| Epic | A body of work that delivers one or more capabilities | [docs/epics/](../epics/) | [epics.md](epics.md) |
| Story | A unit of implementation work with acceptance criteria | [docs/stories/](../stories/) | [stories/](stories/) (one file per milestone, for example [stories/m0.md](stories/m0.md)) |

## Single source of truth

Each level's status lives **only** in its progress file. Roadmap, epic, and story documents describe *what* is planned and never carry a status, so they do not go stale. Higher levels are rolled up from lower ones by hand, in the same change.

```
story status  ->  epic status  ->  capability status  ->  milestone status
```

## Status values

| Status | Meaning |
|---|---|
| `Not started` | No work has begun |
| `In progress` | At least one piece of work is under way or merged, but the acceptance criteria are not all met |
| `Blocked` | Cannot proceed; say why and what unblocks it in Notes |
| `Done` | All acceptance criteria met, and the work is merged to `main` |
| `Dropped` | Deliberately not doing it; say why in Notes (the item stays listed) |

Never delete a row. Dropped and replaced work stays visible.

## Roll-up rules

- **Epic** is `Done` when all its stories are `Done` or `Dropped` (with at least one `Done`). It is `In progress` when any story is `In progress` or `Done` but not all are. Otherwise it is `Not started`. If every unfinished story is `Blocked`, the epic is `Blocked`.
- **Capability** follows the same rule over the epics that deliver it. A capability delivered by several epics is `Done` only when all of them are.
- **Milestone** is `Done` when all its capabilities are `Done`, and follows the same rule otherwise.
- The count columns (`Stories done`, `Capabilities done`) count only `Done` items, not `Dropped`.

## How to update

Update progress **in the same pull request** as the work, not afterwards.

1. **Starting a story.** Set the story to `In progress` in `stories/mN.md`. Recompute the epic row in `epics.md`, and the capability and milestone rows in `capabilities.md`.
2. **Finishing a story.** Check every acceptance criterion in the story file. Set the story to `Done`, add the PR number in the PR column, and recompute the counts and the rows above it.
3. **Blocked or dropped.** Set the status and write the reason in Notes.
4. **Always** update the `Last updated` date at the top of each file you touched, and the `Overall` count in `stories/mN.md`.
5. If a pull request links to a story, the PR description should name the story id (for example `E2-S2`).

A story that merges across several pull requests stays `In progress` until the last one; list each PR in the PR column.

## Adding things

- **New story:** add the story file, add it to the story index in `docs/stories/mN/README.md`, add a row in `stories/mN.md`, and update the epic's story count in `epics.md`.
- **New epic or milestone breakdown:** add `docs/epics/mN-*.md`, `docs/stories/mN/`, and `stories/mN.md`; replace the "not broken down yet" text in `capabilities.md` and `epics.md`.
- **New or changed capability:** change `ROADMAP.md` first, then the matching row in `capabilities.md`.
- **Renaming or moving a document:** fix every link to it, including those in this folder.

## Files

```
docs/progress/
  README.md          this file
  capabilities.md    milestones and capabilities (M0 to M6)
  epics.md           epics, with story counts
  stories/
    m0.md            every M0 story
```

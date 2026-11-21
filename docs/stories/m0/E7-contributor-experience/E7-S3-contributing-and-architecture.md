# E7-S3: Contributing guide and architecture overview

| | |
|---|---|
| **Epic** | [E7: Contributor experience](../../../epics/m0-foundation-epics.md#e7-contributor-experience) |
| **Size** | M |
| **Depends on** | E6-S5 |
| **Blocks** | E7-S4 |

## User story

As a contributor, I want a guide to how the project is organised and how to propose a change, so that I can add a feature without reverse engineering the conventions.

## Context

M0 sets conventions that every later milestone inherits: determinism rules, concept-first columns, event-logged mess, truth kept separate. They are spread across story files today. Contributors need one short place that states them and one that explains how the pieces fit together.

## Scope

**In scope**
- `CONTRIBUTING.md` at the repo root.
- `docs/architecture.md`.
- Recipes for the two most common extensions.

**Out of scope**
- A code of conduct and governance (revisit if the project gains contributors).

## Technical design

### `CONTRIBUTING.md`

1. **Workflow.** Pick a story from `docs/stories/`, create a branch, open a pull request into `main`.
2. **Branch names.** `docs/<topic>`, `feat/<story-id>-<slug>`, `fix/<slug>`, matching the existing history.
3. **Commit messages.** Short imperative subject, body when needed; one logical change per commit.
4. **Pull requests.** Use the template; link the story; wait for green checks.
5. **Local checks.** The four commands from the getting started guide.
6. **Rules of the road.**
   - Determinism: named random streams only, no clock, no unordered iteration.
   - Money is `Decimal`.
   - Synthetic data only; never paste real data anywhere in the repo.
   - Generated output changes require a generator version bump and changelog entry.
   - New columns need a concept first (catalogue), then a profile entry.
   - Truth never leaks into exports.
7. **How to add a mess type.** Steps: define the class with `name`, `touches`, `max_rate`, subtypes; register it; emit events for every change; add tests (unit, isolation, coverage); add to presets; regenerate the mess catalogue; bump the version.
8. **How to add a source column.** Steps: concept in catalogue, profile column and formatter, projection, answer key picks it up automatically, update the glossary if a new term appears, tests, checksum update.
9. **Documentation.** Where docs live and the link guard.

### `docs/architecture.md`

- A plain-text diagram of the pipeline:

```
config -> truth firm -> per-source rows -> coverage -> mess -> exports
                                    \                      \
                                     +---- events ----------+--> answer keys (truth/)
```

- Module map: one line per package under `src/onboardkit/datagen/`.
- Data flow description with the in-memory types (`TruthFirm`, `SourceRow`, `MessEvent`, `CoverageEvent`).
- Determinism design: named streams, fixed clock, deterministic Excel.
- Truth versus exports boundary and why it exists.
- Extension points and how later milestones (M1 to M6) will connect: ingestion consumes `exports/` only; evaluation consumes `truth/`.
- Decisions list with one-line rationales (why `src/` layout rather than `data/`, why YAML plus Pydantic, why Typer).

## Files to create or change

- `CONTRIBUTING.md`
- `docs/architecture.md`

## Acceptance criteria

- [x] `CONTRIBUTING.md` covers all nine sections.
- [x] A contributor can follow the "add a mess type" recipe and reach a passing build; verified by walking through it once on a throwaway branch.
- [x] `docs/architecture.md` contains the pipeline diagram and module map, and the module map matches the real package list (guard test compares directory names).
- [x] Links between the guides, glossary, stories, and README resolve (link guard).
- [x] The branch naming rules match the pull request template.

## Test plan

- Throwaway-branch walkthrough of both recipes, noting any missing steps.
- Link and module-map guard tests.

## Risks and notes

- Keep the architecture document to what exists, not what is planned; the roadmap covers plans.
- Update both documents in any pull request that changes structure.

## Notes

- Dependency: this story depends on E6-S5, which is only partly done (template and settings guide merged; branch protection not yet applied). The guides only link to `docs/repo-settings.md`, so nothing here relies on protection being active.
- The "add a mess type" recipe was walked through once on a throwaway branch with a trivial type (CRM first names in capitals). It reached a passing build only after five fixes to the recipe, now included: the `clean` preset must keep the type disabled; `test_hash_is_pinned` and `test_preset_values_match_the_story` must be updated deliberately; the changelog, version and checksums; the regenerated catalogue; and the sample dataset id in the demo walkthrough. The "add a source column" recipe was written from the code but not walked through; treat it as unverified.
- The module-map guard compares the table in `docs/architecture.md` with the folders and modules in `src/onboardkit/datagen/`. `CONTRIBUTING.md` is now among the documents scanned by the link, command and anchor guards.
- The pull request template gained a checklist line pointing at the branch naming rules.


# E7-S1: Getting started guide

| | |
|---|---|
| **Epic** | [E7: Contributor experience](../../../m0-foundation-epics.md#e7-contributor-experience) |
| **Size** | S |
| **Depends on** | E6-S1 (and E4-S4 for the generate step) |
| **Blocks** | E7-S4 |

## User story

As a newcomer, I want setup instructions that work from a clean machine, so that I can install the project, run the checks, and generate a dataset without asking for help.

## Context

The M0 exit criterion is that someone who has not seen the project can follow the docs alone. The primary development machine is Windows with PowerShell, so instructions must work there first, with Linux and macOS equivalents. Commands in this guide are verified automatically by a guard test (E6-S3), so they cannot rot.

## Scope

**In scope**
- `docs/getting-started.md`.
- A troubleshooting section for the problems most likely on a clean machine.

**Out of scope**
- Project structure and contribution rules (E7-S3).
- The data tour (E7-S2).

## Technical design

The guide has these sections:

1. **Prerequisites.** Git, `uv` (with the one-line install for each platform), nothing else; `uv` fetches Python 3.12 itself. State the supported platforms: Windows 10 or 11, Linux, macOS.
2. **Get the code.** `git clone`, change into the directory.
3. **Install.** `uv sync`, and what it creates.
4. **Check the install.** The four commands: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest`, with the expected final lines of output.
5. **Generate your first dataset.** `uv run onboardkit-gen generate --preset typical --size sample --seed 42`, the expected output (dataset id and counts), and where files land.
6. **Look at the result.** A short listing of `exports/` and a pointer to the walkthrough (E7-S2).
7. **Troubleshooting.**
   - `uv` not found after install: restart the shell.
   - Execution policy or path issues on PowerShell.
   - Long path errors on Windows and enabling long paths.
   - Dataset already exists: use `--overwrite`.
   - Test failures about checksums: likely a different dependency version; run `uv sync --locked`.
8. **Next steps.** Links to the walkthrough, contributing guide, and roadmap.

Every command block is tagged `powershell` or `bash` so the guard test can find it. Provide both forms only where they differ.

## Files to create or change

- `docs/getting-started.md`

## Acceptance criteria

- [ ] Following the guide on a machine with only Git and `uv` installed ends with a generated sample dataset and passing checks.
- [ ] Every command in the guide appears in a tagged code block.
- [ ] The guard test (E6-S3) validates each `onboardkit-gen` command.
- [ ] Expected output shown matches reality for the current generator version.
- [ ] Windows, Linux, and macOS differences are called out where they exist.
- [ ] No step requires editing a file or setting an environment variable by hand.

## Test plan

- Verified by the clean-room test in E7-S4 on Windows.
- Guard test run in CI.

## Risks and notes

- Keep expected output short (key lines, not full logs), or it goes stale quickly.
- If the install story changes (new tool, new Python version), update this guide in the same pull request.

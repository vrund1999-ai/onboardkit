# M0 clean-room log

Evidence that the documented path works from a fresh checkout, and that each M0 exit criterion has evidence. Update this file whenever the run is repeated.

## Run 1

| | |
|---|---|
| Date | 2026-11-21 |
| Generator version | 0.2.0 |
| Environment | Windows 11, Git Bash, fresh `git clone` of the branch, fresh `.venv`, empty uv cache (all packages downloaded) |
| Followed | [getting-started.md](../../getting-started.md) in order, then [demo-walkthrough.md](../../demo-walkthrough.md) sections 1 to 4 (generate, tour, find the mess, truth) |
| Time taken | 3 minutes 45 seconds (225 s), of which the full test run was 2 minutes 21 seconds |
| Result | Every command exited 0; 649 tests passed; `verify` and `check` reported ok; the walkthrough's `Hines` search found both rows |

### Deviations and issues

1. `uv` was not on this shell's PATH, so commands were run as `python -m uv ...`. This is the first troubleshooting row of the getting started guide ("`uv` is not found after installing"), but the machine already had Python, so it is not a clean-room condition.

### Limits of this run

- It was run by the author, on the author's machine, so it is not an independent or truly clean machine: Python and other tools were already installed, so "only Git and uv" is not demonstrated. The story asks for a fresh environment (for example Windows Sandbox or a virtual machine) and, ideally, a different person.
- Linux and macOS were not run locally; CI runs the tests on Ubuntu and Windows.
- The exit criterion "A newcomer can get started from the docs alone" is therefore **not yet closed**. Repeat on a clean machine and record it as Run 2.

## M0 exit criteria evidence

The criteria are in the [M0 epics document](../../epics/m0-foundation-epics.md#milestone-exit-criteria).

| Exit criterion | Evidence | Result |
|---|---|---|
| A standard demo dataset can be regenerated in one step and looks like a real firm's messy exports | `uv run onboardkit-gen generate --preset typical --size default --seed 42`; `tests/datagen/test_standard_datasets.py` compares the recorded checksums; [demo walkthrough](../../demo-walkthrough.md) shows the mess | Pass (Run 1: dataset id `typical-sample-s42-937ab0dd` for the sample) |
| The mess can be turned up or down, and each kind of mess is visible when enabled | `--preset clean/typical/nightmare` and `--mess names=heavy`; `tests/datagen/test_mess_coverage.py` (every subtype appears at `nightmare`) and `tests/datagen/test_mess_isolation.py`; [mess catalogue](../../mess-catalogue.md) | Pass |
| Ground truth exists for every dataset and covers mapping, matching, and reconciliation | `truth/` has 12 files (`column_mappings.csv`, `entity_matches.csv`, `discrepancies.csv` and others); `uv run onboardkit-gen check <dataset>` printed `ok: truth is complete, consistent, and separate from the exports` | Pass |
| Automated checks guard every change | CI runs lint, typecheck, tests on Ubuntu and Windows, and a secrets scan on pull requests; the guards in `tests/guards/`; coverage threshold 85 percent | Pass for the checks. Branch protection that makes them *block* merging is documented in [repo-settings.md](../../repo-settings.md) but **not yet applied** (E6-S5) |
| A newcomer can get started from the docs alone | Run 1 above | **Open**: needs an independent clean-machine run |

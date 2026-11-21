# Getting started

From a clean machine to a generated sample dataset and passing checks. All data is synthetic.

## Prerequisites

- **Git**
- **uv**, the Python package manager. It downloads Python 3.12 itself, so you do not install Python separately.

Supported platforms: Windows 10 or 11, Linux, macOS.

Install uv:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen your terminal afterwards so `uv` is on the path.

## Get the code

```bash
git clone https://github.com/vrund1999-ai/onboardkit.git
cd onboardkit
```

## Install

```bash
uv sync
```

This creates a `.venv` folder with Python 3.12 and every dependency at the locked versions. Nothing else needs setting up and no environment variables are used.

## Check the install

Run the four checks. Each should finish without errors:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Expected last lines (counts grow as the project does):

```
All checks passed!
94 files already formatted
Success: no issues found in 42 source files
637 passed in 300s
```

The full test run takes a few minutes. For a quicker loop, skip the slow tests with `uv run pytest -m "not slow"`. See [testing](testing.md).

## Generate your first dataset

```bash
uv run onboardkit-gen generate --preset typical --size sample --seed 42
```

Expected output:

```
dataset: typical-sample-s42-937ab0dd
path: data/generated/typical-sample-s42-937ab0dd
households: 15
persons: 27
accounts: 43
events.coverage: 19
events.mess: 90
rows.custodian: 43
rows.crm: 70
rows.book_of_business: 32
```

The same preset, size and seed always produce the same dataset id, so yours should match. Files land in `data/generated/`, which git ignores.

## Look at the result

```
data/generated/typical-sample-s42-937ab0dd/
  manifest.json                 every file with its checksum
  exports/
    custodian/custodian_accounts.csv
    crm/crm_contacts.csv, crm_linked_accounts.csv
    book_of_business/book_of_business.xlsx
  truth/                        the answer key (what the exports should reconcile to)
```

Check the dataset is intact, then see its summary:

```bash
uv run onboardkit-gen verify data/generated/typical-sample-s42-937ab0dd
uv run onboardkit-gen show data/generated/typical-sample-s42-937ab0dd
```

List the available presets with:

```bash
uv run onboardkit-gen presets
```

The `exports/` folder is what an onboarding tool would receive. `truth/` is only for checking answers and is never an input.

## Troubleshooting

| Problem | Fix |
|---|---|
| `uv` is not found after installing | Close and reopen the terminal so the path is refreshed. |
| PowerShell refuses to run the installer | The installer command above passes `-ExecutionPolicy ByPass` for that one command; run it exactly as shown. |
| Path too long errors on Windows | Clone into a short folder such as `C:\src`, or enable long paths (`git config --global core.longpaths true`, and the Windows "Enable Win32 long paths" setting). |
| `error: ... use --overwrite to replace it` (exit code 3) | The dataset already exists. Add `--overwrite` to replace it, or pick another `--out` folder. |
| A test about checksums fails | Usually different dependency versions. Run `uv sync --locked` and try again. |

## Next steps

- [Testing](testing.md): how tests are organised.
- [Roadmap](../ROADMAP.md): what comes next.
- [Glossary](glossary.md): terms used throughout.

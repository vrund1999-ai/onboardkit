# E6-S1: Project scaffold and tooling

| | |
|---|---|
| **Epic** | [E6: Automated quality gate](../../../epics/m0-foundation-epics.md#e6-automated-quality-gate) |
| **Size** | M |
| **Depends on** | none |
| **Blocks** | E1-S4, E6-S2, E6-S3, E7-S1 |

## User story

As a contributor, I want a working Python project with linting, formatting, type checking, and tests wired up, so that every later story starts on a stable base.

## Context

The repository currently holds only documents. Everything else assumes a package, a lockfile, and standard tooling. This story creates the skeleton and nothing more: no generator logic. It can start on day one, in parallel with the document stories.

## Scope

**In scope**
- `pyproject.toml`, lockfile, source layout, tool configuration.
- A trivial importable package and one passing test.
- Editor and line-ending configuration that makes Windows and Linux agree.

**Out of scope**
- CI (E6-S2).
- Any datagen code.

## Technical design

### Layout

```
pyproject.toml
uv.lock
.python-version            3.12
.editorconfig
.gitattributes
src/onboardkit/__init__.py
src/onboardkit/datagen/__init__.py     version constant placeholder
tests/__init__.py
tests/test_smoke.py
```

### `pyproject.toml`

- `[project]`: name `onboardkit`, version `0.1.0`, `requires-python = ">=3.12"`, license placeholder, dependencies: `pydantic>=2`, `pyyaml`, `typer`, `faker`, `openpyxl`.
- `[dependency-groups] dev`: `pytest`, `pytest-cov`, `ruff`, `mypy`, `types-PyYAML`.
- `[build-system]`: `hatchling`; `[tool.hatch.build.targets.wheel] packages = ["src/onboardkit"]`.
- `[tool.ruff]`: line length 100, target `py312`; lint select `E, F, I, B, UP, SIM, N, RUF`; formatter defaults.
- `[tool.mypy]`: `strict = true`, `files = ["src"]`, plugin `pydantic.mypy`.
- `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `addopts = "-ra --strict-markers"`, markers `slow`.
- `[tool.coverage.run]`: `source = ["onboardkit"]`.

### Line endings

`.gitattributes`:

```
* text=auto eol=lf
*.csv text eol=lf
*.xlsx binary
tests/**/expected/** -text
```

This also removes the LF-to-CRLF warnings seen on Windows. `.editorconfig`: UTF-8, LF, final newline, 4-space Python, 2-space YAML and JSON.

### Developer commands

Documented in the getting started guide (E7-S1), not scripted in a Makefile because the primary shell is PowerShell:

```
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

## Files to create or change

- `pyproject.toml`, `uv.lock`, `.python-version`, `.editorconfig`, `.gitattributes`
- `src/onboardkit/__init__.py`, `src/onboardkit/datagen/__init__.py`
- `tests/test_smoke.py`
- Append to `.gitignore` if needed (`.coverage`, `htmlcov/`, `dist/`).

## Acceptance criteria

- [x] `uv sync` on a clean checkout succeeds and creates the environment.
- [x] `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, and `uv run pytest` all pass.
- [x] `import onboardkit` works and exposes a version.
- [x] `uv.lock` is committed and `uv sync --locked` succeeds.
- [x] No tool configuration lives outside `pyproject.toml` except `.editorconfig` and `.gitattributes`.
- [ ] Windows and Linux checkouts produce identical file contents for text files (verified later by CI).

## Test plan

- The smoke test imports the package and asserts the version string format.
- Run all four commands locally on Windows.

## Risks and notes

- Pinning is done through the lockfile; do not add upper bounds in `pyproject.toml` without a reason.
- `strict` mypy with Pydantic needs the plugin; if friction is high, relax specific flags rather than turning strict off.
- `ruff` is configured to skip `*.md` (`extend-exclude`), because recent ruff versions format Python code blocks inside markdown and the story documents contain illustrative sketches rather than real code.

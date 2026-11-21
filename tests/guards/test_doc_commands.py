"""Guard: every ``onboardkit-gen`` command written in the documentation is accepted by the CLI."""

import re
import shlex

import pytest
from typer.exceptions import Exit, TyperException
from typer.main import get_command

from onboardkit.datagen.cli import app
from tests.guards.markdown import documents, split

SHELLS = {"bash", "sh", "shell", "console", "powershell", "pwsh", "ps1"}
PREFIXES = (
    re.compile(r"^(?:\$|PS>|>)\s*"),
    re.compile(r"^(?:python\s+-m\s+)?uv\s+run\s+"),
)
ENTRY = re.compile(r"^(?:onboardkit-gen|python\s+-m\s+onboardkit\.datagen)\s*")


def commands_in(text: str) -> list[str]:
    """Arguments of every onboardkit-gen invocation in the shell blocks of ``text``."""
    found = []
    for block in split(text)[1]:
        if block.language not in SHELLS:
            continue
        joined: list[str] = []
        carry = ""
        for line in block.lines:
            stripped = line.rstrip()
            if stripped.endswith(("\\", "`")):
                carry += stripped[:-1] + " "
                continue
            joined.append(carry + stripped)
            carry = ""
        for line in joined:
            text_line = line.strip()
            for prefix in PREFIXES:
                text_line = prefix.sub("", text_line)
            for prefix in PREFIXES:
                text_line = prefix.sub("", text_line)
            match = ENTRY.match(text_line)
            if match:
                command = re.split(r"\s+[|>]\s*|\s+2>", text_line[match.end() :])[0]
                found.append(" ".join(command.split()))
    return found


def validate(arguments: str) -> str | None:
    """None when the CLI parses ``arguments``, otherwise the reason it does not."""
    group = get_command(app)
    try:
        tokens = shlex.split(arguments)
        if not tokens or tokens[0].startswith("-"):
            group.make_context("onboardkit-gen", tokens)  # for example --help
            return None
        name, rest = tokens[0], tokens[1:]
        context = group.make_context("onboardkit-gen", [name])
        command = group.get_command(context, name)
        if command is None:
            return f"No such command {name!r}"
        command.make_context(name, rest, parent=context)
    except Exit:
        return None  # --help
    except (TyperException, ValueError) as exc:
        return str(exc)
    return None


def test_documented_commands_are_valid() -> None:
    problems = []
    for path in documents():
        for arguments in commands_in(path.read_text(encoding="utf-8")):
            reason = validate(arguments)
            if reason:
                problems.append(f"{path.name}: onboardkit-gen {arguments}: {reason}")
    assert problems == []


DOC = """
Some text.

```bash
$ onboardkit-gen generate --preset typical --size sample \\
    --seed 42 --out data/generated
uv run onboardkit-gen verify data/generated/x
python -m onboardkit.datagen presets
```

```powershell
onboardkit-gen check .\\data\\generated\\x
```

```python
onboardkit_gen = "not a shell block"
```
"""


def test_commands_are_extracted_from_shell_blocks_only() -> None:
    assert commands_in(DOC) == [
        "generate --preset typical --size sample --seed 42 --out data/generated",
        "verify data/generated/x",
        "presets",
        "check .\\data\\generated\\x",
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        "generate --preset typical --size sample --seed 42 --out data/generated",
        "generate --help",
        "presets",
        "verify some/dir",
        "check some/dir",
        "show some/dir",
    ],
)
def test_valid_commands_pass(arguments: str) -> None:
    assert validate(arguments) is None


@pytest.mark.parametrize(
    "arguments",
    [
        "generate --presett typical",  # a renamed or misspelled flag
        "generate --size",  # option without its value
        "verify",  # missing required argument
        "frobnicate",  # unknown subcommand
    ],
)
def test_renamed_flags_and_unknown_commands_fail_the_guard(arguments: str) -> None:
    assert validate(arguments) is not None

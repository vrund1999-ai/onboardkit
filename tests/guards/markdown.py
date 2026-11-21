"""Small markdown helpers for the documentation guards: fenced blocks, headings, and links only."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FENCE = re.compile(r"^\s*(```+|~~~+)\s*([A-Za-z0-9_+-]*)")
LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


@dataclass(frozen=True)
class Block:
    language: str
    lines: tuple[str, ...]


def documents() -> list[Path]:
    """Every markdown file a reader of the repository would open (not tool caches)."""
    found = [
        REPO_ROOT / name for name in ("README.md", "ROADMAP.md", "CLAUDE.md", "CONTRIBUTING.md")
    ]
    found += sorted((REPO_ROOT / "docs").rglob("*.md"))
    return [p for p in found if p.is_file()]


def split(text: str) -> tuple[list[str], list[Block]]:
    """The lines outside fenced blocks, and the fenced blocks."""
    prose: list[str] = []
    blocks: list[Block] = []
    fence: str | None = None
    language = ""
    current: list[str] = []
    for line in text.splitlines():
        match = FENCE.match(line)
        if fence is None and match:
            fence, language, current = match.group(1)[:3], match.group(2).lower(), []
        elif fence is not None and line.strip().startswith(fence):
            blocks.append(Block(language, tuple(current)))
            fence = None
        elif fence is not None:
            current.append(line)
        else:
            prose.append(line)
    return prose, blocks


def slug(heading: str) -> str:
    """GitHub's anchor for a heading: lower case, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"`|\*|_(?=\S)|\[([^\]]*)\]\([^)]*\)", lambda m: m.group(1) or "", heading)
    text = re.sub(r"[^\w\- ]", "", text.strip().lower())
    return text.replace(" ", "-")


def anchors(text: str) -> set[str]:
    """Every anchor a document defines, with GitHub's numeric suffix for repeated headings."""
    seen: dict[str, int] = {}
    result: set[str] = set()
    for line in split(text)[0]:
        match = HEADING.match(line)
        if not match:
            continue
        base = slug(match.group(2))
        count = seen.get(base, 0)
        seen[base] = count + 1
        result.add(base if count == 0 else f"{base}-{count}")
    return result


def broken_links(path: Path, text: str, root: Path = REPO_ROOT) -> list[str]:
    """Relative links in ``text`` (a document at ``path``) whose file or anchor does not exist."""
    problems = []
    for line in split(text)[0]:
        for target in LINK.findall(line):
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("//"):
                continue  # http, https, mailto, and so on: never followed (no network)
            file_part, _, fragment = target.partition("#")
            destination = path if not file_part else (path.parent / file_part).resolve()
            where = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
            if not destination.exists():
                problems.append(f"{where}: {target} points to a file that does not exist")
            elif (
                fragment
                and destination.suffix == ".md"
                and fragment.lower() not in anchors(destination.read_text(encoding="utf-8"))
            ):
                problems.append(f"{where}: {target} points to a missing heading")
    return problems

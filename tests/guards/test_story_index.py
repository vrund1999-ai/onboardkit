"""Guard: story files, the story index, and the progress tables always agree."""

import re
from collections import defaultdict
from pathlib import Path

import pytest

from tests.guards.markdown import REPO_ROOT

MILESTONES = ("m0", "m1")
MINIMUM_STORIES = {"m0": 35, "m1": 8}
EPICS = REPO_ROOT / "docs" / "progress" / "epics.md"
STATUSES = ("Not started", "In progress", "Blocked", "Done", "Dropped")
ID = r"E\d+-S\d+"
ROW = re.compile(rf"^\|\s*\[({ID})\]\(([^)]+)\)\s*\|(.*)\|\s*$")


def story_files(root: Path) -> dict[str, Path]:
    return {
        re.match(ID, p.name).group(0): p  # type: ignore[union-attr]
        for p in sorted(root.glob("E*/E*-S*.md"))
    }


def indexed(text: str) -> dict[str, str]:
    """Story id to the link target, from the story index table."""
    return {m.group(1): m.group(2) for line in text.splitlines() if (m := ROW.match(line))}


def progress_rows(text: str) -> list[tuple[str, str, str]]:
    """(story id, epic id, status) for every row of the progress table."""
    rows = []
    epic = ""
    for line in text.splitlines():
        heading = re.match(r"^## (E\d+):", line)
        if heading:
            epic = heading.group(1)
        match = ROW.match(line)
        if match:
            cells = [c.strip() for c in match.group(3).split("|")]
            rows.append((match.group(1), epic, cells[2]))  # title | size | status | ...
    return rows


def rolled_up(statuses: list[str]) -> str:
    """The roll-up rule from docs/progress/README.md."""
    finished = [s for s in statuses if s in ("Done", "Dropped")]
    if len(finished) == len(statuses) and "Done" in statuses:
        return "Done"
    unfinished = [s for s in statuses if s not in ("Done", "Dropped")]
    if unfinished and all(s == "Blocked" for s in unfinished):
        return "Blocked"
    if "In progress" in statuses or "Done" in statuses:
        return "In progress"
    return "Not started"


def index_problems(files: dict[str, Path], index: dict[str, str], root: Path) -> list[str]:
    problems = [
        f"{i}: story file has no entry in the index" for i in sorted(files.keys() - index.keys())
    ]
    problems += [
        f"{i}: indexed but there is no story file" for i in sorted(index.keys() - files.keys())
    ]
    for story_id in sorted(files.keys() & index.keys()):
        if (root / index[story_id]).resolve() != files[story_id].resolve():
            problems.append(f"{story_id}: index link does not point at its story file")
    return problems


def paths(milestone: str) -> tuple[Path, Path, Path]:
    """(stories folder, story index, progress table) for a milestone."""
    stories = REPO_ROOT / "docs" / "stories" / milestone
    progress = REPO_ROOT / "docs" / "progress" / "stories" / f"{milestone}.md"
    return stories, stories / "README.md", progress


@pytest.mark.parametrize("milestone", MILESTONES)
def test_every_story_file_is_in_the_index_and_the_index_has_no_ghosts(milestone: str) -> None:
    stories, index, _ = paths(milestone)
    files = story_files(stories)
    assert len(files) >= MINIMUM_STORIES[milestone]
    assert index_problems(files, indexed(index.read_text(encoding="utf-8")), stories) == []


@pytest.mark.parametrize("milestone", MILESTONES)
def test_every_story_file_has_a_progress_row_and_vice_versa(milestone: str) -> None:
    stories, _, progress = paths(milestone)
    rows = progress_rows(progress.read_text(encoding="utf-8"))
    ids = [r[0] for r in rows]
    assert len(ids) == len(set(ids)), "a story appears twice in the progress table"
    assert set(ids) == set(story_files(stories))


@pytest.mark.parametrize("milestone", MILESTONES)
def test_statuses_come_from_the_allowed_list(milestone: str) -> None:
    _, _, progress = paths(milestone)
    for story_id, _, status in progress_rows(progress.read_text(encoding="utf-8")):
        assert status in STATUSES, f"{story_id}: {status!r}"


@pytest.mark.parametrize("milestone", MILESTONES)
def test_progress_counts_match_the_rows(milestone: str) -> None:
    _, _, progress = paths(milestone)
    text = progress.read_text(encoding="utf-8")
    rows = progress_rows(text)
    per_epic: dict[str, list[str]] = defaultdict(list)
    for _, epic, status in rows:
        per_epic[epic].append(status)
    overall = re.search(r"\*\*Overall:\*\* (\d+) of (\d+) stories done", text)
    assert overall, "missing the Overall line"
    assert (int(overall.group(1)), int(overall.group(2))) == (
        sum(s == "Done" for _, _, s in rows),
        len(rows),
    )
    for epic, statuses in per_epic.items():
        section = re.search(rf"## {epic}:.*?\n\n(\d+) of (\d+) done", text, re.S)
        assert section, f"{epic}: missing its 'N of M done' line"
        assert (int(section.group(1)), int(section.group(2))) == (
            statuses.count("Done"),
            len(statuses),
        ), epic


def test_epic_rows_equal_the_story_rows_and_roll_up_correctly() -> None:
    per_epic: dict[str, list[str]] = defaultdict(list)
    for milestone in MILESTONES:
        _, _, progress = paths(milestone)
        for _, epic, status in progress_rows(progress.read_text(encoding="utf-8")):
            per_epic[epic].append(status)
    seen = set()
    for line in EPICS.read_text(encoding="utf-8").splitlines():
        match = re.match(
            r"^\|\s*\[(E\d+)\]\([^)]*\)\s*\|[^|]*\|\s*(\d+) / (\d+)\s*\|\s*([^|]+?)\s*\|", line
        )
        if not match:
            continue
        epic, done, total, status = (
            match.group(1),
            int(match.group(2)),
            int(match.group(3)),
            match.group(4),
        )
        seen.add(epic)
        statuses = per_epic.get(epic, [])
        assert (done, total) == (statuses.count("Done"), len(statuses)), epic
        assert status in STATUSES and status == rolled_up(statuses), f"{epic}: {status}"
    assert {e for e in per_epic} <= seen
    assert {"E1", "E7", "E8", "E9"} <= seen


def test_a_story_file_without_an_index_entry_fails_the_guard(tmp_path: Path) -> None:
    (tmp_path / "E9-x").mkdir()
    new = tmp_path / "E9-x" / "E9-S1-new.md"
    new.write_text("# E9-S1: New\n", encoding="utf-8")
    files = story_files(tmp_path)
    assert index_problems(files, {}, tmp_path) == ["E9-S1: story file has no entry in the index"]
    assert index_problems(files, {"E9-S1": "E9-x/E9-S1-new.md"}, tmp_path) == []
    assert index_problems({}, {"E9-S2": "x.md"}, tmp_path) == [
        "E9-S2: indexed but there is no story file"
    ]
    assert index_problems(files, {"E9-S1": "E9-x/other.md"}, tmp_path) == [
        "E9-S1: index link does not point at its story file"
    ]


def test_roll_up_rules() -> None:
    assert rolled_up(["Done", "Done"]) == "Done"
    assert rolled_up(["Done", "Dropped"]) == "Done"
    assert rolled_up(["Dropped"]) == "Not started"
    assert rolled_up(["Done", "Not started"]) == "In progress"
    assert rolled_up(["In progress", "Not started"]) == "In progress"
    assert rolled_up(["Done", "Blocked"]) == "Blocked"
    assert rolled_up(["Not started", "Not started"]) == "Not started"


def test_progress_rows_are_read_from_the_table() -> None:
    text = (
        "## E1: X\n\n"
        "| [E1-S1](a.md) | Title | S | Done | [#1](u) |  |\n"
        "| [E1-S2](b.md) | Title | M | Not started |  |  |\n"
    )
    assert progress_rows(text) == [("E1-S1", "E1", "Done"), ("E1-S2", "E1", "Not started")]

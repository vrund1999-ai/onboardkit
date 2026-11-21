"""Guard: relative links and anchors in the markdown documents resolve."""

from pathlib import Path

from tests.guards.markdown import anchors, broken_links, documents, slug


def test_relative_links_in_documents_resolve() -> None:
    problems = []
    for path in documents():
        problems += broken_links(path, path.read_text(encoding="utf-8"))
    assert problems == []


def test_a_broken_file_link_is_reported(tmp_path: Path) -> None:
    doc = tmp_path / "a.md"
    doc.write_text("See [other](missing.md) and [ok](b.md).\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B\n", encoding="utf-8")
    problems = broken_links(doc, doc.read_text(encoding="utf-8"), tmp_path)
    assert problems == ["a.md: missing.md points to a file that does not exist"]


def test_a_broken_anchor_is_reported_and_a_good_one_is_not(tmp_path: Path) -> None:
    doc = tmp_path / "a.md"
    (tmp_path / "b.md").write_text("# Title\n\n## Some `Heading`, here\n", encoding="utf-8")
    doc.write_text(
        "[good](b.md#some-heading-here) [bad](b.md#nope) [self](#top)\n\n# Top\n", encoding="utf-8"
    )
    problems = broken_links(doc, doc.read_text(encoding="utf-8"), tmp_path)
    assert problems == ["a.md: b.md#nope points to a missing heading"]


def test_links_inside_code_fences_and_external_links_are_ignored(tmp_path: Path) -> None:
    doc = tmp_path / "a.md"
    text = "```\n[x](gone.md)\n```\n[web](https://example.com/x) [mail](mailto:a@b.c)\n"
    doc.write_text(text, encoding="utf-8")
    assert broken_links(doc, text, tmp_path) == []


def test_slug_and_repeated_headings() -> None:
    assert slug("E1: Fictional firm & the `vocabulary`") == "e1-fictional-firm--the-vocabulary"
    assert anchors("# A\n\n## A\n\n## A\n") == {"a", "a-1", "a-2"}

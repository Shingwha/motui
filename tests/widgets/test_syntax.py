"""Syntax: the regex highlighter, its language table and its theme bands."""

from dataclasses import replace

import pytest

from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import Markdown
from motui.widgets.syntax import (
    Highlighter,
    RegexHighlighter,
    default_highlighter,
    highlight,
)



@pytest.mark.parametrize(
    "lang, code, kind, token",
    [
        ("python", "x = 1", "number", "1"),
        ("python", "# note", "comment", "# note"),
        ("py", '"text"', "string", '"text"'),
        ("bash", "# note", "comment", "# note"),
        ("unknown", "x = 1", None, "x = 1"),
    ],
)
def test_the_highlighter_colors_the_matching_tokens(lang, code, kind, token):
    row = highlight(code, lang)[0]
    if kind is None:
        assert all(seg.style == DEFAULT_THEME.content.code for seg in row.segments)
        return
    matched = [seg for seg in row.segments if seg.text == token]
    assert matched and matched[0].style != DEFAULT_THEME.content.code


def test_python_keywords_carry_the_accent_hue():
    row = highlight("def f(x): return 1", "python")[0]
    styles = {seg.text: seg.style for seg in row.segments}
    accent = Style(fg=DEFAULT_THEME.content.accent.fg)
    assert styles["def"] == accent
    assert styles["return"] == accent
    assert styles["1"] == DEFAULT_THEME.status.warning


def test_a_fence_highlights_its_tagged_body_row_by_row():
    rows = Markdown("```python\nx = 1\n```").render(80)
    assert rows[0].text == "```python"
    assert [seg.text for seg in rows[1].segments] == ["x = ", "1"]
    assert rows[1].segments[1].style == DEFAULT_THEME.status.warning


@pytest.mark.parametrize("alias, canonical", [("py", "python")])
def test_language_aliases_resolve_to_the_same_rows(alias, canonical):
    code = "x = 1"
    assert [row.text for row in highlight(code, alias)] == [
        row.text for row in highlight(code, canonical)
    ]


def test_unknown_and_empty_languages_render_monochrome():
    for lang in ("", "unknown"):
        rows = highlight("plain text", lang)
        assert rows[0].segments[0].style == DEFAULT_THEME.content.code


def test_token_colors_follow_the_injected_theme():
    theme = replace(
        DEFAULT_THEME,
        syntax=replace(DEFAULT_THEME.syntax, number=Style(fg="#ff00ff")),
    )
    row = highlight("x = 1", "python", theme=theme)[0]
    number = [seg for seg in row.segments if seg.text == "1"]
    assert number[0].style == Style(fg="#ff00ff")


def test_a_custom_language_table_extends_and_overrides():
    custom = RegexHighlighter(languages={"mine": [(r"\bfoo\b", "keyword")]})
    row = custom.highlight("foo bar", "mine")[0]
    assert row.segments[0].text == "foo"
    assert row.segments[0].style == Style(fg=DEFAULT_THEME.content.accent.fg)
    with pytest.raises(ValueError, match="unknown syntax token"):
        RegexHighlighter(languages={"bad": [(r"x", "nope")]})


def test_the_shared_default_highlighter_is_one_instance():
    assert default_highlighter() is default_highlighter()
    assert isinstance(default_highlighter(), Highlighter)
    assert [row.text for row in default_highlighter().highlight("x = 1", "python")] == ["x = 1"]

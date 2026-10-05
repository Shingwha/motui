"""Tests for the fenced-code highlighter wiring in mocode_tui.widgets.markdown.

Contracts (W3 ticket): ``FenceRule`` parses the info string's language tag
and routes the body through the highlighter -- the built-in regex engine by
default, an injected one via ``Markdown(..., highlighter=...)``.  Unknown or
missing tags render monochrome in ``CODE``; the fence's row set and width
behavior are unchanged; a half-open fence stays streaming-safe.
"""

from dataclasses import replace

from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import CODE, MUTED, Style
from mocode_tui.core.theme import DEFAULT_THEME
from mocode_tui.widgets.markdown import Markdown

# The highlighter's token colors, derived from DEFAULT_THEME.
COMMENT = DEFAULT_THEME.muted.merge(Style(italic=True))
KEYWORD = Style(fg=DEFAULT_THEME.accent.fg)  # accent's hue, weight-neutral
NUMBER = DEFAULT_THEME.warning
STRING = DEFAULT_THEME.success


def _tokens(row: Line) -> list[tuple[str, Style]]:
    return [(seg.text, seg.style) for seg in row.segments]


def test_python_fence_highlights_tokens_row_by_row():
    rows = Markdown("```python\n# note\ndef f():\n    return 1\n```").render(80)
    assert [row.text for row in rows] == [
        "```python",
        "# note",
        "def f():",
        "    return 1",
        "```",
    ]
    assert _tokens(rows[0]) == [("```python", MUTED)]  # the markers stay visible
    assert _tokens(rows[2]) == [("def", KEYWORD), (" f():", CODE)]
    assert _tokens(rows[3]) == [
        ("    ", CODE),
        ("return", KEYWORD),
        (" ", CODE),
        ("1", NUMBER),
    ]


def test_bash_and_json_fences_highlight_their_own_tokens():
    bash = Markdown('```bash\necho "hi" # tail\n```').render(80)
    assert _tokens(bash[1]) == [
        ("echo ", CODE),  # the builtin shares the plain code color and fuses
        ('"hi"', STRING),
        (" ", CODE),
        ("# tail", COMMENT),
    ]
    rows = Markdown('```json\n{"a": 1, "b": true}\n```').render(80)
    assert _tokens(rows[1]) == [
        ("{", CODE),
        ('"a"', KEYWORD),
        (": ", CODE),
        ("1", NUMBER),
        (", ", CODE),
        ('"b"', KEYWORD),
        (": ", CODE),
        ("true", KEYWORD),
        ("}", CODE),
    ]


def test_untagged_and_unknown_tags_render_monochrome():
    for text, opening in (
        ("```\nplain body\n```", "```"),
        ("```brainfuck\nplain body\n```", "```brainfuck"),
    ):
        rows = Markdown(text).render(80)
        assert [row.text for row in rows] == [opening, "plain body", "```"]
        assert _tokens(rows[0]) == [(opening, MUTED)]  # the markers render muted
        assert _tokens(rows[1]) == [("plain body", CODE)]  # the body stays monochrome


def test_a_tag_with_trailing_attributes_still_resolves():
    rows = Markdown("```python title=example.py\nx = 1\n```").render(80)
    assert _tokens(rows[0]) == [("```python title=example.py", MUTED)]
    assert _tokens(rows[1]) == [("x = ", CODE), ("1", NUMBER)]


def test_injected_highlighter_reaches_the_fence_rule():
    class Stub:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def highlight(self, code: str, lang: str) -> list[Line]:
            self.calls.append((code, lang))
            return [Line.from_text(f"{lang}:{code}", Style(bold=True))]

    stub = Stub()
    md = Markdown("```python\nbody line\n```", highlighter=stub)
    assert [row.text for row in md.render(80)] == ["```python", "python:body line", "```"]
    assert stub.calls == [("body line", "python")]
    # An untagged fence still calls the engine (it owns the fallback).
    assert [row.text for row in Markdown("```\nbody\n```", highlighter=stub).render(80)] == [
        "```",
        ":body",
        "```",
    ]


def test_theme_restyles_the_fence_tokens():
    theme = replace(DEFAULT_THEME, warning=Style(fg="#abcdef"))
    rows = Markdown("```python\nn = 1\n```", theme=theme).render(80)
    assert _tokens(rows[0]) == [("```python", theme.muted)]
    assert _tokens(rows[1]) == [("n = ", theme.code), ("1", theme.warning)]


def test_fence_rows_still_fit_the_width_and_wrap_nowhere():
    md = Markdown("```python\nthis line is considerably longer than the width\n```")
    rows = md.render(20)
    assert [row.width for row in rows] == [9, 20, 3]  # markers, fit body, markers
    assert rows[1].text.endswith("\u2026")


def test_half_open_fence_streaming_stays_safe():
    for size in range(len("```python\ndef f(:\n    x") + 1):
        source = "```python\ndef f(:\n    x"[:size]
        rows = Markdown(source).render(16)
        assert all(row.width <= 16 for row in rows)  # never raises, never overflows

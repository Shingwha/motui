"""Tests for mocode_tui.core.theme (Theme / DEFAULT_THEME) and its wiring.

``DEFAULT_THEME`` reproduces the pre-Theme defaults field by field; a
component resolves styles from its ``theme=``, an explicit ``style=`` winning.
"""

from dataclasses import replace

import pytest

from mocode_tui import DEFAULT_THEME, Segment, Theme
from mocode_tui.chat.message import Message
from mocode_tui.chat.tools import EditBlock, ToolBlock
from mocode_tui.core.style import (
    ACCENT,
    BORDER,
    CODE,
    CURSOR,
    DIM,
    ERROR,
    HEADING,
    INLINE_CODE,
    LINK,
    LIST_MARKER,
    MUTED,
    NONE,
    SELECTION,
    SUCCESS,
    WARNING,
    Style,
)
from mocode_tui.core.theme import DEFAULT_THEME
from mocode_tui.widgets.chrome import Divider, Notice
from mocode_tui.widgets.input import Input
from mocode_tui.widgets.markdown import Markdown
from mocode_tui.widgets.table import DEFAULT_HEADER_STYLE, Table


def test_default_theme_matches_the_old_module_constants():
    """Every field equals the constant the components used to define."""
    assert DEFAULT_THEME.dim == DIM
    assert DEFAULT_THEME.muted == MUTED
    assert DEFAULT_THEME.accent == ACCENT
    assert DEFAULT_THEME.success == SUCCESS
    assert DEFAULT_THEME.error == ERROR
    assert DEFAULT_THEME.warning == WARNING
    assert DEFAULT_THEME.border == BORDER
    assert DEFAULT_THEME.code == CODE
    assert DEFAULT_THEME.cursor == CURSOR
    assert DEFAULT_THEME.selection == SELECTION
    # The markdown palette mirrors its constants; color VALUES stay unpinned
    # (retuning a hex in style.py must never turn the suite red).
    assert DEFAULT_THEME.heading == HEADING
    assert DEFAULT_THEME.link == LINK
    assert DEFAULT_THEME.inline_code == INLINE_CODE
    assert DEFAULT_THEME.list_marker == LIST_MARKER


def test_default_theme_structures_keep_their_shape():
    """The structural tables keep their keys and value sources; color values
    stay unpinned so retuning a default never turns the suite red."""
    assert set(DEFAULT_THEME.tones) == {"tool", "code", "plain"}
    assert set(DEFAULT_THEME.title_tones) == {"tool"}
    assert DEFAULT_THEME.notice_levels == {
        "warn": ("WARNING: ", WARNING),
        "error": ("ERROR: ", ERROR),
    }


def test_default_palette_keeps_bold_out_of_the_markdown_defaults():
    """The bold policy: none of the markdown-facing default styles -- the
    heading ladder, the link, inline code, list markers, the table first
    column, the table header or the syntax token table -- carries bold.  The
    only bold in a default render comes from the ``**...**`` syntax itself."""
    ladder = DEFAULT_THEME.headings
    assert not any(style.bold for style in ladder)
    assert ladder[0].underline  # h1 underlines
    assert all(style == ladder[1] for style in ladder[1:])  # one hue below h1
    for name in ("link", "inline_code", "list_marker", "first_column"):
        assert not getattr(DEFAULT_THEME, name).bold, name
    assert DEFAULT_HEADER_STYLE == NONE


def test_theme_is_frozen_and_replaceable():
    theme = replace(DEFAULT_THEME, accent=Style(fg="#ff0000"))
    assert theme.accent == Style(fg="#ff0000")
    assert theme.border == DEFAULT_THEME.border  # untouched fields carry over
    assert theme != DEFAULT_THEME
    assert DEFAULT_THEME.accent == ACCENT  # the original is never mutated
    with pytest.raises(Exception):  # frozen dataclass: assignment raises
        theme.accent = ACCENT  # type: ignore[misc]


def test_message_band_comes_from_the_theme():
    band = Style(bg="#123456")
    rows = Message("user", "hi", theme=Theme(user_bg=band)).render(6)
    assert all(seg.style == band for row in rows for seg in row.segments)


def test_tool_block_and_edit_block_bands_come_from_the_theme():
    tool_bg = Style(bg="#001100")
    code_bg = Style(bg="#002200")
    theme = Theme(tool_bg=tool_bg, code_bg=code_bg)
    rows = ToolBlock("t", ["b"], tone="tool", theme=theme).render(20)
    assert {seg.style.bg for row in rows for seg in row.segments} == {"#001100"}
    rows = ToolBlock("t", ["b"], tone="code", theme=theme).render(20)
    assert {seg.style.bg for row in rows for seg in row.segments} == {"#002200"}
    rows = EditBlock("p", theme=theme).render(20)
    assert {seg.style.bg for row in rows for seg in row.segments} == {"#002200"}


def test_table_styles_come_from_the_theme():
    theme = Theme(
        table_border=Style(fg="#111111"),
        first_column=Style(fg="#222222"),
    )
    rows = Table(["A", "B"], [["1", "x"]], theme=theme).render(12)
    grid = set("\u2502\u251c\u253c\u2524\u2500\u250c\u252c\u2510\u2514\u2534\u2518")
    for row in rows:
        for seg in row.segments:
            if seg.text and set(seg.text) <= grid:
                assert seg.style == Style(fg="#111111")
    # The header is plain by default; the first data column takes the theme's.
    assert rows[1].segments[1] == Segment(" A ", NONE)
    assert rows[3].segments[1] == Segment(" 1 ", Style(fg="#222222"))


def test_notice_levels_come_from_the_theme():
    theme = Theme(warning=Style(fg="#333333"))
    row = Notice("careful", level="warn", theme=theme).render(80)[0]
    assert row.segments[0] == Segment("WARNING: ", Style(fg="#333333"))


def test_input_prompt_and_cursor_come_from_the_theme():
    theme = Theme(accent=Style(fg="#444444"), cursor=Style(reverse=True, bold=True))
    field = Input(theme=theme)
    field.insert("a")
    rows = field.render(20)
    assert rows[0].segments[0].style == Style(fg="#444444")  # the prompt
    # The cursor cell merges the theme's cursor style onto the text style.
    assert rows[0].segments[2].style == Style(reverse=True, bold=True)


def test_markdown_headings_and_code_come_from_the_theme():
    theme = Theme(heading=Style(fg="#555555"), code=Style(fg="#666666"))
    md = Markdown("# H\n\n```\nx = 1\n```", theme=theme)
    rows = md.render(80)
    assert rows[0].segments[0].style == Style(fg="#555555", underline=True)  # h1
    assert rows[-2].segments[0].style == Style(fg="#666666")  # fenced code body


def test_markdown_heading_ladder_derives_from_the_theme():
    """The whole ladder follows heading, not just the first level."""
    theme = Theme(heading=Style(fg="#555555"))
    styles = [
        Markdown(f"{'#' * level} H", theme=theme).render(80)[0].segments[0].style
        for level in range(1, 7)
    ]
    assert styles[0] == Style(fg="#555555", underline=True)
    assert all(style == Style(fg="#555555") for style in styles[1:])


def test_markdown_quote_and_list_markers_come_from_the_theme():
    theme = Theme(muted=Style(fg="#777777"), list_marker=Style(fg="#777777"))
    quote = Markdown("> q", theme=theme).render(80)
    assert quote[0].segments[0].style == Style(fg="#777777")  # the bar stays muted
    assert quote[0].segments[1].style == Style(italic=True)  # the body is italic
    listed = Markdown("- item", theme=theme).render(80)
    assert listed[0].segments[0].style == Style(fg="#777777")  # the marker


def test_divider_border_comes_from_the_theme():
    row = Divider(theme=Theme(border=Style(fg="#888888"))).render(10)[0]
    assert all(seg.style == Style(fg="#888888") for seg in row.segments)


def test_explicit_style_beats_the_theme():
    theme = Theme(user_bg=Style(bg="#001100"))
    rows = Message("user", "hi", style=Style(bg="#ff0000"), theme=theme).render(6)
    assert all(seg.style == Style(bg="#ff0000") for row in rows for seg in row.segments)
    # Without the explicit style the same theme still paints the band.
    rows = Message("user", "hi", theme=theme).render(6)
    assert all(seg.style == Style(bg="#001100") for row in rows for seg in row.segments)


def test_default_theme_is_a_plain_theme_instance():
    assert DEFAULT_THEME == Theme()

"""Tests for mocode_tui.core.theme (Theme / DEFAULT_THEME) and its wiring.

Contracts (the W1 ticket):

* :data:`~mocode_tui.core.theme.DEFAULT_THEME` reproduces the pre-Theme
  defaults field by field -- every component renders identically with no
  theme injected (the demo's piped dump is the byte-level proof; here the
  fields are pinned directly);
* a component built with ``theme=`` resolves its styles from that theme at
  render time;
* an explicit ``style=`` argument wins over the theme field;
* ``dataclasses.replace`` builds variants, and a variant handed to a
  component changes only what it overrides.
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
    MUTED,
    NONE,
    SELECTION,
    SUCCESS,
    WARNING,
    Style,
)
from mocode_tui.core.theme import Theme as CoreTheme
from mocode_tui.widgets.chrome import Divider, Notice
from mocode_tui.widgets.input import Input
from mocode_tui.widgets.markdown import Markdown
from mocode_tui.widgets.table import Table


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
    # Component bands: the old message.USER_BG / tools.TOOL_BG / tools.CODE_BG
    # / table.TABLE_BORDER / table first-column purple.
    assert DEFAULT_THEME.user_bg == Style(bg="#1c2b3a")
    assert DEFAULT_THEME.tool_bg == Style(bg="#16281c")
    assert DEFAULT_THEME.code_bg == Style(bg="#12181f")
    assert DEFAULT_THEME.table_border == NONE
    assert DEFAULT_THEME.first_column == Style(fg="#bc8cff", bold=True)


def test_default_theme_structures_match_the_old_private_tables():
    """headings / tones / title_tones / notice_levels keep their old shape."""
    assert DEFAULT_THEME.headings == (
        ACCENT,
        ACCENT.merge(Style(underline=True)),
        MUTED,
        MUTED.merge(Style(dim=True)),
        MUTED.merge(Style(dim=True)),
        MUTED.merge(Style(dim=True, italic=True)),
    )
    assert DEFAULT_THEME.tones == {
        "tool": Style(bg="#16281c"),
        "code": Style(bg="#12181f"),
        "plain": NONE,
    }
    assert DEFAULT_THEME.title_tones == {
        "tool": Style(bg="#16281c").merge(SUCCESS).merge(Style(bold=True)),
    }
    assert DEFAULT_THEME.notice_levels == {
        "warn": ("WARNING: ", WARNING),
        "error": ("ERROR: ", ERROR),
    }


def test_theme_is_frozen_and_replaceable():
    theme = replace(DEFAULT_THEME, accent=Style(fg="#ff0000"))
    assert theme.accent == Style(fg="#ff0000")
    assert theme.border == DEFAULT_THEME.border  # untouched fields carry over
    assert theme != DEFAULT_THEME
    assert DEFAULT_THEME.accent == ACCENT  # the original is never mutated
    with pytest.raises(Exception):  # frozen dataclass: assignment raises
        theme.accent = ACCENT  # type: ignore[misc]


def test_theme_is_one_object_from_both_faces():
    assert Theme is CoreTheme

    from mocode_tui.core import DEFAULT_THEME as core_default

    assert core_default is DEFAULT_THEME


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
    # The header keeps its bold style; the first data column takes the theme's.
    assert rows[1].segments[1] == Segment(" A ", Style(bold=True))
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
    theme = Theme(accent=Style(fg="#555555"), code=Style(fg="#666666"))
    md = Markdown("# H\n\n```\nx = 1\n```", theme=theme)
    rows = md.render(80)
    assert rows[0].segments[0].style == Style(fg="#555555")  # heading ladder
    assert rows[-1].segments[0].style == Style(fg="#666666")  # fenced code


def test_markdown_heading_ladder_derives_from_the_theme():
    """The whole ladder follows accent/muted, not just the first level."""
    theme = Theme(accent=Style(fg="#555555"), muted=Style(fg="#666666"))
    styles = [
        Markdown(f"{'#' * level} H", theme=theme).render(80)[0].segments[0].style
        for level in range(1, 7)
    ]
    assert styles[0] == Style(fg="#555555")
    assert styles[1] == Style(fg="#555555", underline=True)
    assert styles[2] == Style(fg="#666666")
    assert styles[3] == Style(fg="#666666", dim=True)
    assert styles[5] == Style(fg="#666666", dim=True, italic=True)


def test_markdown_quote_and_list_markers_come_from_the_theme():
    theme = Theme(muted=Style(fg="#777777"))
    quote = Markdown("> q", theme=theme).render(80)
    assert quote[0].segments[0].style == Style(fg="#777777")
    listed = Markdown("- item", theme=theme).render(80)
    assert listed[0].segments[0].style == Style(fg="#777777")


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


def test_replace_chain_restyles_a_whole_family():
    """One replace, handed to several components, restyles each of them."""
    theme = replace(
        DEFAULT_THEME,
        accent=Style(fg="#ff8800"),
        border=Style(fg="#ff8800"),
    )
    assert Markdown("# H", theme=theme).render(80)[0].segments[0].style == Style(fg="#ff8800")
    assert Divider(theme=theme).render(10)[0].segments[0].style == Style(fg="#ff8800")
    assert Input(theme=theme).render(20)[0].segments[0].style == Style(fg="#ff8800")


def test_default_theme_is_a_plain_theme_instance():
    assert DEFAULT_THEME == Theme()

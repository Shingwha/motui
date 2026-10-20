"""Tests for motui.kernel.theme (Theme / DEFAULT_THEME) and its wiring.

``DEFAULT_THEME`` reproduces the pre-Theme defaults field by field; a
component resolves styles from its ``theme=``, an explicit ``style=`` winning.
"""

from dataclasses import replace

import pytest

from motui import DEFAULT_THEME, Segment, Theme
from motui.kernel import ACCENT, DIM, ERROR, MUTED, SUCCESS, WARNING
from motui.kernel.style import (
    BORDER,
    CODE,
    FOCUS,
    HEADING,
    INLINE_CODE,
    LINK,
    LIST_MARKER,
    NONE,
    SELECTION,
    Style,
)
from motui.kernel.theme import DEFAULT_THEME, Themed
from motui.widgets import (
    Autocomplete,
    Button,
    CheckGroup,
    Checkbox,
    Collapsible,
    Dialog,
    Diff,
    Divider,
    Editor,
    Link,
    List,
    Option,
    ProgressBar,
    Radio,
    Select,
    ShortcutBar,
    Slider,
    StatusLine,
    Text,
    Tree,
    TreeNode,
)
from motui.widgets.textfield import Input
from motui.widgets.markdown import Markdown
from motui.widgets.table import DEFAULT_HEADER_STYLE, Table


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
    assert DEFAULT_THEME.focus == FOCUS
    assert DEFAULT_THEME.selection == SELECTION
    # The band family's own defaults: the whole family is NONE (D1 -- the
    # toolkit paints structure and position, the host paints feedback), and
    # the caret's one-cell block is the band family's carve-out (D2).
    assert DEFAULT_THEME.caret == Style(reverse=True)
    assert DEFAULT_THEME.ground == NONE
    assert DEFAULT_THEME.hover == NONE
    assert DEFAULT_THEME.ground_active == NONE
    # The markdown palette mirrors its constants; color VALUES stay unpinned
    # (retuning a hex in style.py must never turn the suite red).
    assert DEFAULT_THEME.heading == HEADING
    assert DEFAULT_THEME.link == LINK
    assert DEFAULT_THEME.inline_code == INLINE_CODE
    assert DEFAULT_THEME.list_marker == LIST_MARKER
    # The scrollbar's bands: the track dims, the thumb stays the terminal's
    # own foreground (the brightest base), the chrome convention.
    assert DEFAULT_THEME.scrollbar == DIM
    assert DEFAULT_THEME.scrollbar_thumb == NONE
    # The toast band: a reverse-video dim band, the overlay reading.
    assert DEFAULT_THEME.toast == Style(reverse=True, dim=True)


def test_the_hover_band_is_a_full_equality_field():
    """``hover``: the pointer tier's own band, NONE by default (D1), and a
    full equality field -- a theme that changes it alone never equals the
    default, which is what lets a host theme pointer feedback alone."""
    assert DEFAULT_THEME.hover == NONE
    assert replace(DEFAULT_THEME, hover=Style(reverse=True)) != DEFAULT_THEME
    assert replace(DEFAULT_THEME, hover=Style(reverse=True, bold=True)) != DEFAULT_THEME


def test_default_theme_structures_keep_their_shape():
    """The structural tables keep their keys and value sources; color values
    stay unpinned so retuning a default never turns the suite red."""
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
    # D4: segment 0 is the blank cursor seat, so the grid's first cell is 2.
    assert rows[1].segments[2] == Segment(" A ", NONE)
    assert rows[3].segments[2] == Segment(" 1 ", Style(fg="#222222"))


def test_input_prompt_and_caret_come_from_the_theme():
    theme = Theme(accent=Style(fg="#444444"), caret=Style(reverse=True, bold=True))
    field = Input(theme=theme)
    field.insert("a")
    rows = field.render(20)
    assert rows[0].segments[0].style == Style(fg="#444444")  # the prompt
    # The caret cell merges the theme's caret style onto the text style.
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
    theme = Theme(border=Style(fg="#001100"))
    row = Divider(style=Style(fg="#ff0000"), theme=theme).render(10)[0]
    assert all(seg.style == Style(fg="#ff0000") for seg in row.segments)
    # Without the explicit style the same theme still paints the rule.
    row = Divider(theme=theme).render(10)[0]
    assert all(seg.style == Style(fg="#001100") for seg in row.segments)


def test_styles_resolve_once_at_construction(monkeypatch):
    """``render(width)`` never resolves a style again -- the DESIGN.md rule.

    ``Themed._pick`` is the toolkit's one resolution point ("explicit > theme
    field > ``DEFAULT_THEME``"), and every construction-time style goes
    through it.  This test wraps it with a counter and pins two facts: the
    batch below *does* resolve while being constructed (the positive
    control, so a silent no-op cannot pass), and a full ``render(width)``
    afterwards adds **zero** calls.  Rendering therefore reads the styles
    stored on the instance -- the theme is frozen, and an implementation
    that started re-picking during render would be doing redundant work on
    the hot path (and would let a future mutable lookup drift from the
    construction-time contract).

    Components that legitimately read the theme *during* render are left
    out of the batch, each for its own documented reason:

    * ``Divider`` / ``Panel``: ``style`` (and the divider's ``label_style``)
      are mutable attributes a host restyles in place, so the border is
      resolved per render by design (``kernel/theme.py``'s docstring names
      the divider case).
    * ``Notice``: a mutable ``level`` selects the band, so it reads
      ``theme.notice_levels`` on every render.
    * ``Tabs`` / ``NavList``: the unfocused rule merges ``theme.muted``
      directly per render; it does not call ``_pick``, so the counter would
      stay at zero, but they are not construction-resolved either.
    * ``Markdown``: its shared rule context reads theme fields per render
      (headings, fences, list markers, a thematic break's ``Divider``).
    * ``Find`` / ``Tooltip`` / ``Stats``: overlays, not ``Themed``
      components; they read theme fields directly while painting.
    """
    original = Themed._pick
    calls: list[str] = []

    def counting_pick(self, style, field):
        calls.append(field)
        return original(self, style, field)

    monkeypatch.setattr(Themed, "_pick", counting_pick)

    components = [
        Button("ok"),
        Checkbox("ok"),
        Link("site"),
        Input(),
        Editor(),
        Select([Option("one"), Option("two")]),
        Autocomplete(options=[Option("one"), Option("two")]),
        Radio(["one", "two"]),
        CheckGroup(["one", "two"]),
        Collapsible("title", Text("body")),
        Dialog("title", Text("body"), ["ok"]),
        Diff("a", "b"),
        ProgressBar(0.5),
        Slider(),
        List(["one", "two"]),
        StatusLine(left=["l"], right=["r"]),
        ShortcutBar([("k", "label")]),
        Table(["h"], [["x"]]),
        Tree([TreeNode("root")]),
    ]
    # Positive control: construction really goes through the resolution seam.
    assert calls
    calls.clear()

    for component in components:
        component.render(40)

    assert calls == []

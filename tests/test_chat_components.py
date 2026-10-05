"""The chat band components: Message, ToolBlock, EditBlock.

Each renders a full-width band: one pure padding row above and below the
content, the band style merged from the theme (or the explicit style), and
every row computed from the painting width -- never a re-typed literal.
"""

from dataclasses import replace

from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import ACCENT, ERROR, MUTED, SUCCESS, Style
from mocode_tui.core.theme import DEFAULT_THEME
from mocode_tui.chat.message import Message
from mocode_tui.chat.tools import EditBlock, ToolBlock

MESSAGE_WIDTH = 80
MESSAGE_PAD = " " * MESSAGE_WIDTH  # a pure band padding row: full width, no content
TOOL_WIDTH = 20
TOOL_PAD = " " * TOOL_WIDTH  # a pure band padding row: full width, no content


def _filled(piece: str) -> str:
    """One band row: the leading pad cell, ``piece``, then the fill."""
    row = " " + piece
    return row + " " * (TOOL_WIDTH - len(row))


# --- Message -------------------------------------------------------------------


def test_user_band_at_width_80():
    rows = Message("user", "hello there").render(MESSAGE_WIDTH)
    assert len(rows) == 3  # top padding, content, bottom padding
    assert [row.text for row in rows] == [
        MESSAGE_PAD,
        " hello there" + " " * (MESSAGE_WIDTH - len(" hello there")),
        MESSAGE_PAD,
    ]
    # Every segment of every row carries the band style.
    assert all(seg.style == DEFAULT_THEME.user_bg for row in rows for seg in row.segments)


def test_assistant_and_thinking_have_no_band():
    assert Message("assistant", "hi").render(MESSAGE_WIDTH) == [Line.from_text("hi")]
    (row,) = Message("thinking", "hmm").render(MESSAGE_WIDTH)
    assert row.text == "hmm"
    assert all(seg.style == MUTED.merge(Style(italic=True)) for seg in row.segments)


def test_unknown_role_degrades_to_assistant():
    assert Message("system", "hello").render(MESSAGE_WIDTH) == Message("assistant", "hello").render(
        MESSAGE_WIDTH
    )


def test_style_overrides_the_role_default():
    rows = Message("user", "hi", style=Style(bg="red")).render(6)
    assert all(seg.style == Style(bg="red") for row in rows for seg in row.segments)
    assert [row.text for row in rows] == [" " * 6, " hi   ", " " * 6]


def test_the_band_padding_rows_survive_a_narrow_width():
    # The two padding rows survive every width; no row exceeds it.
    rows = Message("user", "hello").render(1)
    assert len(rows) >= 3
    assert all(row.width <= 1 for row in rows)
    assert all(
        seg.style == DEFAULT_THEME.user_bg for row in (rows[0], rows[-1]) for seg in row.segments
    )
    assert Message("assistant", "hello").render(0) == [Line()]


def test_user_text_area_is_width_minus_two():
    width = 9
    rows = Message("user", "aaa bbb ccc").render(width)
    body = width - 2  # one pad cell per side: the text area the wrap uses

    def fit(piece: str) -> str:
        row = " " + piece  # the leading pad cell, then the wrapped piece
        return row + " " * (width - len(row))  # the fill closes the band

    assert [row.text for row in rows] == [
        " " * width,  # top padding
        fit("aaa bbb"),  # " aaa bbb " -- the piece exactly fills the body
        fit("ccc"),  # " ccc     " -- the fill absorbs what is left
        " " * width,  # bottom padding
    ]
    assert rows[1].segments[0] == Segment(" ", DEFAULT_THEME.user_bg)


# --- ToolBlock / EditBlock -----------------------------------------------------


def test_tool_block_row_structure():
    rows = ToolBlock("$ echo hi", ["hi"], tone="tool", footer="Took 0.1s").render(TOOL_WIDTH)
    assert [row.text for row in rows] == [
        TOOL_PAD,  # top in-band padding
        _filled("$ echo hi"),
        TOOL_PAD,  # body separator
        _filled("hi"),
        TOOL_PAD,  # footer separator
        _filled("Took 0.1s"),
        TOOL_PAD,  # bottom in-band padding
    ]
    # The title is bold (green on the tool band), the footer dim italic --
    # both merged onto the band.
    assert rows[1].segments[1].style == DEFAULT_THEME.tool_bg.merge(SUCCESS).merge(Style(bold=True))
    assert rows[-2].segments[1].style == DEFAULT_THEME.tool_bg.merge(Style(dim=True, italic=True))


def test_tool_block_empty_sections_leave_no_stray_gap():
    assert len(ToolBlock("t", footer="f").render(TOOL_WIDTH)) == 5  # pad, title, blank, footer, pad
    assert len(ToolBlock("t", ["b"]).render(TOOL_WIDTH)) == 5  # pad, title, blank, body, pad
    only = ToolBlock("t").render(TOOL_WIDTH)
    assert len(only) == 3  # pad, title, pad
    assert only[1].text == _filled("t")


def test_tool_block_tones_pick_the_band():
    for tone, band in (("tool", DEFAULT_THEME.tool_bg), ("code", DEFAULT_THEME.code_bg)):
        rows = ToolBlock("t", ["b"], tone=tone, footer="f").render(TOOL_WIDTH)
        assert {seg.style.bg for row in rows for seg in row.segments} == {band.bg}
    for tone in ("plain", "fancy", ""):  # plain and unknown carry no band
        rows = ToolBlock("t", ["b"], tone=tone, footer="f").render(TOOL_WIDTH)
        assert {seg.style.bg for row in rows for seg in row.segments} == {None}
    plain = ToolBlock("t", ["b"], tone="plain", footer="f").render(TOOL_WIDTH)
    assert plain[1].segments[1].style == Style(bold=True)  # emphasis survives


def test_tool_block_padding_rows_are_solid_band_filled():
    rows = ToolBlock("t", ["b"], tone="tool", footer="f").render(TOOL_WIDTH)
    for row in (rows[0], rows[-1]):
        assert row.segments  # a padding row is a real row, not an empty one
        assert all(seg.style == DEFAULT_THEME.tool_bg for seg in row.segments)
        assert row.width == TOOL_WIDTH


def test_edit_block_structure_numbering_and_badge():
    rows = EditBlock("p.py", context=["aa"], removed=["bb"], added=["cc"]).render(TOOL_WIDTH)
    assert [row.text for row in rows] == [
        TOOL_PAD,  # top in-band padding
        _filled("p.py"),
        _filled("1 aa"),
        _filled("-2 bb"),
        _filled("+3 cc (edited)"),
        TOOL_PAD,  # bottom in-band padding
    ]
    # Numbering is continuous across groups; the badge is on the last added row.
    continuous = EditBlock("p", ["c1", "c2"], ["r1"], ["a1", "a2"]).render(40)
    assert [row.text.split(" ")[1] for row in continuous[2:7]] == ["1", "2", "-3", "+4", "+5"]
    assert " (edited)" in continuous[6].text
    badge = next(seg for seg in continuous[6].segments if seg.text == " (edited)")
    assert badge.style == DEFAULT_THEME.code_bg.merge(SUCCESS).merge(Style(bold=True))


def test_edit_block_styles_merge_onto_the_code_band():
    rows = EditBlock("src/app.py", removed=["x"], added=["y"]).render(40)
    assert {seg.style.bg for row in rows for seg in row.segments} == {DEFAULT_THEME.code_bg.bg}
    assert next(s for s in rows[1].segments if s.text == "src/app.py").style == (
        DEFAULT_THEME.code_bg.merge(ACCENT).merge(Style(bold=True))
    )
    assert next(s for s in rows[2].segments if s.text == "-1 ").style == DEFAULT_THEME.code_bg.merge(ERROR)
    assert next(s for s in rows[3].segments if s.text == "+2 ").style == DEFAULT_THEME.code_bg.merge(SUCCESS)
    context = next(s for s in EditBlock("p", context=["aa"]).render(TOOL_WIDTH)[2].segments if s.text == "1 ")
    assert context.style == Style(bg=DEFAULT_THEME.code_bg.bg)  # context prefix is plain on the band


def test_narrow_width_guard():
    for rows in (
        ToolBlock("t", ["b"], footer="f").render(1),
        EditBlock("p", ["c"], ["r"], ["a"]).render(1),
    ):
        assert len(rows) >= 6  # the two padding rows survive
        assert all(row.width <= 1 for row in rows)
    # Degenerate widths collapse the padding rows to empty lines, not to nothing.
    assert ToolBlock("t", ["b"], footer="f").render(0) == [Line()] * 7
    assert EditBlock("p", ["c"], ["r"], ["a"]).render(0) == [Line()] * 6
    # Over-wide content is fit (ellipsized), one row per item -- the caller wraps.
    assert ToolBlock("t", ["a b c d e"]).render(5)[3].text == " a b\u2026"


def test_the_band_resolves_the_theme_once_at_construction():
    injected = Style(bg="#123456")
    theme = replace(DEFAULT_THEME, code_bg=injected)
    rows = EditBlock("p", theme=theme).render(TOOL_WIDTH)
    assert {seg.style.bg for row in rows for seg in row.segments} == {injected.bg}
    # The stored theme back-fills a plain constructor default.
    assert EditBlock("p").render(TOOL_WIDTH)[0].segments[0].style.bg == DEFAULT_THEME.code_bg.bg

    # ``tone`` is a mutable attribute, so the ToolBlock band re-resolves per
    # render against the theme the block was built with.
    tool = ToolBlock("t", ["b"], tone="plain")
    assert tool.render(TOOL_WIDTH)[1].segments[1].style == Style(bold=True)
    tool.tone = "tool"
    assert tool.render(TOOL_WIDTH)[1].segments[1].style.bg == DEFAULT_THEME.tool_bg.bg

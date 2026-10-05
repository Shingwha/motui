"""Tests for mocode_tui.components.tools (ToolBlock / EditBlock).

Contracts (COMPONENTS.md): both blocks fill the width behind a one-cell left
padding and are wrapped in one pure band padding row above and below.
``ToolBlock`` stacks title / blank / body / blank / footer and picks its band
from ``tone`` (``tool`` / ``code`` / ``plain``, unknown degrades to plain);
empty sections leave no stray gap while the padding rows always stay.
``EditBlock`` renders an accent path row, numbered context / ``-`` / ``+``
rows, and a green ``(edited)`` badge on the last added row.
"""

from mocode_tui.components.tools import CODE_BG, TOOL_BG, EditBlock, ToolBlock
from mocode_tui.core.lines import Line
from mocode_tui.core.style import ACCENT, ERROR, SUCCESS, Style


def test_tool_block_row_structure():
    rows = ToolBlock("$ echo hi", ["hi"], tone="tool", footer="Took 0.1s").render(20)
    assert [row.text for row in rows] == [
        " " * 20,  # top in-band padding
        " $ echo hi" + " " * 10,
        " " * 20,
        " hi" + " " * 17,
        " " * 20,
        " Took 0.1s" + " " * 10,
        " " * 20,  # bottom in-band padding
    ]
    # The title is bold (green on the tool band), the footer dim italic --
    # both merged onto the band.
    assert rows[1].segments[1].style == TOOL_BG.merge(SUCCESS).merge(Style(bold=True))
    assert rows[-2].segments[1].style == TOOL_BG.merge(Style(dim=True, italic=True))


def test_tool_block_empty_sections_leave_no_stray_gap():
    assert len(ToolBlock("t", footer="f").render(20)) == 5  # pad, title, blank, footer, pad
    assert len(ToolBlock("t", ["b"]).render(20)) == 5  # pad, title, blank, body, pad
    only = ToolBlock("t").render(20)
    assert len(only) == 3  # pad, title, pad
    assert only[1].text == " t" + " " * 18


def test_tool_block_tones_pick_the_band():
    for tone, band in (("tool", TOOL_BG), ("code", CODE_BG)):
        rows = ToolBlock("t", ["b"], tone=tone, footer="f").render(20)
        assert {seg.style.bg for row in rows for seg in row.segments} == {band.bg}
    for tone in ("plain", "fancy", ""):  # plain and unknown carry no band
        rows = ToolBlock("t", ["b"], tone=tone, footer="f").render(20)
        assert {seg.style.bg for row in rows for seg in row.segments} == {None}
    plain = ToolBlock("t", ["b"], tone="plain", footer="f").render(20)
    assert plain[1].segments[1].style == Style(bold=True)  # emphasis survives


def test_tool_block_padding_rows_are_real_band_rows():
    rows = ToolBlock("t", ["b"], tone="tool", footer="f").render(20)
    for row in (rows[0], rows[-1]):
        assert row.segments  # a padding row is a real row, not an empty one
        assert all(seg.style == TOOL_BG for seg in row.segments)
        assert row.width == 20


def test_edit_block_structure_numbering_and_badge():
    rows = EditBlock("p.py", context=["aa"], removed=["bb"], added=["cc"]).render(20)
    assert [row.text for row in rows] == [
        " " * 20,  # top in-band padding
        " p.py               ",
        " 1 aa               ",
        " -2 bb              ",
        " +3 cc (edited)     ",
        " " * 20,  # bottom in-band padding
    ]
    # Numbering is continuous across groups; the badge is on the last added row.
    continuous = EditBlock("p", ["c1", "c2"], ["r1"], ["a1", "a2"]).render(40)
    assert [row.text.split(" ")[1] for row in continuous[2:7]] == ["1", "2", "-3", "+4", "+5"]
    assert " (edited)" in continuous[6].text
    badge = next(seg for seg in continuous[6].segments if seg.text == " (edited)")
    assert badge.style == CODE_BG.merge(SUCCESS).merge(Style(bold=True))


def test_edit_block_styles_merge_onto_the_code_band():
    rows = EditBlock("src/app.py", removed=["x"], added=["y"]).render(40)
    assert {seg.style.bg for row in rows for seg in row.segments} == {CODE_BG.bg}
    assert next(s for s in rows[1].segments if s.text == "src/app.py").style == (
        CODE_BG.merge(ACCENT).merge(Style(bold=True))
    )
    assert next(s for s in rows[2].segments if s.text == "-1 ").style == CODE_BG.merge(ERROR)
    assert next(s for s in rows[3].segments if s.text == "+2 ").style == CODE_BG.merge(SUCCESS)
    context = next(s for s in EditBlock("p", context=["aa"]).render(20)[2].segments if s.text == "1 ")
    assert context.style == Style(bg=CODE_BG.bg)  # context prefix is plain on the band


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

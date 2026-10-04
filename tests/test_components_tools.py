"""Tests for mocode_tui.components.tools (ToolBlock / EditBlock)."""

import pytest

from mocode_tui.components.tools import CODE_BG, TOOL_BG, EditBlock, ToolBlock
from mocode_tui.lines import Line
from mocode_tui.style import ACCENT, ERROR, SUCCESS, Style


# --- ToolBlock: structure ---------------------------------------------------------


def test_tool_block_row_structure_with_body_and_footer():
    rows = ToolBlock("$ echo hi", ["hi"], tone="tool", footer="Took 0.1s").render(20)
    assert [row.text for row in rows] == [
        " $ echo hi" + " " * 10,
        " " * 20,
        " hi" + " " * 17,
        " " * 20,
        " Took 0.1s" + " " * 10,
    ]
    assert all(row.width == 20 for row in rows)


def test_tool_block_omits_blank_rows_for_empty_sections():
    assert len(ToolBlock("t", footer="f").render(20)) == 3  # title, blank, footer
    assert len(ToolBlock("t", ["b"]).render(20)) == 3  # title, blank, body
    only = ToolBlock("t").render(20)
    assert len(only) == 1  # title only, no stray blanks
    assert only[0].text == " t" + " " * 18
    assert only[0].width == 20
    assert len(ToolBlock("t", body=[], footer="").render(20)) == 1


def test_tool_block_title_and_footer_emphasis_merge_onto_the_band():
    rows = ToolBlock("$ x", ["out"], tone="tool", footer="Took 0.1s").render(20)
    # Palette-agnostic: pinned through the band and semantic constants, so a
    # palette upgrade never reddens these assertions.
    assert rows[0].segments[1].style == TOOL_BG.merge(SUCCESS).merge(Style(bold=True))
    assert rows[-1].segments[1].style == TOOL_BG.merge(Style(dim=True, italic=True))


def test_tool_block_body_rows_are_verbatim_not_wrapped():
    rows = ToolBlock("t", ["a b c d e"]).render(5)
    assert len(rows) == 3  # one row per body item: the caller wraps
    assert rows[2].text == " a b\u2026"


def test_tool_block_over_wide_rows_are_fit():
    rows = ToolBlock("$ " + "x" * 40, ["y" * 40], footer="Took 9.9s").render(12)
    assert len(rows) == 5
    assert all(row.width <= 12 for row in rows)
    assert "\u2026" in rows[0].text


# --- ToolBlock: tones ---------------------------------------------------------------


def test_tool_and_code_tones_carry_their_band():
    for tone, expected in (("tool", "bright_black"), ("code", "black")):
        rows = ToolBlock("t", ["b"], tone=tone, footer="f").render(20)
        assert rows
        assert {seg.style.bg for row in rows for seg in row.segments} == {expected}
    assert TOOL_BG == Style(bg="bright_black")
    assert CODE_BG == Style(bg="black")


def test_plain_and_unknown_tones_carry_no_band():
    for tone in ("plain", "fancy", ""):
        rows = ToolBlock("t", ["b"], tone=tone, footer="f").render(20)
        assert {seg.style.bg for row in rows for seg in row.segments} == {None}
    plain = ToolBlock("t", ["b"], tone="plain", footer="f").render(20)
    assert plain[0].segments[1].style == Style(bold=True)  # title emphasis survives
    assert plain[-1].segments[1].style == Style(dim=True, italic=True)  # footer too


# --- EditBlock ------------------------------------------------------------------------


def test_edit_block_row_structure_numbering_and_badge():
    rows = EditBlock("p.py", context=["aa"], removed=["bb"], added=["cc"]).render(20)
    assert [row.text for row in rows] == [
        " p.py               ",
        " 1 aa               ",
        " -2 bb              ",
        " +3 cc (edited)     ",
    ]
    assert all(row.width == 20 for row in rows)


def test_edit_block_numbering_is_continuous_across_groups():
    rows = EditBlock("p", ["c1", "c2"], ["r1"], ["a1", "a2"]).render(40)
    assert rows[1].text.startswith(" 1 c1")
    assert rows[2].text.startswith(" 2 c2")
    assert rows[3].text.startswith(" -3 r1")
    assert rows[4].text.startswith(" +4 a1")
    assert rows[5].text.startswith(" +5 a2 (edited)")


def test_edit_block_badge_only_on_the_last_added_row():
    rows = EditBlock("p", added=["a", "b"]).render(30)
    assert " (edited)" not in rows[1].text
    assert rows[2].text.startswith(" +2 b (edited)")
    badge = next(seg for seg in rows[2].segments if seg.text == " (edited)")
    assert badge.style == CODE_BG.merge(SUCCESS).merge(Style(bold=True))


def test_edit_block_prefix_and_path_styles():
    rows = EditBlock("src/app.py", removed=["x"], added=["y"]).render(40)
    assert {seg.style.bg for row in rows for seg in row.segments} == {CODE_BG.bg}
    path = next(seg for seg in rows[0].segments if seg.text == "src/app.py")
    assert path.style == CODE_BG.merge(ACCENT).merge(Style(bold=True))  # ACCENT on the band
    removed = next(seg for seg in rows[1].segments if seg.text == "-1 ")
    assert removed.style == CODE_BG.merge(ERROR)  # ERROR on the band
    added = next(seg for seg in rows[2].segments if seg.text == "+2 ")
    assert added.style == CODE_BG.merge(SUCCESS)  # SUCCESS on the band


def test_edit_block_context_prefix_is_plain_on_the_band():
    rows = EditBlock("p", context=["aa"]).render(20)
    prefix = next(seg for seg in rows[1].segments if seg.text == "1 ")
    assert prefix.style == Style(bg="black")


def test_edit_block_empty_removed_and_added():
    rows = EditBlock("p", context=["aa"]).render(20)
    assert len(rows) == 2
    assert rows[1].text.startswith(" 1 aa")
    assert not any("edited" in row.text for row in rows)


def test_edit_block_over_wide_rows_are_fit():
    rows = EditBlock("p" * 50, context=["c" * 50], removed=["r" * 50], added=["a" * 50]).render(10)
    assert all(row.width <= 10 for row in rows)


# --- degenerate widths -----------------------------------------------------------------


def test_tool_block_degenerate_widths():
    rows = ToolBlock("t", ["b"], footer="f").render(0)
    assert rows == [Line()] * 5
    one = ToolBlock("t", ["b"], footer="f").render(1)
    assert len(one) == 5
    assert all(row.width <= 1 for row in one)


def test_edit_block_degenerate_widths():
    block = EditBlock("p", ["c"], ["r"], ["a"])
    assert block.render(0) == [Line()] * 4
    assert all(row.width <= 1 for row in block.render(1))


@pytest.mark.parametrize("width", range(0, 25))
def test_tool_block_rows_never_exceed_width(width):
    rows = ToolBlock("$ echo 日本語", ["out 日本語"], tone="code", footer="Took 0.1s").render(width)
    assert rows
    assert all(row.width <= width for row in rows)


@pytest.mark.parametrize("width", range(0, 25))
def test_edit_block_rows_never_exceed_width(width):
    rows = EditBlock("src/日本語.py", ["ctx 日本語"], ["old 日本語"], ["new 日本語"]).render(width)
    assert rows
    assert all(row.width <= width for row in rows)

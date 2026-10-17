"""Tests for motui.widgets.diff (Diff).

The row kinds (`@@` header, space, `-`, `+`, and the elision row), the
theme bands behind them, hunk merging versus context=0, the empty and
identical degenerate cases, the fit guard, the trimmed walk's real hunk
around a one-line edit, and the whole-region replacement a middle past
``LCS_LIMIT`` with nothing in common degrades to.
"""

from dataclasses import replace

import pytest

from motui.kernel.lines import Segment
from motui.kernel.style import NONE, RESET, Style
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import Diff
from motui.widgets.diff import ELISION, LCS_LIMIT

#: Injected bands: a round trip through the theme fields, never a pinned
#: default color.
DEL_BAND = Style(fg="#aa0000")
INS_BAND = Style(fg="#00aa00")
HUNK_BAND = Style(fg="#555555")
BANDS = {"error": DEL_BAND, "success": INS_BAND, "muted": HUNK_BAND}


def _texts(rows) -> list[str]:
    """The plain texts of an already-rendered row list."""
    return [row.text for row in rows]


def test_the_four_row_kinds_carry_their_prefix_and_band():
    diff = Diff("a\nb\nc", "a\nB\nc", context=0, theme=replace(DEFAULT_THEME, **BANDS))
    rows = diff.render(40)
    assert _texts(rows) == ["@@ -2,1 +2,1 @@", "-b", "+B"]
    header, deleted, inserted = rows
    # The bands are the injected styles' own prefixes -- the `@@` header in
    # muted, the deletion in error, the insertion in success.
    assert header.styled() == HUNK_BAND.prefix() + "@@ -2,1 +2,1 @@" + RESET
    assert deleted.styled() == DEL_BAND.prefix() + "-b" + RESET
    assert inserted.styled() == INS_BAND.prefix() + "+B" + RESET


def test_context_rows_keep_the_default_style_and_the_default_theme_holds():
    rows = Diff("a\nb\nc", "a\nB\nc", context=1).render(40)
    assert _texts(rows) == ["@@ -1,3 +1,3 @@", " a", "-b", "+B", " c"]
    assert all(rows[i].segments[0].style == NONE for i in (1, 4))
    # The shipped theme's fields are what the default resolves to.
    deleted = Diff("x", "y", context=0).render(40)[1]
    assert deleted.styled() == DEFAULT_THEME.error.prefix() + "-x" + RESET


def test_a_kept_line_alone_renders_no_rows():
    assert Diff("a\nb", "a\nb").render(40) == []
    assert Diff("a\n", "a").render(40) == []  # a trailing newline adds no line
    assert Diff("", "").render(40) == []


def test_one_sided_texts_open_and_close_the_file():
    assert _texts(Diff("", "x").render(40)) == ["@@ -0,0 +1,1 @@", "+x"]
    assert _texts(Diff("x", "").render(40)) == ["@@ -1,1 +0,0 @@", "-x"]
    assert _texts(Diff("", "x\ny").render(40)) == ["@@ -0,0 +1,2 @@", "+x", "+y"]


def test_context_zero_tightens_the_hunk_and_keeps_the_numbers_exact():
    before = "\n".join(f"line {i}" for i in range(1, 11))
    after = before.replace("line 2", "LINE 2").replace("line 10", "LINE 10")
    rows = _texts(Diff(before, after, context=0).render(40))
    # Two changes eight lines apart with no context: two hunks and the one
    # elision row between them -- the lines the hunks skip.
    assert rows == [
        "@@ -2,1 +2,1 @@",
        "-line 2",
        "+LINE 2",
        ELISION,
        "@@ -10,1 +10,1 @@",
        "-line 10",
        "+LINE 10",
    ]


def test_close_changes_merge_into_one_hunk_with_the_default_context():
    before = "\n".join(f"line {i}" for i in range(1, 11))
    after = before.replace("line 2", "LINE 2").replace("line 8", "LINE 8")
    rows = _texts(Diff(before, after).render(40))
    # Five kept lines separate the changes: 5 <= 2 * 3, so the context
    # reaches across and the whole file is one hunk -- no elision row.
    assert rows[0] == "@@ -1,10 +1,10 @@"
    assert ELISION not in rows
    assert rows[1] == " line 1" and rows[-1] == " line 10"
    assert rows.count("-line 2") == 1 and rows.count("+LINE 8") == 1


def test_the_elision_row_sits_between_hunks_in_the_muted_band():
    before = "\n".join(f"l{i}" for i in range(1, 13))
    after = before.replace("l2", "L2").replace("l12", "L12")
    rows = Diff(before, after, context=1, theme=replace(DEFAULT_THEME, **BANDS)).render(80)
    elisions = [row for row in rows if row.text == ELISION]
    assert len(elisions) == 1
    assert elisions[0].segments == (Segment(ELISION, HUNK_BAND),)


def test_every_row_is_fitted_to_the_width():
    diff = Diff("short", "a much longer replacement line")
    rows = diff.render(10)
    assert all(row.width <= 10 for row in rows)
    assert rows[-1].text.endswith("\u2026")
    # width <= 0 keeps the row count, every row empty (the fit rule).
    empty = diff.render(0)
    assert len(empty) == len(rows) and all(row.text == "" for row in empty)


def test_negative_context_is_rejected():
    with pytest.raises(ValueError):
        Diff("a", "b", context=-1)


def test_a_region_with_no_shared_line_replaces_itself_in_one_hunk():
    lines = 2000
    before = "\n".join(f"line {i}" for i in range(lines))
    after = "\n".join(f"other {i}()" for i in range(lines))
    assert lines * lines > LCS_LIMIT  # the pair budget really is exceeded
    rows = _texts(Diff(before, after).render(80))
    # The shape is the contract: nothing is shared, so the whole region is
    # replaced -- one hunk, every `-` line and then every `+` line, nothing
    # singled out and nothing skipped.
    assert [text for text in rows if text.startswith("@@")] == ["@@ -1,2000 +1,2000 @@"]
    assert sum(1 for text in rows if text.startswith("-")) == lines
    assert sum(1 for text in rows if text.startswith("+")) == lines
    assert len(rows) == 1 + 2 * lines
    assert ELISION not in rows


def test_unique_lines_anchor_a_big_region_into_three_hunks():
    lines = 500
    before = "\n".join(f"line {i}" for i in range(lines))
    after = before
    for index in (10, 250, 490):
        after = after.replace(f"line {index}\n", f"LINE {index}\n")
    assert lines * lines > LCS_LIMIT  # the pair budget really is exceeded
    rows = _texts(Diff(before, after).render(80))
    # Every untouched line is unique on both sides, so each one is an anchor
    # and the region splits into three small changes -- each with three
    # context lines a side, and the 233 lines between them elided.
    assert len(rows) == 29
    assert [text for text in rows if text.startswith("@@")] == [
        "@@ -8,7 +8,7 @@",
        "@@ -248,7 +248,7 @@",
        "@@ -488,7 +488,7 @@",
    ]
    # Two elision rows sit between the three hunks; the counts they carry
    # (233 skipped lines each) are pinned with the counted row itself.
    assert [text for text in rows if text.startswith("\u2026")] == [ELISION, ELISION]


def test_the_trimmed_walk_turns_a_one_line_edit_into_one_small_hunk():
    lines = 2000
    before = "\n".join(f"line {i}" for i in range(lines))
    after = before.replace("line 1000", "LINE 1000 ONCE")
    assert lines * lines > LCS_LIMIT  # the pair budget really is exceeded
    rows = _texts(Diff(before, after).render(80))
    # The common head and tail never enter a table: the middle is the two
    # lines around the edit, and the hunk is three context lines a side.
    assert len(rows) == 9
    assert [text for text in rows if text.startswith("@@")] == ["@@ -998,7 +998,7 @@"]
    assert rows[4] == "-line 1000" and rows[5] == "+LINE 1000 ONCE"
    assert rows[1:4] == [" line 997", " line 998", " line 999"]
    assert rows[6:] == [" line 1001", " line 1002", " line 1003"]


def test_a_shared_head_and_tail_around_one_change_stays_one_small_hunk():
    before = "\n".join(f"l{i}" for i in range(50))
    after = before.replace("l25", "L25")
    rows = _texts(Diff(before, after, context=2).render(80))
    # Two kept lines on either side, the rest of the 50 lines outside the
    # hunk and not rendered at all (five before lines: two kept, the
    # deleted one and the two kept after the insertion).
    assert rows == ["@@ -24,5 +24,5 @@", " l23", " l24", "-l25", "+L25", " l26", " l27"]


def test_a_modified_line_reads_as_a_deletion_before_its_insertion():
    rows = _texts(Diff("keep\nold\nkeep2", "keep\nnew\nkeep2", context=1).render(40))
    assert rows == ["@@ -1,3 +1,3 @@", " keep", "-old", "+new", " keep2"]

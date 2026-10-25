"""Diff: the line-level unified diff rows and their live inputs."""

import pytest

from motui.kernel.cell import Surface
from motui.kernel.layout import Constraints
from motui.kernel.style import NONE
from motui.kernel.text import WrapMode
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import Diff
from dataclasses import replace

from tests.testing import many, texts


def test_identical_texts_render_no_rows():
    assert list(Diff("a\nb", "a\nb").render(Constraints(width=20))) == []
    assert list(Diff("", "").render(Constraints(width=20))) == []


def test_a_replaced_line_renders_one_hunk_with_its_context():
    diff = Diff("a\nb\nc", "a\nx\nc")
    assert texts(diff, 20) == ["@@ -1,3 +1,3 @@", " a", "-b", "+x", " c"]


def test_context_zero_renders_the_changes_alone():
    assert texts(Diff("a\nb\nc", "a\nx\nc", context=0), 20) == [
        "@@ -2,1 +2,1 @@",
        "-b",
        "+x",
    ]


def test_distant_hunks_are_joined_by_an_elision_row():
    before = many(20)
    after = list(before)
    after[1] = "changed"
    after[17] = "also"
    rows = texts(Diff("\n".join(before), "\n".join(after), context=1), 40)
    assert sum(row.startswith("@@") for row in rows) == 2
    assert any(row.startswith("\u2026") and "lines" in row for row in rows)


def test_line_numbers_right_align_in_one_gutter():
    diff = Diff("a\nb", "a\nx", numbers=True)
    assert texts(diff, 20) == ["@@ -1,2 +1,2 @@", "1  a", "2 -b", "2 +x"]
    assert texts(Diff("a\nb", "a\nx"), 20)[1] == " a"


def test_assignment_rebuilds_the_rows_and_rejects_a_negative_context():
    diff = Diff("a\nb", "a\nb")
    diff.after = "a\nc"
    assert texts(diff, 20) == ["@@ -1,2 +1,2 @@", " a", "-b", "+c"]
    diff.before = "z\nb"
    assert "-z" in texts(diff, 20) and "+a" in texts(diff, 20)
    with pytest.raises(ValueError):
        diff.context = -1


def test_the_diff_bands_carry_the_theme_roles():
    rows = Diff("a\nb\nc", "a\nx\nc").render(Constraints(width=20))
    styles = {row.text: row.segments[0].style for row in rows}
    deletion = replace(DEFAULT_THEME.status.danger, bold=False)
    assert styles["-b"] == deletion
    assert styles["-b"].bold is False
    assert styles["+x"] == DEFAULT_THEME.status.success
    assert styles["@@ -1,3 +1,3 @@"] == DEFAULT_THEME.text.muted
    assert styles[" a"] == NONE


@pytest.mark.parametrize(
    "before, after, expected",
    [
        ("", "a\nb", ["@@ -0,0 +1,2 @@", "+a", "+b"]),
    ],
)
def test_a_one_sided_diff_renders_one_hunk(before, after, expected):
    assert texts(Diff(before, after), 20) == expected
    assert texts(Diff("a\nb", ""), 20) == ["@@ -1,2 +0,0 @@", "-a", "-b"]


# -- the 2.0 render contract -------------------------------------------------


def test_a_diff_takes_constraints_and_honours_the_height_budget():
    diff = Diff("a\nb\nc", "a\nx\nc")
    assert isinstance(diff.render(Constraints(width=20)), Surface)
    assert diff.render(Constraints(width=20)) == diff.render(Constraints(width=20))
    surface = diff.render(Constraints(width=20, max_height=2))
    assert [row.text for row in surface] == ["@@ -1,3 +1,3 @@", " a"]
    assert list(diff.render(Constraints(width=20, max_height=0))) == []


def test_the_diff_cache_keys_on_the_width_not_the_height_budget():
    diff = Diff("a\nb\nc", "a\nx\nc")
    diff.render(Constraints(width=20, max_height=1))
    assert diff.render(Constraints(width=20)).height == 5
    assert all(row.width <= 20 for row in diff.render(Constraints(width=20)))


def test_wrap_selects_how_a_long_diff_line_fits():
    before, after = "x" * 30, "y" * 30
    default = texts(Diff(before, after, context=0), 20)
    assert default[-1] == "+" + "y" * 18 + "\u2026"

    clip = texts(Diff(before, after, context=0, wrap=WrapMode.CLIP), 20)
    assert clip[-1] == "+" + "y" * 19
    assert not any("\u2026" in row for row in clip)

    wrapped = texts(
        Diff("hello world hello world", "", context=0, wrap=WrapMode.WORD), 12
    )
    assert len(wrapped) > 2 and all(len(row) <= 12 for row in wrapped)

    # OVERFLOW keeps every row whole and hands its natural width out for a
    # horizontal scroll container to window.
    overflow = Diff(before, after, context=0, wrap=WrapMode.OVERFLOW)
    surface = overflow.render(Constraints(width=20))
    assert surface.width == 31  # "+" + the 30-character insertion
    assert surface[-1].text == "+" + "y" * 30
    assert all(row.width <= surface.width for row in surface)
    # The height budget still truncates the natural-width surface.
    budgeted = overflow.render(Constraints(width=20, max_height=1))
    assert budgeted.width == 31 and budgeted.height == 1
    assert list(budgeted)[0].text.startswith("@@")


def test_wrap_is_part_of_the_render_key_and_touches():
    plain = Diff("a" * 30, "b" * 30)
    clipped = Diff("a" * 30, "b" * 30, wrap=WrapMode.CLIP)
    assert list(plain.render(Constraints(width=20))) != list(
        clipped.render(Constraints(width=20))
    )
    assert list(plain.render(Constraints(width=20))) == list(
        plain.render(Constraints(width=20))
    )
    before = plain.generation
    plain.wrap = WrapMode.CLIP
    assert plain.generation > before

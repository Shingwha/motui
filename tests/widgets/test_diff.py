"""Diff: the line-level unified diff rows and their live inputs."""

import pytest

from motui.kernel.style import NONE
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import Diff
from dataclasses import replace

from tests.testing import many, texts


def test_identical_texts_render_no_rows():
    assert Diff("a\nb", "a\nb").render(20) == []
    assert Diff("", "").render(20) == []


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
    rows = Diff("a\nb\nc", "a\nx\nc").render(20)
    styles = {row.text: row.segments[0].style for row in rows}
    deletion = replace(DEFAULT_THEME.error, bold=False)
    assert styles["-b"] == deletion
    assert styles["-b"].bold is False
    assert styles["+x"] == DEFAULT_THEME.success
    assert styles["@@ -1,3 +1,3 @@"] == DEFAULT_THEME.muted
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

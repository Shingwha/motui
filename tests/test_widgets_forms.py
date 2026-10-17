"""The form widgets: ``Collapsible``.

The foldable section, asserted as its own contract: the state it holds,
the controller methods a host routes (and the ``chosen`` value each writes
for a single read), the row-level ``hover_at`` marking that must render zero
extra bytes when it cleared, and the focus band that must be told apart from
the plain render.  The choice presets (``Radio`` / ``CheckGroup``) are
exercised beside their base in ``test_widgets_choice.py``, the value
indicators (``Slider`` / ``ProgressBar`` / ``Spinner``) in
``test_widgets_indicators.py``, and the rows (``ShortcutBar`` /
``StatusLine`` / ``Notice``) in ``test_widgets_rows.py``.
"""

from __future__ import annotations

import pytest

from _doubles import texts

from motui.kernel import Component
from motui.kernel.block import Activable, Clickable
from motui.kernel.lines import Segment
from motui.kernel.lines import Text
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME, Theme
from motui.widgets import Collapsible

#: Injected styles: they flow back out of the render equal.
SELECTED = Style(fg="#abcdef")
PLAIN = Style(fg="#123456")
HOVER = Style(italic=True)
FOCUS = Style(underline=True)




# --- Collapsible -----------------------------------------------------------------


def test_collapsible_folds_its_body_away_and_back():
    section = Collapsible("options", Text("body one\nbody two"))
    rows = section.render(20)
    assert [row.text for row in rows] == ["\u25be options", "  body one", "  body two"]
    assert rows[0].segments == (
        Segment("\u25be ", DEFAULT_THEME.accent),
        Segment("options", DEFAULT_THEME.accent),
    )
    assert section.open is True
    section.open = False  # a host may set the state directly
    assert [row.text for row in section.render(20)] == ["\u25b8 options"]
    assert isinstance(section, Component)


def test_collapsible_click_and_activate_are_the_same_flip():
    section = Collapsible("options", Text("body"))
    assert isinstance(section, Clickable) and isinstance(section, Activable)
    assert section.chosen is None
    assert section.activate() is True
    assert (section.open, section.chosen) == (False, False)
    section.chosen = None  # the host reads once and resets
    expected = True
    for col in (0, 3, 40):  # the title row owns the whole width; each hit flips it
        assert section.click(0, col) is True
        assert section.open is expected and section.chosen is expected
        section.chosen = None
        expected = not expected
    for row in (-1, 1, 9):  # a body row or a cell past the render is not the control
        assert section.click(row, 0) is False and section.chosen is None
    assert section.open is True  # the misses never flipped it


def test_collapsible_marks_the_title_row_and_clears_back():
    section = Collapsible(
        "options", Text("body"), title_style=SELECTED, hover_style=HOVER
    )
    plain = section.render(20)
    assert section.hover_at(0, 2) is True
    marked = section.render(20)
    assert marked[0].segments[0].style == SELECTED.merge(HOVER)
    assert marked[0].segments[1].style == SELECTED.merge(HOVER)
    assert marked[1] == plain[1]  # the body row is untouched
    assert section.hover_at(0, 0) is False  # the same row: nothing to repaint
    assert section.hover_at(1, 0) is True  # a body row carries no marking
    assert section.render(20) == plain  # byte-for-byte the un-hovered rows
    assert section.hover_at(-1, -1) is False  # nothing was marked: no change


def test_collapsible_focus_band_is_told_apart_from_the_plain_render():
    styles = dict(title_style=SELECTED, focus_style=FOCUS)
    plain = Collapsible("options", Text("body"), **styles).render(20)
    focused = Collapsible("options", Text("body"), focused=True, **styles).render(20)
    assert focused[0].segments[0].style == SELECTED.merge(FOCUS)
    assert focused[1] == plain[1]  # the body keeps its own styles
    assert plain[0].segments[0].style == SELECTED


def test_collapsible_nested_content_stays_inside_the_width():
    nested = Collapsible(
        "outer",
        Collapsible("inner", Text("a long body line that has to wrap inside the section")),
    )
    for row in nested.render(24):
        assert row.width <= 24
    assert [row.text for row in nested.render(24)][:2] == [
        "\u25be outer",
        "  \u25be inner",
    ]
    # a body wider than the painting width truncates through fit, marker and all
    narrow = Collapsible("a-title-that-is-far-too-long", Text("body")).render(4)
    assert narrow[0].width == 4 and narrow[0].text.endswith("\u2026")

"""The default-theme invariant (D5): the library paints structure and position.

Under :data:`~motui.kernel.theme.DEFAULT_THEME` the toolkit paints **zero
``bg``** and **no ``reverse``** outside two documented carve-outs.  That is
the machine-checkable form of "the default never surprises": a transparent
terminal, a light terminal and a custom theme are all safe, because the
default assumes no background of its own -- the band family (``ground``,
``ground_active``, ``hover``) is the host's to theme, and feedback is the
host's to paint.

The two carve-outs (D2) are **position and text semantics, not feedback**,
and each is pinned as the documented exception rather than left implicit:

* the **caret cell** -- the insertion point's one cell, the only
  terminal-independent way to show it, so a text field without a caret is
  not a text field;
* a **focused control's focus band** -- the keyboard position signal, which
  predates this taxonomy and which mocode's dialog buttons sit on.

The third, a **text selection's band**, is *not* asserted here: the
selection tests in ``test_widgets_editing.py`` already pin it (they theme
``selection`` explicitly), and duplicating them would only risk the two
drifting apart.  They are named in
:func:`test_the_selection_band_is_asserted_by_the_editing_tests`.

What is covered here:

* the **row family** -- ``List``, ``Tree``, ``Table``, ``NavList``,
  ``Select``, ``Radio``, ``CheckGroup``;
* the **hover consumers** -- ``Button``, ``Link``, ``Checkbox``,
  ``Collapsible``, ``Tabs``, ``Text``, ``Markdown``, ``Input``, ``Editor``;

each in its default state (resting, unfocused, un-hovered) and, for the row
family, in every engaged state too -- the cursor row, the pointer-hovered
row and the marked rows -- because those are exactly the states whose band
used to be reverse video and now must paint nothing.
"""

from dataclasses import replace

from motui import (
    DEFAULT_THEME,
    Button,
    Checkbox,
    Editor,
    Input,
    Link,
    List,
    Markdown,
    NavList,
    Option,
    Select,
    Table,
    Tabs,
    Text,
    Tree,
)
from motui.kernel.style import NONE, Style
from motui.widgets import CheckGroup, Collapsible, Radio, TreeNode

#: The painting width every case renders at: wide enough that no row is
#: truncated, narrow enough to stay a realistic pane.
WIDTH = 40


def _listed() -> List:
    """A list with a window, a counter below and three items to rest on."""
    return List(["alpha", "beta", "gamma", "delta", "epsilon"], window=3)


def _treed() -> Tree:
    """A tree with an expanded branch: a parent row and two leaf rows."""
    return Tree(
        [TreeNode("src", [TreeNode("app.py"), TreeNode("lib")], expanded=True)]
    )


def _tabled() -> Table:
    """A grid with a header, a rule and two data rows."""
    return Table(["name", "value"], [["alpha", "1"], ["beta", "2"]])


def _unfocused_tabled() -> Table:
    """A grid whose row cursor is set while the table is unfocused.

    The unfocused rule merges the theme's ``dim`` onto the cursor row's
    band; ``dim`` is an attribute, not a background, so the row must still
    paint no ``bg`` and no ``reverse``.
    """
    table = Table(["name", "value"], [["alpha", "1"]], focused=False)
    table.index = 0
    return table


def _selected() -> Select:
    """A menu with a title row, a description column and a window."""
    return Select(
        [Option("one", description="first"), Option("two", description="second")],
        title="pick",
    )


#: One builder per component under test: ``(name, factory)``, the factory
#: fresh each time so no case inherits another's state.  Every one is in its
#: **default** state -- resting, unfocused, un-hovered -- which is what the
#: invariant is about.
DEFAULT_CASES = (
    ("List", _listed),
    ("Tree", _treed),
    ("Table", _tabled),
    ("NavList", lambda: NavList(["overview", "text", "layout"])),
    ("Select", _selected),
    ("Radio", lambda: Radio(["one", "two", "three"])),
    ("CheckGroup", lambda: CheckGroup(["x", "y", "z"], marked=(1,))),
    ("Button", lambda: Button("Ship it")),
    ("Link", lambda: Link("Read the README")),
    ("Checkbox", lambda: Checkbox("Trace")),
    ("Collapsible", lambda: Collapsible("a foldable section", Text("body"))),
    ("Tabs", lambda: Tabs(["one", "two", "three"])),
    ("Text", lambda: Text("a paragraph of plain text")),
    (
        "Markdown",
        lambda: Markdown("# Title\n\nA paragraph with **bold** and `code`.\n\n- item"),
    ),
    (
        "Input",
        lambda: _filled(Input(), "hello"),
    ),
    (
        "Editor",
        lambda: Editor(text="line one\nline two"),
    ),
)


#: One builder per **engaged** state of the row family: the cursor row, the
#: pointer-hovered row and the marked rows.  These are the states whose band
#: was reverse video before D1 and must now paint nothing.
ENGAGED_CASES = (
    ("List cursor", lambda: _listed()),
    ("List hovered", lambda: _hovered(_listed(), 1)),
    ("Tree cursor", lambda: _treed()),
    ("Tree hovered", lambda: _hovered(_treed(), 1)),
    ("Table cursor", lambda: _indexed(_tabled(), 1)),
    ("Table hovered", lambda: _hovered(_tabled(), 5)),
    ("NavList active", lambda: NavList(["one", "two", "three"])),
    ("NavList hovered", lambda: _hovered(NavList(["one", "two", "three"]), 2)),
    ("Select cursor", lambda: _selected()),
    ("Select hovered", lambda: _hovered(_selected(), 1)),
    ("Radio cursor", lambda: Radio(["one", "two", "three"])),
    ("Radio hovered", lambda: _hovered(Radio(["one", "two", "three"]), 2)),
    ("CheckGroup cursor", lambda: CheckGroup(["x", "y"], marked=(0,))),
    ("CheckGroup hovered", lambda: _hovered(CheckGroup(["x", "y"]), 1)),
    ("Table unfocused cursor", _unfocused_tabled),
)


def _filled(field: Input, text: str) -> Input:
    """An ``Input`` with content, so the caret sits inside the row."""
    field.insert(text)
    return field


def _indexed(table: Table, index: int) -> Table:
    """A table with its row cursor on ``index``."""
    table.index = index
    return table


def _hovered(component, row: int):
    """A component with the pointer marked on ``row``."""
    component.hover_at(row, 0)
    return component


def _painted(component) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """``(bg segments, reverse segments)`` of one component's whole render.

    Each entry is ``(row index, the segment's text)``, so a failure names
    both the row and the cell that painted.  ``bg`` is read as "the style
    sets a background colour at all" -- an attribute-only ``reverse`` has
    no ``bg`` of its own, which is why the two lists are collected apart.
    """
    backgrounds: list[tuple[int, str]] = []
    reverses: list[tuple[int, str]] = []
    for row_index, row in enumerate(component.render(WIDTH)):
        for segment in row.segments:
            if segment.style.bg is not None:
                backgrounds.append((row_index, segment.text))
            if segment.style.reverse:
                reverses.append((row_index, segment.text))
    return backgrounds, reverses


def test_the_default_theme_paints_no_background_at_all():
    """Zero ``bg`` on every segment of every default render -- D1's core."""
    for name, factory in DEFAULT_CASES:
        backgrounds, _ = _painted(factory())
        assert backgrounds == [], f"{name}: a default render painted a bg"


def test_the_default_theme_paints_no_reverse_outside_the_caret_cell():
    """Zero ``reverse`` except the caret cell of ``Input`` / ``Editor`` -- D5.

    The caret is the D2 carve-out: one reversed cell per text field, on the
    row the cursor sits on.  Every other component -- the row family and the
    hover consumers alike -- paints no reverse at all in its default state.
    """
    for name, factory in DEFAULT_CASES:
        _, reverses = _painted(factory())
        if name in ("Input", "Editor"):
            # The one documented exception: the insertion point's own cell.
            assert len(reverses) == 1, f"{name}: expected the caret cell alone"
            continue
        assert reverses == [], f"{name}: a default render painted reverse"


def test_the_engaged_rows_paint_nothing_either():
    """The cursor row, the hovered row and the marks are clean too -- D1.

    These are the states whose band *was* reverse video: the registered
    1.1.8 default.  With the band family at ``NONE`` they paint the very
    same bytes as at rest, which is what makes a transparent terminal and a
    light terminal safe.  A host that themes the band still gets it -- that
    is the themed case, asserted in the widget tests and probed in the A/B.
    """
    for name, factory in ENGAGED_CASES:
        backgrounds, reverses = _painted(factory())
        assert backgrounds == [], f"{name}: an engaged row painted a bg"
        assert reverses == [], f"{name}: an engaged row painted reverse"


def test_a_focused_control_paints_the_focus_band():
    """The focus carve-out (D2): a *focused* control paints ``focus``.

    The keyboard position signal, which predates this taxonomy and which
    mocode's dialog buttons sit on -- so it keeps its default.  The same
    band is what the unfocused row family must *not* paint: only the
    control's own focus flag raises it.
    """
    focused = Button("Ship it", focused=True)
    backgrounds, reverses = _painted(focused)
    assert reverses == [(0, " Ship it ")]  # the whole row is the focus band
    assert backgrounds == []  # reverse is an attribute, not a background
    assert DEFAULT_THEME.focus == Style(reverse=True)
    # The resting button paints nothing: the flag alone raises the band.
    assert _painted(Button("Ship it")) == ([], [])
    # ... and the band is the theme's, so a host can restyle it.
    retitled = replace(DEFAULT_THEME, focus=Style(underline=True))
    assert _painted(Button("Ship it", focused=True, theme=retitled)) == ([], [])


def test_the_caret_cell_is_the_themes_own_block():
    """The caret carve-out (D2): the one cell is the theme's ``caret`` style.

    Not a band a host could confuse with feedback: an attribute-only
    reverse, no background of its own, exactly one cell per text field --
    ``Input`` on its single row, ``Editor`` on the row the cursor sits on.
    """
    assert DEFAULT_THEME.caret == Style(reverse=True)
    assert DEFAULT_THEME.caret.bg is None
    for name, factory in (
        ("Input", lambda: _filled(Input(), "hello")),
        ("Editor", lambda: Editor(text="line one\nline two")),
    ):
        _, reverses = _painted(factory())
        assert len(reverses) == 1, f"{name}: the caret is one cell"


def test_the_selection_band_is_asserted_by_the_editing_tests():
    """The third carve-out (D2) lives in the editing tests, not here.

    A text selection paints the ``selection`` band -- the selection's own
    semantics, kept on purpose.  ``test_widgets_editing.py`` pins it against
    an explicitly themed ``selection``, and re-asserting it here would only
    give the two a chance to drift.  This case therefore checks the *wiring*
    the default needs -- the theme field is the one the tests theme, and it
    is a band a default render only raises for a selection -- and names the
    tests that own the assertion.
    """
    assert DEFAULT_THEME.selection == Style(reverse=True)
    assert DEFAULT_THEME.selection.bg is None
    # A field with no selection paints no selection band of its own.
    field = _filled(Input(), "hello")
    assert _painted(field) == ([], [(0, " ")])  # the caret cell alone
    # The owners of the selection assertion, for the record.
    owners = (
        "test_the_selection_renders_the_band_over_the_prompted_row",
        "test_the_selection_outranks_the_cursor_on_a_cell_they_share",
        "test_the_selection_band_renders_in_an_unfocused_field_without_a_cursor",
        "test_a_selection_spans_the_rendered_rows",
    )
    assert len(owners) == 4


def test_the_default_theme_fields_the_invariant_reads():
    """The three fields the invariant is written against, pinned directly.

    The band family is ``NONE`` (D1) and the carve-outs keep their values
    (D2) -- so a future edit that re-inlines a default here turns this case
    red before it can turn a render surprising.
    """
    assert DEFAULT_THEME.ground is NONE
    assert DEFAULT_THEME.ground_active is NONE
    assert DEFAULT_THEME.hover is NONE
    assert DEFAULT_THEME.caret == Style(reverse=True)
    assert DEFAULT_THEME.focus == Style(reverse=True)
    assert DEFAULT_THEME.selection == Style(reverse=True)

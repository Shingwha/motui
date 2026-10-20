"""The glyph-vocabulary contract matrix: six components, five scenarios.

The rows' glyphs are content and each component takes them as keyword-only
parameters.  This matrix pins the same five properties for every row
component at once, on ``Line`` segments and display widths:

1. **default bytes** -- building with the vocabulary constants named
   explicitly renders exactly the bytes a plain construction does;
2. **custom** -- a host's glyph reaches the row as content;
3. **empty collapse** -- ``""`` disables the glyph and its whole seat,
   leaving no dangling separator;
4. **wide (CJK)** -- seats are measured by ``visible_width``, so a
   two-column glyph widens every row's column and labels stay aligned;
5. **pair alignment** -- the two states of a pair (cursor/indent,
   marked/unmarked, open/closed, bar/blank, filled/empty) share one column.

The cases cover the ticket's six components; the choice family contributes
its three classes (``Select``, ``RadioGroup``, ``CheckboxGroup``), each pinned
separately because their row geometry differs.
"""

from dataclasses import dataclass
from typing import Callable

import pytest

from motui.kernel import glyphs
from motui.kernel.lines import Line
from motui.kernel.text import visible_width
from motui.widgets.choice import CheckboxGroup, Option, RadioGroup, Select
from motui.widgets.list import List
from motui.widgets.navlist import NavList
from motui.widgets.table import Table
from motui.widgets.tree import Tree, TreeNode

WIDTH = 30


def _texts(rows: list[Line]) -> tuple[str, ...]:
    return tuple(row.text for row in rows)


def _label_columns(rows: list[Line], labels: tuple[str, ...]) -> tuple[int, ...]:
    """The display column each label starts at, per row."""
    return tuple(
        visible_width(row.text[: row.text.index(label)])
        for row, label in zip(rows, labels)
    )


def _seat_widths(rows: list[Line], segment: int) -> tuple[int, ...]:
    """The display width of one segment in every row."""
    return tuple(visible_width(row.segments[segment].text) for row in rows)


def _table_head_width(row: Line, label: str) -> int:
    """The display width between a table row's left frame and its label."""
    return visible_width(row.text[2 : row.text.index(label)])


def _tree_sample() -> list[TreeNode]:
    return [
        TreeNode(
            "src",
            children=[
                TreeNode("app.py"),
                TreeNode("lib", children=[TreeNode("a.py")]),
            ],
        )
    ]


# --- the case factories --------------------------------------------------------------


def _list_custom() -> List:
    lst = List(["alpha", "beta"], window=2, marker=">", mark_pair=("[X]", "[ ]"))
    lst.toggle()
    return lst


def _list_empty() -> List:
    return List(
        ["alpha", "beta"],
        window=1,
        marker="",
        more_up="",
        more_down="",
        mark_pair=("", ""),
    )


def _list_wide() -> List:
    return List(["alpha", "beta"], window=2, marker="\u6811")


def _list_pair() -> List:
    lst = List(["alpha", "beta"], window=2, mark_pair=("\u6811", ""))
    lst.toggle()
    return lst


def _check_group_custom() -> CheckboxGroup:
    return CheckboxGroup(["one", "two"], marked=(0,), mark_pair=("[X]", "[ ]"))


def _check_group_empty() -> CheckboxGroup:
    return CheckboxGroup(["one", "two"], marked=(0,), mark_pair=("", ""))


def _check_group_wide() -> CheckboxGroup:
    return CheckboxGroup(
        ["one", "two"], marked=(0,), mark_pair=("\u6811", "\u662f")
    )


def _radio_wide() -> RadioGroup:
    return RadioGroup(["one", "two"], empty="( )", filled="\u6811")


def _tree_custom() -> Tree:
    tree = Tree(_tree_sample(), expanded="v", collapsed=">")
    tree.activate()
    return tree


def _tree_empty() -> Tree:
    tree = Tree(_tree_sample(), expanded="", collapsed="")
    tree.activate()
    return tree


def _tree_wide() -> Tree:
    tree = Tree(_tree_sample(), expanded="\u5f00", collapsed="\u5173")
    tree.activate()
    return tree


def _table_custom() -> Table:
    table = Table(["name"], [["alpha"], ["beta"]], mark_pair=("[X]", "[ ]"))
    table.index = 0
    table.toggle()
    return table


def _table_empty() -> Table:
    table = Table(["name"], [["alpha"], ["beta"]], mark_pair=("", ""))
    table.index = 0
    table.toggle()
    return table


def _table_wide() -> Table:
    table = Table(["name"], [["alpha"], ["beta"]], mark_pair=("\u6811", ""))
    table.index = 0
    table.toggle()
    return table


# --- the checks ----------------------------------------------------------------------


def _list_custom_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("> [X] alpha", "  [ ] beta")


def _list_empty_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("alpha", "1 more")
    assert rows[0].segments[0].text == ""  # the zero-width marker seat
    assert rows[1].text == "1 more"  # the counter's empty seat leaves no space


def _list_wide_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("\u6811 alpha", "   beta")
    assert _label_columns(rows, ("alpha", "beta")) == (3, 3)


def _list_pair_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("\u25b8 \u6811 alpha", "     beta")
    assert _seat_widths(rows, 1) == (3, 3)  # marked and unmarked share one seat


def _select_custom_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("> one", "  two")


def _select_empty_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("one", "two")
    assert _seat_widths(rows, 0) == (0, 0)  # no dangling separator


def _select_wide_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("\u6811 one", "   two")
    assert _label_columns(rows, ("one", "two")) == (3, 3)


def _select_pair_check(rows: list[Line]) -> None:
    assert _seat_widths(rows, 0) == (3, 3)  # cursor seat and indent share one width


def _radio_custom_check(rows: list[Line]) -> None:
    assert _texts(rows) == (">   one", "( ) two")  # ">" padded to the pair's width


def _radio_empty_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("one", "two")
    assert _seat_widths(rows, 0) == (0, 0)


def _radio_wide_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("\u6811  one", "( ) two")
    assert _label_columns(rows, ("one", "two")) == (4, 4)


def _radio_pair_check(rows: list[Line]) -> None:
    assert _seat_widths(rows, 0) == (4, 4)  # filled and empty share one column


def _check_group_custom_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("\u2192 [X] one", "  [ ] two")


def _check_group_empty_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("\u2192 one", "  two")
    assert _seat_widths(rows, 1) == (0, 0)


def _check_group_wide_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("\u2192 \u6811 one", "  \u662f two")
    assert _label_columns(rows, ("one", "two")) == (5, 5)


def _check_group_pair_check(rows: list[Line]) -> None:
    assert _seat_widths(rows, 1) == (3, 3)


def _navlist_custom_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("> one", "  two")


def _navlist_empty_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("one", "two")
    assert _seat_widths(rows, 0) == (0, 0)


def _navlist_wide_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("\u6811 one", "   two")
    assert _label_columns(rows, ("one", "two")) == (3, 3)


def _navlist_pair_check(rows: list[Line]) -> None:
    assert _seat_widths(rows, 0) == (2, 2)  # bar column and blank column


def _tree_custom_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("v src", "    app.py", "  > lib")


def _tree_empty_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("src", "  app.py", "  lib")


def _tree_wide_check(rows: list[Line]) -> None:
    assert _texts(rows) == ("\u5f00 src", "     app.py", "  \u5173 lib")
    assert _label_columns(rows, ("src", "app.py", "lib")) == (3, 5, 5)


def _tree_pair_check(rows: list[Line]) -> None:
    # The indicator column is the pair's seat: 3 columns at depth 0 and at
    # depth 1 alike (the guide is the difference).
    head = rows[0].segments[0].text[: rows[0].segments[0].text.index("src")]
    assert visible_width(head) == 3
    assert visible_width(rows[1].segments[0].text) - 2 == 3
    assert visible_width(rows[2].segments[0].text) - 2 == 3


def _table_custom_check(rows: list[Line]) -> None:
    assert any("[X] alpha" in row.text for row in rows)
    assert any("[ ] beta" in row.text for row in rows)
    assert len({row.width for row in rows}) == 1
    for label in ("alpha", "beta"):
        row = next(r for r in rows if label in r.text)
        assert _table_head_width(row, label) == 4  # the pair's wider seat


def _table_empty_check(rows: list[Line]) -> None:
    plain = Table(["name"], [["alpha"], ["beta"]]).render(WIDTH)
    assert [row.styled() for row in rows] == [row.styled() for row in plain]


def _table_wide_check(rows: list[Line]) -> None:
    assert any("\u6811 alpha" in row.text for row in rows)
    assert any("   beta" in row.text for row in rows)
    assert _table_head_width(next(r for r in rows if "alpha" in r.text), "alpha") == 3
    assert _table_head_width(next(r for r in rows if "beta" in r.text), "beta") == 3


def _table_pair_check(rows: list[Line]) -> None:
    # The marked and unmarked rows put their labels at the same in-cell
    # column (the pair's wider seat).
    assert _table_head_width(next(r for r in rows if "alpha" in r.text), "alpha") == 3
    assert _table_head_width(next(r for r in rows if "beta" in r.text), "beta") == 3


# --- the matrix ----------------------------------------------------------------------


@dataclass(frozen=True)
class Case:
    """One row component and the five scenarios' fixtures and checks."""

    name: str
    plain: Callable[[], object]
    explicit: Callable[[], object]
    custom: Callable[[], object]
    custom_check: Callable[[list[Line]], None]
    empty: Callable[[], object]
    empty_check: Callable[[list[Line]], None]
    wide: Callable[[], object]
    wide_check: Callable[[list[Line]], None]
    pair: Callable[[], object]
    pair_check: Callable[[list[Line]], None]


CASES = (
    Case(
        "List",
        plain=lambda: List(["alpha", "beta"], window=2),
        explicit=lambda: List(
            ["alpha", "beta"],
            window=2,
            marker=glyphs.CURSOR,
            more_up=glyphs.MORE_UP,
            more_down=glyphs.MORE_DOWN,
            mark_pair=(glyphs.MARKED, glyphs.UNMARKED),
        ),
        custom=_list_custom,
        custom_check=_list_custom_check,
        empty=_list_empty,
        empty_check=_list_empty_check,
        wide=_list_wide,
        wide_check=_list_wide_check,
        pair=_list_pair,
        pair_check=_list_pair_check,
    ),
    Case(
        "Select",
        plain=lambda: Select([Option("one"), Option("two")]),
        explicit=lambda: Select(
            [Option("one"), Option("two")],
            marker=glyphs.MENU_CURSOR,
            mark_pair=(glyphs.MARKED, glyphs.UNMARKED),
        ),
        custom=lambda: Select([Option("one"), Option("two")], marker=">"),
        custom_check=_select_custom_check,
        empty=lambda: Select([Option("one"), Option("two")], marker=""),
        empty_check=_select_empty_check,
        wide=lambda: Select([Option("one"), Option("two")], marker="\u6811"),
        wide_check=_select_wide_check,
        pair=lambda: Select([Option("one"), Option("two")], marker="\u6811"),
        pair_check=_select_pair_check,
    ),
    Case(
        "RadioGroup",
        plain=lambda: RadioGroup(["one", "two"]),
        explicit=lambda: RadioGroup(
            ["one", "two"], empty=glyphs.RADIO_EMPTY, filled=glyphs.RADIO_FILLED
        ),
        custom=lambda: RadioGroup(["one", "two"], empty="( )", filled=">"),
        custom_check=_radio_custom_check,
        empty=lambda: RadioGroup(["one", "two"], empty="", filled=""),
        empty_check=_radio_empty_check,
        wide=_radio_wide,
        wide_check=_radio_wide_check,
        pair=_radio_wide,
        pair_check=_radio_pair_check,
    ),
    Case(
        "CheckboxGroup",
        plain=lambda: CheckboxGroup(["one", "two"]),
        explicit=lambda: CheckboxGroup(
            ["one", "two"], mark_pair=(glyphs.MARKED, glyphs.UNMARKED)
        ),
        custom=_check_group_custom,
        custom_check=_check_group_custom_check,
        empty=_check_group_empty,
        empty_check=_check_group_empty_check,
        wide=_check_group_wide,
        wide_check=_check_group_wide_check,
        pair=_check_group_wide,
        pair_check=_check_group_pair_check,
    ),
    Case(
        "NavList",
        plain=lambda: NavList(["one", "two"]),
        explicit=lambda: NavList(["one", "two"], bar=glyphs.RAIL_BAR),
        custom=lambda: NavList(["one", "two"], bar=">"),
        custom_check=_navlist_custom_check,
        empty=lambda: NavList(["one", "two"], bar=""),
        empty_check=_navlist_empty_check,
        wide=lambda: NavList(["one", "two"], bar="\u6811"),
        wide_check=_navlist_wide_check,
        pair=lambda: NavList(["one", "two"], bar="\u6811"),
        pair_check=_navlist_pair_check,
    ),
    Case(
        "Tree",
        plain=lambda: Tree(_tree_sample()),
        explicit=lambda: Tree(
            _tree_sample(), expanded=glyphs.EXPANDED, collapsed=glyphs.COLLAPSED
        ),
        custom=_tree_custom,
        custom_check=_tree_custom_check,
        empty=_tree_empty,
        empty_check=_tree_empty_check,
        wide=_tree_wide,
        wide_check=_tree_wide_check,
        pair=_tree_wide,
        pair_check=_tree_pair_check,
    ),
    Case(
        "Table",
        plain=lambda: Table(["name"], [["alpha"], ["beta"]]),
        explicit=lambda: Table(
            ["name"], [["alpha"], ["beta"]], mark_pair=(glyphs.MARKED, glyphs.UNMARKED)
        ),
        custom=_table_custom,
        custom_check=_table_custom_check,
        empty=_table_empty,
        empty_check=_table_empty_check,
        wide=_table_wide,
        wide_check=_table_wide_check,
        pair=_table_wide,
        pair_check=_table_pair_check,
    ),
)


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_defaults_are_the_vocabulary_constants_byte_for_byte(case):
    """Naming the shipped constants explicitly changes nothing: a plain
    construction and the explicit one render the same styled bytes."""
    plain = [row.styled() for row in case.plain().render(WIDTH)]
    explicit = [row.styled() for row in case.explicit().render(WIDTH)]
    assert explicit == plain


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_a_custom_glyph_reaches_the_row_as_content(case):
    rows = case.custom().render(WIDTH)
    assert rows
    case.custom_check(rows)


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_an_empty_glyph_collapses_its_whole_seat(case):
    case.empty_check(case.empty().render(WIDTH))


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_a_wide_cjk_glyph_keeps_the_labels_in_one_column(case):
    case.wide_check(case.wide().render(WIDTH))


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_the_two_states_of_a_pair_share_one_column(case):
    case.pair_check(case.pair().render(WIDTH))

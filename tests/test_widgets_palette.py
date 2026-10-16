"""Tests for mocode_tui.widgets.palette (Palette).

The self-contained command palette: closed it renders zero rows and consumes
nothing; open it pins its own query row over the list.  Typing routes through
that row and re-filters the commands; ``handle`` consumes up/down/enter/escape
itself, recording a selection in ``chosen``.  The rows are the menu kernel's:
an ``\u2192`` cursor row in the theme's accent, an aligned description column,
a ``max_rows`` window with its ``(i/n)`` counter, and a cursor that wraps the
ends.
"""

import pytest

from _doubles import key

from mocode_tui.core.events import Paste
from mocode_tui.core.lines import Segment
from mocode_tui.core.style import Style
from mocode_tui.core.theme import DEFAULT_THEME, Theme
from mocode_tui.widgets.choice import Option
from mocode_tui.widgets.palette import Palette

_MENU = [
    Option("/help", value="help", description="What this demo can do"),
    Option("/model", value="model", description="Switch the fake model"),
    Option("/clear", value="clear", description="Empty the scrollback"),
    Option("/quit", value="quit", description="Leave the demo"),
]

#: The arrow the menu kernel puts on the cursor row.
_MARKED = "\u2192"


def _list_rows(palette: Palette, width: int = 40) -> list:
    """The rendered list rows: the palette's own query row(s) dropped."""
    return palette.render(width)[len(palette.input.render(width)) :]


def _option_rows(palette: Palette, width: int = 40) -> list:
    """The rendered option rows: the counter row (when there is one) dropped."""
    return [row for row in _list_rows(palette, width) if not row.segments[0].text.startswith("(")]


def _labels(palette: Palette, width: int = 40) -> list[str]:
    """The command labels of the rendered rows, in order."""
    return [row.segments[1].text for row in _option_rows(palette, width)]


def _marked_label(palette: Palette, width: int = 40) -> str:
    """The label of the row carrying the cursor's arrow."""
    for row in _option_rows(palette, width):
        if row.segments[0].text.startswith(_MARKED):
            return row.segments[1].text
    return ""


def _typed(palette: Palette, text: str) -> list[bool]:
    """Feed ``text`` one printable key at a time; return what ``handle`` said."""
    return [palette.handle(key(char, char)) for char in text]


def test_closed_palette_renders_zero_rows_and_consumes_nothing():
    palette = Palette(_MENU)
    assert palette.is_open is False
    assert palette.chosen is None
    assert palette.render(40) == []
    # Every key is the host's -- the palette never eats a closed keyboard.
    for name in ("up", "down", "enter", "escape", "a", "/", "backspace"):
        assert palette.handle(key(name)) is False
    assert palette.handle(Paste("text")) is False
    assert palette.is_open is False and palette.chosen is None


def test_open_pins_the_query_row_over_every_command():
    palette = Palette(_MENU)
    palette.open()
    assert palette.is_open is True
    assert palette.input.text == "" and palette.list.query == ""
    rows = palette.render(40)
    # The query row leads: the input's own prompt and cursor, byte for byte.
    query_rows = palette.input.render(40)
    assert rows[: len(query_rows)] == query_rows
    assert rows[0].text == "\u276e  "
    assert rows[0].segments[0] == Segment("\u276e ", DEFAULT_THEME.accent)
    # The list follows, the cursor row first, in the theme's accent.
    assert _labels(palette) == ["/help", "/model", "/clear", "/quit"]
    mark_row = _option_rows(palette)[0]
    assert mark_row.segments[0] == Segment("\u2192 ", DEFAULT_THEME.accent)
    assert mark_row.segments[1] == Segment("/help", DEFAULT_THEME.accent)
    # The non-cursor rows indent past the marker; descriptions sit dim.
    assert _option_rows(palette)[1].segments[0] == Segment("  ")
    assert _option_rows(palette)[1].segments[-1] == Segment(
        "Switch the fake model", DEFAULT_THEME.dim
    )


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("/", ["/help", "/model", "/clear", "/quit"]),  # the bare slash matches all
        ("/mod", ["/model"]),  # a prefix match
        ("/clear", ["/clear"]),  # exact label
        ("/HELP", []),  # the kernel does not fold case
        ("/zzz", []),  # nothing matches
    ],
)
def test_typing_filters_the_commands_through_the_query_row(typed, expected):
    palette = Palette(_MENU)
    palette.open()
    assert all(_typed(palette, typed))  # the query row consumed every printable
    assert palette.input.text == typed
    assert palette.list.query == typed
    assert _labels(palette) == expected


def test_the_clear_key_empties_the_query_and_restores_the_full_list():
    palette = Palette(_MENU)
    palette.open()
    _typed(palette, "/mod")
    assert _labels(palette) == ["/model"]
    assert palette.handle(key("c-u")) is True  # the row's own clear binding
    assert palette.input.text == "" and palette.list.query == ""
    assert _labels(palette) == ["/help", "/model", "/clear", "/quit"]


@pytest.mark.parametrize(
    ("steps", "expected"),
    [
        (0, "/help"),  # the cursor starts on the first match
        (1, "/model"),
        (2, "/clear"),
        (3, "/quit"),
        (4, "/help"),  # off the last match onto the first
        (10, "/clear"),  # any number of steps lands modulo the matches
    ],
)
def test_navigation_moves_the_cursor_and_wraps_the_ends(steps, expected):
    palette = Palette(_MENU)
    palette.open()
    for _ in range(steps):
        assert palette.handle(key("down")) is True
    assert palette.chosen is None  # navigation selects nothing
    assert _marked_label(palette) == expected
    (row,) = [r for r in _option_rows(palette) if r.segments[0].text.startswith(_MARKED)]
    assert row.segments[0].style == DEFAULT_THEME.accent  # the theme's cursor row
    for _ in range(steps):  # walking back up lands on the first match again
        assert palette.handle(key("up")) is True
    assert _marked_label(palette) == "/help"


def test_navigation_clears_a_pending_selection():
    palette = Palette(_MENU)
    palette.open()
    palette.chosen = "stale"  # a pick from some earlier visit
    assert palette.handle(key("down")) is True
    assert palette.chosen is None
    palette.chosen = "stale"
    assert palette.handle(key("up")) is True
    assert palette.chosen is None


@pytest.mark.parametrize(
    ("name", "typed", "expected"),
    [
        ("enter", "/mod", "model"),  # a selection records the option's value
        ("enter", "/zzz", None),  # nothing matches: consumed, but nothing chosen
        ("escape", "", None),  # a dismissal chooses nothing
    ],
)
def test_enter_and_escape_consume_the_palette_and_close_it(name, typed, expected):
    palette = Palette(_MENU)
    palette.open()
    if typed:
        _typed(palette, typed)
    assert palette.handle(key(name)) is True
    assert palette.chosen == expected
    assert palette.is_open is False
    assert palette.render(40) == []
    # The host reads the pick once and resets the attribute itself.
    palette.chosen = None
    assert palette.chosen is None


def test_a_selection_does_not_leak_into_the_next_visit():
    palette = Palette(_MENU)
    palette.open()
    _typed(palette, "/mod")
    assert palette.handle(key("enter")) is True and palette.chosen == "model"
    palette.open()  # a fresh visit starts with nothing chosen and no query
    assert palette.chosen is None
    assert palette.input.text == ""
    assert _labels(palette) == ["/help", "/model", "/clear", "/quit"]


def test_the_query_row_takes_every_other_key():
    """Typing and editing route through the palette's own Input; a key the
    row does not bind (tab, c-c) falls back to the host."""
    palette = Palette(_MENU)
    palette.open()
    for name in ("backspace", "left", "right", "home", "end", "delete", "c-u", "c-a"):
        assert palette.handle(key(name)) is True, name
    for name in ("tab", "c-c"):
        assert palette.handle(key(name)) is False, name
    assert palette.handle(Paste("text")) is True  # the row inserts the paste
    assert palette.input.text == "text"
    assert palette.list.query == "text"
    assert palette.is_open is True and palette.chosen is None  # none of them disturbed it


def test_max_rows_caps_the_window_and_shows_the_counter():
    commands = [Option(f"/c{i}", value=i) for i in range(12)]
    palette = Palette(commands, max_rows=3)
    palette.open()
    rows = _list_rows(palette)
    assert len(rows) == 4 and rows[-1].text == "(1/12)"  # 3 rows plus the counter
    assert _marked_label(palette) == "/c0"
    palette.handle(key("down"))
    assert len(_list_rows(palette)) == 4 and _marked_label(palette) == "/c1"
    for _ in range(10):  # walk to the bottom: the window follows the cursor
        palette.handle(key("down"))
    assert _labels(palette) == ["/c9", "/c10", "/c11"]
    assert _marked_label(palette) == "/c11"  # the selected row stays visible
    assert _list_rows(palette)[-1].text == "(12/12)"


def test_the_theme_reaches_both_composed_children():
    theme = Theme(accent=Style(reverse=True))
    palette = Palette(_MENU, theme=theme)
    assert palette.input.theme is theme
    assert palette.list.theme is theme
    palette.open()
    (row,) = [r for r in _option_rows(palette) if r.segments[0].text.startswith(_MARKED)]
    assert row.segments[0].style == Style(reverse=True)  # the cursor row follows

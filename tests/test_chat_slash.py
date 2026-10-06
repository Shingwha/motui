"""Tests for mocode_tui.chat.slash (SlashPalette).

The palette starts closed and renders zero rows; a ``"/"`` query filters the
commands verbatim; ``handle`` consumes only up/down/enter/escape, recording a
selection in ``chosen``.  The rows are the menu kernel's: an ``\u2192`` cursor
row in the theme's accent, an aligned description column, a ``max_rows``
window with its ``(i/n)`` counter, and a cursor that wraps the ends.
"""

import pytest

from _doubles import key

from mocode_tui.chat.slash import SlashPalette
from mocode_tui.core.events import Paste
from mocode_tui.core.lines import Segment
from mocode_tui.core.style import Style
from mocode_tui.core.theme import DEFAULT_THEME, Theme
from mocode_tui.widgets.choice import Option

_MENU = [
    Option("/help", value="help", description="What this demo can do"),
    Option("/model", value="model", description="Switch the fake model"),
    Option("/clear", value="clear", description="Empty the scrollback"),
    Option("/quit", value="quit", description="Leave the demo"),
]

#: The arrow the menu kernel puts on the cursor row.
_MARKED = "\u2192"


def _option_rows(palette: SlashPalette, width: int = 40) -> list:
    """The rendered option rows: the counter row (when there is one) dropped."""
    return [row for row in palette.render(width) if not row.segments[0].text.startswith("(")]


def _labels(palette: SlashPalette, width: int = 40) -> list[str]:
    """The command labels of the rendered rows, in order."""
    return [row.segments[1].text for row in _option_rows(palette, width)]


def _marked_label(palette: SlashPalette, width: int = 40) -> str:
    """The label of the row carrying the cursor's arrow."""
    for row in _option_rows(palette, width):
        if row.segments[0].text.startswith(_MARKED):
            return row.segments[1].text
    return ""


def test_closed_palette_renders_zero_rows_and_consumes_nothing():
    palette = SlashPalette(_MENU)
    assert palette.is_open is False
    assert palette.chosen is None
    assert palette.render(40) == []
    # Every key is the editor's -- the palette never eats a closed keyboard.
    for name in ("up", "down", "enter", "escape", "a", "/"):
        assert palette.handle(key(name)) is False
    assert palette.handle(Paste("text")) is False
    assert palette.is_open is False and palette.chosen is None


def test_open_shows_every_command_and_resets_a_stale_query():
    palette = SlashPalette(_MENU)
    palette.open()
    assert palette.is_open is True
    assert _labels(palette) == ["/help", "/model", "/clear", "/quit"]
    # The cursor row leads with the arrow in the theme's accent; the other
    # rows indent past it, and every description sits in one column.
    rows = palette.render(40)
    assert rows[0].segments[0] == Segment("\u2192 ", DEFAULT_THEME.accent)
    assert rows[0].segments[1] == Segment("/help", DEFAULT_THEME.accent)
    assert rows[1].segments[0] == Segment("  ")
    assert rows[1].segments[-1] == Segment("Switch the fake model", DEFAULT_THEME.dim)

    palette.set_query("/q")
    assert _labels(palette) == ["/quit"]
    palette.close()
    palette.open()  # a fresh visit must not inherit the old query
    assert _labels(palette) == ["/help", "/model", "/clear", "/quit"]
    # An explicit selection style overrides the theme's on the cursor row.
    styled = SlashPalette(_MENU, theme=Theme(accent=Style(reverse=True)))
    styled.open()
    (row,) = [r for r in styled.render(40) if r.segments[0].text.startswith(_MARKED)]
    assert row.segments[0].style == Style(reverse=True)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("/", ["/help", "/model", "/clear", "/quit"]),  # the bare slash matches all
        ("/mod", ["/model"]),  # a prefix match
        ("/clear", ["/clear"]),  # exact label
        ("/help", ["/help"]),  # case must match exactly
        ("/HELP", []),  # the kernel does not fold case
        ("/zzz", []),  # nothing matches
    ],
)
def test_a_slash_query_filters_the_commands_verbatim(query, expected):
    palette = SlashPalette(_MENU)
    palette.open()
    palette.set_query(query)
    assert _labels(palette) == expected


def test_losing_the_leading_slash_closes_the_palette():
    palette = SlashPalette(_MENU)
    palette.open()
    assert palette.is_open is True
    palette.set_query("help")  # no leading slash: not a command any more
    assert palette.is_open is False
    assert palette.render(40) == []


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
    palette = SlashPalette(_MENU)
    palette.open()
    for _ in range(steps):
        assert palette.handle(key("down")) is True
    assert palette.chosen is None  # navigation selects nothing
    assert _marked_label(palette) == expected
    (row,) = [r for r in palette.render(40) if r.segments[0].text.startswith(_MARKED)]
    assert row.segments[0].style == DEFAULT_THEME.accent  # the theme's cursor row
    for _ in range(steps):  # walking back up lands on the first match again
        assert palette.handle(key("up")) is True
    assert _marked_label(palette) == "/help"


@pytest.mark.parametrize(
    ("gesture", "chosen"),
    [
        (("enter", "/mod"), "model"),  # a selection records the option's value
        (("enter", "/zzz"), None),  # nothing matches: consumed, but nothing chosen
        (("escape", ""), None),  # a dismissal chooses nothing
    ],
)
def test_enter_and_escape_consume_the_palette_and_close_it(gesture, chosen):
    name, query = gesture
    palette = SlashPalette(_MENU)
    palette.open()
    if query:
        palette.set_query(query)
    assert palette.handle(key(name)) is True
    assert palette.chosen == chosen
    palette.chosen = None  # the host reads the selection, then clears it
    assert palette.chosen is None
    assert palette.is_open is False
    assert palette.render(40) == []


def test_a_selection_does_not_leak_into_the_next_visit():
    palette = SlashPalette(_MENU)
    palette.open()
    palette.set_query("/mod")
    assert palette.handle(key("enter")) is True and palette.chosen == "model"
    palette.open()  # a fresh visit starts with nothing chosen
    assert palette.chosen is None


def test_every_other_key_falls_through_to_the_editor():
    palette = SlashPalette(_MENU)
    palette.open()
    for name in ("a", "q", "space", "backspace", "left", "right", "home", "end",
                 "tab", "c-c", "/"):
        assert palette.handle(key(name)) is False, name
    assert palette.handle(Paste("text")) is False
    assert palette.is_open is True and palette.chosen is None  # none of them disturbed it


def test_max_rows_caps_the_window_and_shows_the_counter():
    commands = [Option(f"/c{i}", value=i) for i in range(12)]
    palette = SlashPalette(commands, max_rows=3)
    palette.open()
    rows = palette.render(40)
    assert len(rows) == 4 and rows[-1].text == "(1/12)"  # 3 rows plus the counter
    assert _marked_label(palette) == "/c0"
    palette.handle(key("down"))
    assert len(palette.render(40)) == 4 and _marked_label(palette) == "/c1"
    for _ in range(10):  # walk to the bottom: the window follows the cursor
        palette.handle(key("down"))
    assert _labels(palette) == ["/c9", "/c10", "/c11"]
    assert _marked_label(palette) == "/c11"  # the selected row stays visible
    assert palette.render(40)[-1].text == "(12/12)"

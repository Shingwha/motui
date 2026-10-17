"""Tests for motui.interaction.palette (Palette).

The command palette is a modal controller now: closed it renders zero rows
and consumes nothing; open it shows its own query row over the list in a
bottom-anchored panel over the scrimmed frame, and every event is the
palette's -- the panel's keys decide, a press outside dismisses with
nothing chosen, and every other event is consumed rather than falling
through to the host.  Typing routes through the query row and re-filters
the commands; ``handle`` consumes up/down/enter/escape itself, recording a
selection in ``chosen``.  The rows are the menu kernel's: an ``\u2192``
cursor row in the theme's accent, an aligned description column, a
``max_rows`` window with its ``(i/n)`` counter, and a cursor that wraps the
ends.
"""

import pytest

from _doubles import key

from motui.interaction.palette import Palette
from motui.kernel.events import MouseEvent, Paste
from motui.kernel.lines import Segment, Text
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME, Theme
from motui.testing import headless_tui
from motui.widgets.choice import Option

_MENU = [
    Option("/help", value="help", description="What this demo can do"),
    Option("/model", value="model", description="Switch the fake model"),
    Option("/clear", value="clear", description="Empty the scrollback"),
    Option("/quit", value="quit", description="Leave the demo"),
]

#: The arrow the menu kernel puts on the cursor row.
_MARKED = "\u2192"


def _palette(commands: list[Option] | None = None, **knobs) -> Palette:
    """A palette over a fresh headless driver (its modal registers there)."""
    return Palette(headless_tui(40, 8), _MENU if commands is None else commands, **knobs)


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
    palette = _palette()
    assert palette.is_open is False
    assert palette.chosen is None
    assert palette.render(40) == []
    # Every key -- and every click -- is the host's: the palette never eats a
    # closed keyboard, and a closed modal leaves the pointer alone too.
    for name in ("up", "down", "enter", "escape", "a", "/", "backspace"):
        assert palette.handle(key(name)) is False
    assert palette.handle(Paste("text")) is False
    assert palette.handle(MouseEvent("left", button=0, x=1, y=0, kind="press")) is False
    assert palette.is_open is False and palette.chosen is None


def test_open_pins_the_query_row_over_every_command():
    palette = _palette()
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
    palette = _palette()
    palette.open()
    assert all(_typed(palette, typed))  # the query row consumed every printable
    assert palette.input.text == typed
    assert palette.list.query == typed
    assert _labels(palette) == expected


def test_the_clear_key_empties_the_query_and_restores_the_full_list():
    palette = _palette()
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
    palette = _palette()
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
    palette = _palette()
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
    palette = _palette()
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
    palette = _palette()
    palette.open()
    _typed(palette, "/mod")
    assert palette.handle(key("enter")) is True and palette.chosen == "model"
    palette.open()  # a fresh visit starts with nothing chosen and no query
    assert palette.chosen is None
    assert palette.input.text == ""
    assert _labels(palette) == ["/help", "/model", "/clear", "/quit"]


def test_the_query_row_takes_every_other_key():
    """Typing and editing route through the palette's own Input; the palette
    is a modal now, so even a key the row does not bind (tab, c-c) is
    consumed and dropped -- no host shortcut reaches through an open one."""
    palette = _palette()
    palette.open()
    for name in ("backspace", "left", "right", "home", "end", "delete", "c-u", "c-a"):
        assert palette.handle(key(name)) is True, name
    for name in ("tab", "c-c"):
        assert palette.handle(key(name)) is True, name  # consumed, deciding nothing
    assert palette.handle(Paste("text")) is True  # the row inserts the paste
    assert palette.input.text == "text"
    assert palette.list.query == "text"
    assert palette.is_open is True and palette.chosen is None  # none of them disturbed it


def test_max_rows_caps_the_window_and_shows_the_counter():
    commands = [Option(f"/c{i}", value=i) for i in range(12)]
    palette = _palette(commands, max_rows=3)
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
    palette = _palette(theme=theme)
    assert palette.input.theme is theme
    assert palette.list.theme is theme
    palette.open()
    (row,) = [r for r in _option_rows(palette) if r.segments[0].text.startswith(_MARKED)]
    assert row.segments[0].style == Style(reverse=True)  # the cursor row follows


# --- the modal paths: the scrim, the placement, the dismissal -------------------


def test_open_scrims_the_frame_and_parks_the_panel_at_the_foot():
    """The modal's paint: every frame row is veiled (D4: colors kept, weight
    down) and the panel's own rows land at the frame's bottom-left."""
    tui = headless_tui(40, 8)
    palette = Palette(tui, _MENU)
    tui.add(Text("under the veil"))
    tui.paint()
    palette.open()
    tui.paint()
    rows = tui.rows
    assert rows[0].text.startswith("under the veil")  # the glyphs stay
    assert rows[0].segments[0].style == Style(dim=True)  # the weight drops
    panel = palette.render(40)
    assert panel  # open: the query row over the list
    top = len(rows) - len(panel)
    for index, row in enumerate(panel):
        assert rows[top + index].text.startswith(row.text), index


def test_a_press_outside_the_panel_dismisses_with_nothing_chosen():
    """The modal's dismissal, and the modal's consumption: a press inside the
    panel is the palette's too -- it just decides nothing (no click gesture)."""
    tui = headless_tui(40, 8)
    palette = Palette(tui, _MENU)
    tui.paint()
    palette.open()
    tui.paint()
    assert palette.handle(MouseEvent("left", button=0, x=20, y=0, kind="press")) is True
    assert palette.is_open is False and palette.chosen is None
    assert palette.render(40) == []

    palette.open()
    tui.paint()
    top = len(tui.rows) - len(palette.render(40))
    assert palette.handle(MouseEvent("left", button=0, x=1, y=top, kind="press")) is True
    assert palette.is_open is True and palette.chosen is None

"""Tests for mocode_tui.chat.slash (SlashPalette).

Contract: the palette starts closed and renders zero rows while closed;
a query starting with ``"/"`` filters the commands verbatim (the label's
own slash is what prefix matching keys on), anything else closes it;
``handle_key`` consumes up/down/enter/escape only -- ``False`` for every
other event (the editor's keys stay the editor's) -- answering the
selected value on enter and ``None`` on navigation or dismissal; opening
resets to the full command list.  Rows are asserted structurally, on
``Line.segments``, never by scraping rendered text.
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
    Option("/help", value="help", hint="What this demo can do"),
    Option("/model", value="model", hint="Switch the fake model"),
    Option("/clear", value="clear", hint="Empty the scrollback"),
    Option("/quit", value="quit", hint="Leave the demo"),
]

#: The selection marker a ``choice.option_row`` puts on the current row.
_MARKED = "\u276e"


def _labels(palette: SlashPalette, width: int = 40) -> list[str]:
    """The command labels of the rendered rows, read off their segments."""
    out: list[str] = []
    for row in palette.render(width):
        # The label is the option body's leading run: marker and hint stripped.
        body = row.segments[0].text
        if body.startswith(_MARKED):
            body = body[len(_MARKED) :].strip()
        out.append(body.strip().split("  ")[0].strip())
    return out


def _marked_label(palette: SlashPalette, width: int = 40) -> str:
    """The label of the row carrying the selection marker."""
    for row in palette.render(width):
        if row.segments[0].text.startswith(_MARKED):
            return row.segments[0].text[len(_MARKED) :].strip().split("  ")[0].strip()
    return ""


def test_closed_palette_renders_zero_rows_and_consumes_nothing():
    palette = SlashPalette(_MENU)
    assert palette.is_open is False
    assert palette.render(40) == []
    # Every key is the editor's -- the palette never eats a closed keyboard.
    for name in ("up", "down", "enter", "escape", "a", "/"):
        assert palette.handle_key(key(name)) is False
    assert palette.handle_key(Paste("text")) is False
    assert palette.is_open is False


def test_open_shows_every_command_and_resets_a_stale_query():
    palette = SlashPalette(_MENU)
    palette.open()
    assert palette.is_open is True
    assert _labels(palette) == ["/help", "/model", "/clear", "/quit"]
    # The selected row is one continuous run: marker, label and hint merged;
    # an unselected row keeps its hint as a separate trailing segment.
    rows = palette.render(40)
    assert rows[0].segments == (
        Segment(f"{_MARKED} /help  What this demo can do", DEFAULT_THEME.selection),
    )
    assert rows[1].segments == (
        Segment("  /model", Style()),
        Segment("  Switch the fake model", DEFAULT_THEME.dim),
    )

    palette.sync_query("/q")
    assert _labels(palette) == ["/quit"]
    palette.close()
    palette.open()  # a fresh visit must not inherit the old query
    assert _labels(palette) == ["/help", "/model", "/clear", "/quit"]
    # An explicit selection style overrides the theme's on the marked row.
    styled = SlashPalette(_MENU, theme=Theme(selection=Style(reverse=True)))
    styled.open()
    marked = [r for r in styled.render(40) if r.segments[0].text.startswith(_MARKED)]
    (row,) = marked
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
    palette.sync_query(query)
    assert _labels(palette) == expected


def test_losing_the_leading_slash_closes_the_palette():
    palette = SlashPalette(_MENU)
    palette.open()
    assert palette.is_open is True
    palette.sync_query("help")  # no leading slash: not a command any more
    assert palette.is_open is False
    assert palette.render(40) == []


@pytest.mark.parametrize(
    ("steps", "expected"),
    [
        (0, "/help"),  # the cursor starts on the first match
        (1, "/model"),
        (2, "/clear"),
        (3, "/quit"),
        (10, "/quit"),  # clamped at the bottom, never wrapping
    ],
)
def test_navigation_moves_and_clamps_the_cursor_within_the_matches(steps, expected):
    palette = SlashPalette(_MENU)
    palette.open()
    for _ in range(steps):
        assert palette.handle_key(key("down")) is None
    assert _marked_label(palette) == expected
    (row,) = [r for r in palette.render(40) if r.segments[0].text.startswith(_MARKED)]
    assert row.segments[0].style == DEFAULT_THEME.selection  # the theme's selection
    # Walking all the way back up lands on the first match and stops there.
    for _ in range(steps + 2):
        assert palette.handle_key(key("up")) is None
    assert _marked_label(palette) == "/help"


@pytest.mark.parametrize(
    ("gesture", "answer"),
    [
        (("enter", "/mod"), "model"),  # a selection answers the option's value
        (("enter", "/zzz"), None),  # nothing matches: consumed, but nothing selected
        (("escape", ""), None),  # a dismissal answers None
    ],
)
def test_enter_and_escape_consume_the_palette_and_close_it(gesture, answer):
    name, query = gesture
    palette = SlashPalette(_MENU)
    palette.open()
    if query:
        palette.sync_query(query)
    assert palette.handle_key(key(name)) == answer
    assert palette.is_open is False
    assert palette.render(40) == []


def test_every_other_key_falls_through_to_the_editor():
    palette = SlashPalette(_MENU)
    palette.open()
    for name in ("a", "q", "space", "backspace", "left", "right", "home", "end",
                 "tab", "c-c", "/"):
        assert palette.handle_key(key(name)) is False, name
    assert palette.handle_key(Paste("text")) is False
    assert palette.is_open is True  # none of them disturbed the palette


def test_max_rows_caps_the_window_around_the_cursor():
    commands = [Option(f"/c{i}", value=i) for i in range(12)]
    palette = SlashPalette(commands, max_rows=3)
    palette.open()
    assert len(palette.render(40)) == 3
    assert _marked_label(palette) == "/c0"
    palette.handle_key(key("down"))
    assert len(palette.render(40)) == 3 and _marked_label(palette) == "/c1"
    for _ in range(10):  # walk to the bottom: the window follows the cursor
        palette.handle_key(key("down"))
    assert _labels(palette) == ["/c9", "/c10", "/c11"]
    assert _marked_label(palette) == "/c11"  # the selected row stays visible

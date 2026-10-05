"""Tests for mocode_tui.chat.slash (SlashPalette).

Contract: the palette starts closed and renders zero rows while closed;
a query starting with ``"/"`` filters the commands verbatim (the label's
own slash is what prefix matching keys on), anything else closes it;
handle_key consumes up/down/enter/escape only -- ``False`` for every
other event (the editor's keys stay the editor's) -- answering the
selected value on enter and ``None`` on navigation or dismissal; opening
resets to the full command list.
"""

from mocode_tui.chat.slash import SlashPalette
from mocode_tui.core.style import Style
from mocode_tui.core.theme import DEFAULT_THEME, Theme
from mocode_tui.keys.events import Key, Paste
from mocode_tui.widgets.choice import Option

_MENU = [
    Option("/help", value="help", hint="What this demo can do"),
    Option("/model", value="model", hint="Switch the fake model"),
    Option("/clear", value="clear", hint="Empty the scrollback"),
    Option("/quit", value="quit", hint="Leave the demo"),
]


def _labels(palette: SlashPalette, width: int = 40) -> list[str]:
    """The command labels of the rendered rows, markers and hints dropped."""
    out = []
    for row in palette.render(width):
        text = row.text.strip()
        if text.startswith("\u276e"):
            text = text[1:].strip()
        out.append(text.split("  ")[0].strip())
    return out


def _marked(palette: SlashPalette, width: int = 40) -> str:
    """The label of the row carrying the selection marker."""
    for row in palette.render(width):
        text = row.text.strip()
        if text.startswith("\u276e"):
            return text[1:].strip().split("  ")[0].strip()
    return ""


def test_starts_closed_and_renders_zero_rows():
    palette = SlashPalette(_MENU)
    assert palette.is_open is False
    assert palette.render(40) == []


def test_open_shows_every_command():
    palette = SlashPalette(_MENU)
    palette.open()
    assert palette.is_open is True
    assert _labels(palette) == ["/help", "/model", "/clear", "/quit"]


def test_open_resets_the_query_to_the_full_list():
    palette = SlashPalette(_MENU)
    palette.open()
    palette.sync_query("/q")
    assert _labels(palette) == ["/quit"]
    palette.close()
    palette.open()  # a fresh visit must not inherit the old query
    assert _labels(palette) == ["/help", "/model", "/clear", "/quit"]


def test_slash_query_filters_verbatim():
    palette = SlashPalette(_MENU)
    palette.open()
    palette.sync_query("/")  # the bare slash matches every label prefix
    assert len(_labels(palette)) == 4
    palette.sync_query("/mod")
    assert _labels(palette) == ["/model"]
    palette.sync_query("/clear")
    assert _labels(palette) == ["/clear"]


def test_query_matching_is_case_sensitive():
    palette = SlashPalette(_MENU)
    palette.open()
    palette.sync_query("/HELP")
    assert _labels(palette) == []  # the kernel does not fold case
    palette.sync_query("/help")
    assert _labels(palette) == ["/help"]


def test_losing_the_slash_closes_the_palette():
    palette = SlashPalette(_MENU)
    palette.open()
    palette.close()
    assert palette.is_open is False and palette.render(40) == []
    palette.open()
    palette.sync_query("help")  # no leading slash: not a command any more
    assert palette.is_open is False
    assert palette.render(40) == []


def test_navigation_keys_are_consumed_and_move_the_cursor():
    palette = SlashPalette(_MENU)
    palette.open()
    assert _marked(palette) == "/help"
    assert palette.handle_key(Key("down")) is None
    assert _marked(palette) == "/model"
    assert palette.handle_key(Key("down")) is None
    assert _marked(palette) == "/clear"
    assert palette.handle_key(Key("up")) is None
    assert _marked(palette) == "/model"


def test_navigation_clamps_and_never_wraps():
    palette = SlashPalette(_MENU)
    palette.open()
    assert palette.handle_key(Key("up")) is None  # already at the top
    assert _marked(palette) == "/help"
    for _ in range(10):
        assert palette.handle_key(Key("down")) is None
    assert _marked(palette) == "/quit"  # clamped at the bottom


def test_enter_answers_the_selected_value_and_closes():
    palette = SlashPalette(_MENU)
    palette.open()
    palette.handle_key(Key("down"))  # /model
    palette.handle_key(Key("down"))  # /clear
    assert palette.handle_key(Key("enter")) == "clear"
    assert palette.is_open is False
    assert palette.render(40) == []


def test_enter_with_no_matches_answers_none_and_closes():
    palette = SlashPalette(_MENU)
    palette.open()
    palette.sync_query("/zzz")
    assert palette.render(40) == []  # nothing matches: nothing renders
    assert palette.handle_key(Key("enter")) is None
    assert palette.is_open is False


def test_escape_dismisses_and_answers_none():
    palette = SlashPalette(_MENU)
    palette.open()
    assert palette.handle_key(Key("escape")) is None
    assert palette.is_open is False


def test_every_other_key_falls_through_to_the_editor():
    palette = SlashPalette(_MENU)
    palette.open()
    for name in ("a", "q", "space", "backspace", "left", "right", "home", "end",
                 "tab", "c-c"):
        assert palette.handle_key(Key(name)) is False, name
    assert palette.handle_key(Key("/")) is False
    assert palette.handle_key(Paste("text")) is False
    assert palette.is_open is True  # none of them disturbed the palette


def test_closed_palette_consumes_nothing():
    palette = SlashPalette(_MENU)
    for name in ("up", "down", "enter", "escape"):
        assert palette.handle_key(Key(name)) is False
    assert palette.is_open is False


def test_max_rows_caps_the_window_around_the_cursor():
    commands = [Option(f"/c{i}", value=i) for i in range(12)]
    palette = SlashPalette(commands, max_rows=3)
    palette.open()
    assert len(palette.render(40)) == 3
    assert _marked(palette) == "/c0"
    palette.handle_key(Key("down"))
    assert len(palette.render(40)) == 3 and _marked(palette) == "/c1"
    for _ in range(10):  # walk to the bottom: the window follows the cursor
        palette.handle_key(Key("down"))
    rows = _labels(palette)
    assert len(rows) == 3
    assert _marked(palette) == "/c11"  # the selected row stays visible


def test_selected_row_carries_the_theme_selection_style():
    palette = SlashPalette(_MENU, theme=Theme(selection=Style(reverse=True)))
    palette.open()
    (row,) = [r for r in palette.render(40) if r.text.startswith("\u276e")]
    assert row.segments[0].style == Style(reverse=True)
    # A theme left alone answers the shipped default.
    palette = SlashPalette(_MENU)
    palette.open()
    (row,) = [r for r in palette.render(40) if r.text.startswith("\u276e")]
    assert row.segments[0].style == DEFAULT_THEME.selection


def test_demo_replay_open_type_navigate_dismiss():
    """Demo alignment: the scripted slash visit, event for event.

    The demo's replay types ``/`` (opens), ``q`` (typing keeps working),
    ``down`` (navigate) and ``escape`` (dismiss, the typed text stays).
    The palette mirrors that: full list on the bare slash, filtered by
    the typed query, navigation clamped inside the matches.
    """
    palette = SlashPalette(_MENU)
    editor_text = ""

    def press(name: str, char: str = ""):
        nonlocal editor_text
        event = Key(name, char)
        answer = palette.handle_key(event)
        if answer is not False:
            return answer  # the palette consumed it
        if char:  # the editor inserts; a freshly typed slash opens the palette
            editor_text += char
            if editor_text.startswith("/") and not palette.is_open:
                palette.open()
        palette.sync_query(editor_text)  # edits filter, or close on a lost slash
        return False

    assert press("/", "/") is False
    assert palette.is_open is True  # the host opened it on the typed slash
    assert _labels(palette) == ["/help", "/model", "/clear", "/quit"]
    assert press("q", "q") is False
    assert palette.is_open is True  # typing is decoupled from navigation
    assert _labels(palette) == ["/quit"]
    assert press("down") is None
    assert _marked(palette) == "/quit"  # a single match: the cursor clamps
    assert press("escape") is None
    assert palette.is_open is False
    assert palette.render(40) == []  # dismissed, and the typed "/q" stays put

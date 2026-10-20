"""Palette: query filtering, navigation, results, dismissal and unmounting."""

from __future__ import annotations

from motui.interaction import FocusManager, Palette
from motui.kernel.events import MouseEvent, PasteEvent
from motui.kernel.lines import Text
from motui.widgets.choice import Option
from tests.testing import headless_tui, key

_MENU = [
    Option("/help", value="help", description="What this demo can do"),
    Option("/model", value="model", description="Switch the fake model"),
    Option("/clear", value="clear", description="Empty the scrollback"),
    Option("/quit", value="quit", description="Leave the demo"),
]

_MARKED = "\u2192"


def palette(commands: list[Option] | None = None, **knobs) -> Palette:
    return Palette(headless_tui(40, 8), _MENU if commands is None else commands, **knobs)


def list_rows(palette: Palette, width: int = 40) -> list:
    return palette.render(width)[len(palette.input.render(width)) :]


def option_rows(palette: Palette, width: int = 40) -> list:
    return [row for row in list_rows(palette, width) if not row.text.startswith("(")]


def labels(palette: Palette, width: int = 40) -> list[str]:
    return [row.segments[1].text for row in option_rows(palette, width)]


def marked_label(palette: Palette, width: int = 40) -> str:
    for row in option_rows(palette, width):
        if row.text.startswith(_MARKED):
            return row.segments[1].text
    return ""


def typed(palette: Palette, text: str) -> list[bool]:
    return [palette.handle(key(char, char)) for char in text]


# -- the closed and open states ----------------------------------------------


def test_closed_palette_renders_zero_rows_and_consumes_nothing():
    palette_ = palette()
    assert palette_.is_open is False
    assert palette_.take_result() is None
    assert palette_.render(40) == []
    for name in ("up", "down", "enter", "escape", "a", "/", "backspace"):
        assert palette_.handle(key(name)) is False
    assert palette_.handle(PasteEvent("text")) is False
    assert palette_.handle(MouseEvent("left", x=1, y=0, kind="press")) is False
    assert palette_.is_open is False and palette_.take_result() is None


def test_open_shows_the_query_row_over_every_command():
    palette_ = palette()
    palette_.open()
    assert palette_.is_open is True
    assert palette_.input.text == "" and palette_.list.query == ""
    rows = palette_.render(40)
    assert rows[: len(palette_.input.render(40))] == palette_.input.render(40)
    assert labels(palette_) == ["/help", "/model", "/clear", "/quit"]
    assert marked_label(palette_) == "/help"


# -- filtering ---------------------------------------------------------------


def test_the_clear_key_empties_the_query_and_restores_the_list():
    palette_ = palette()
    palette_.open()
    typed(palette_, "/mod")
    assert labels(palette_) == ["/model"]
    assert palette_.handle(key("c-u")) is True
    assert palette_.input.text == "" and palette_.list.query == ""
    assert labels(palette_) == ["/help", "/model", "/clear", "/quit"]


# -- navigation and results --------------------------------------------------


def test_max_rows_caps_the_window_and_the_counter_tracks_the_cursor():
    commands = [Option(f"/c{i}", value=i) for i in range(12)]
    palette_ = palette(commands, max_rows=3)
    palette_.open()
    rows = list_rows(palette_)
    assert len(rows) == 4 and rows[-1].text == "(1/12)"
    assert marked_label(palette_) == "/c0"
    palette_.handle(key("down"))
    assert marked_label(palette_) == "/c1"
    for _ in range(10):
        palette_.handle(key("down"))
    assert labels(palette_) == ["/c9", "/c10", "/c11"]
    assert marked_label(palette_) == "/c11"
    assert list_rows(palette_)[-1].text == "(12/12)"


# -- modal integration -------------------------------------------------------


def test_open_scrims_the_frame_and_parks_the_panel_at_the_foot():
    from motui.kernel.style import Style

    tui = headless_tui(40, 8)
    palette_ = Palette(tui, _MENU)
    tui.add(Text("under the veil"))
    tui.paint()
    palette_.open()
    tui.paint()
    rows = tui.rows
    assert rows[0].text.startswith("under the veil")
    assert rows[0].segments[0].style == Style(dim=True)
    panel = palette_.render(40)
    top = len(rows) - len(panel)
    for index, row in enumerate(panel):
        assert rows[top + index].text.startswith(row.text)


def test_a_press_outside_dismisses_and_a_press_inside_is_consumed():
    tui = headless_tui(40, 8)
    palette_ = Palette(tui, _MENU)
    tui.paint()
    palette_.open()
    tui.paint()
    assert palette_.handle(MouseEvent("left", x=20, y=0, kind="press")) is True
    assert palette_.is_open is False and palette_.take_result() is None
    assert palette_.render(40) == []

    palette_.open()
    tui.paint()
    top = len(tui.rows) - len(palette_.render(40))
    assert palette_.handle(MouseEvent("left", x=1, y=top, kind="press")) is True
    assert palette_.is_open is True and palette_.take_result() is None


def test_detach_unmounts_and_close_only_hides():
    tui = headless_tui(40, 8)
    palette_ = Palette(tui, _MENU)
    palette_.open()
    palette_.close()
    assert palette_.is_open is False
    palette_.open()
    assert palette_.is_open is True

    palette_.detach()
    assert palette_.is_open is False
    assert palette_.handle(key("down")) is False
    palette_.open()
    assert palette_.is_open is False
    tui.paint()
    assert not any("\u276e" in row.text for row in tui.rows)


def test_the_palette_forwards_its_focus_trap():
    tui = headless_tui(40, 8)
    focus = FocusManager()
    palette_ = Palette(tui, _MENU, focus=focus)
    palette_.open()
    assert len(focus.targets) == 1 and focus.focused is focus.targets[0]
    palette_.close()
    assert focus.targets == ()


def test_typing_filters_the_commands_through_the_query_row():
    for typed_text, expected in (
        ("/", ["/help", "/model", "/clear", "/quit"]),
        ("/mod", ["/model"]),
        ("/HELP", ["/help"]),
        ("/zzz", []),
    ):
        palette_ = palette()
        palette_.open()
        assert all(typed(palette_, typed_text))
        assert palette_.input.text == typed_text
        assert palette_.list.query == typed_text
        assert labels(palette_) == expected


def test_navigation_wraps_the_ends():
    for steps, expected in ((0, "/help"), (1, "/model"), (4, "/help"), (10, "/clear")):
        palette_ = palette()
        palette_.open()
        for _ in range(steps):
            assert palette_.handle(key("down")) is True
        assert palette_.take_result() is None
        assert marked_label(palette_) == expected
        for _ in range(steps):
            assert palette_.handle(key("up")) is True
        assert marked_label(palette_) == "/help"


def test_enter_and_escape_close_the_palette_with_a_result():
    for name, typed_text, expected in (
        ("enter", "/mod", "model"),
        ("enter", "/zzz", None),
        ("escape", "", None),
    ):
        palette_ = palette()
        palette_.open()
        if typed_text:
            typed(palette_, typed_text)
        assert palette_.handle(key(name)) is True
        assert palette_.take_result() == expected
        assert palette_.is_open is False
        assert palette_.render(40) == []
        assert palette_.take_result() is None

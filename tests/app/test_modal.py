"""Modal: lifecycle, scrim and placement, event routing, results, focus traps."""

from __future__ import annotations

from motui.app import FocusManager, Modal
from motui.core.events import KeyEvent, MouseEvent, PasteEvent
from motui.core.lines import Line, Text
from motui.core.style import Style
from motui.widgets import Button, ButtonSpec, Dialog
from tests.testing import headless_tui, key, many, press


class Panel:
    """A modal panel double: rows, a click cell and a small key table."""

    def __init__(
        self,
        *texts: str,
        decisions: dict[str, object] | None = None,
        declined: tuple[str, ...] = (),
        click_cell: tuple[int, int] | None = None,
        click_value: object = None,
    ) -> None:
        self.texts = list(texts)
        self.decisions = dict(decisions or {})
        self.declined = set(declined)
        self.click_cell = click_cell
        self.click_value = click_value
        self.clicks: list[tuple[int, int]] = []
        self.seen: list[str] = []
        self.pending: object = None

    def render(self, width: int) -> list[Line]:
        return [Line.from_text(text) for text in self.texts]

    def click(self, row: int, col: int) -> bool:
        self.clicks.append((row, col))
        if self.click_cell != (row, col):
            return False
        self.pending = self.click_value
        return True

    def handle(self, event) -> bool:
        self.seen.append(name_of(event))
        if not isinstance(event, KeyEvent):
            return False
        if event.key in self.decisions:
            self.pending = self.decisions[event.key]
            return True
        return event.key in self.declined

    def take_result(self) -> object | None:
        value, self.pending = self.pending, None
        return value


class Body:
    """A panel body: consumes the keys it takes and records what it saw."""

    def __init__(self, takes: tuple[str, ...] = ()) -> None:
        self.takes = set(takes)
        self.seen: list[str] = []

    def handle(self, event) -> bool:
        self.seen.append(name_of(event))
        return name_of(event) in self.takes


def name_of(event) -> str:
    return "paste" if isinstance(event, PasteEvent) else event.key


def framed(*texts: str, width: int = 20, height: int = 5):
    tui = headless_tui(width, height)
    for text in texts:
        tui.add(Text(text))
    tui.paint()
    return tui


# -- lifecycle ---------------------------------------------------------------


def test_a_closed_modal_paints_nothing_and_consumes_nothing():
    tui = framed("hello")
    before = [row.text for row in tui.rows]
    modal = Modal(tui, Panel("panel"))
    assert modal.is_open is False and modal.take_result() is None
    assert modal.paint(tui.frame) is tui.frame.layout
    tui.paint()
    assert [row.text for row in tui.rows] == before
    assert modal.handle(key("x", "x")) is False
    assert modal.handle(press(7, 2)) is False


def test_detach_unregisters_and_a_detached_modal_stays_out():
    tui = framed("hello")
    before = len(tui.frame.overlays)
    modal = Modal(tui, Panel("panel"))
    assert len(tui.frame.overlays) == before + 1
    modal.open()
    modal.detach()
    assert modal not in tui.frame.overlays
    modal.detach()
    assert modal not in tui.frame.overlays
    modal.open()
    assert modal not in tui.frame.overlays
    tui.paint()
    assert all("panel" not in row.text for row in tui.rows)


# -- paint and placement -----------------------------------------------------


def test_open_scrims_every_row_and_centers_the_panel():
    tui = framed("hello", "world")
    modal = Modal(tui, Panel("panel"))
    modal.open()
    tui.paint()
    rows = tui.rows
    assert [row.text[:5] for row in rows[:2]] == ["hello", "world"]
    assert rows[0].segments[0].style == Style(dim=True)
    assert rows[1].segments[0].style == Style(dim=True)
    assert rows[2].text.find("panel") == 7
    assert len(rows[2].text) == 20

    modal.close()
    tui.paint()
    assert tui.rows[0].segments[0].style == Style()


def test_the_anchor_pins_the_panel_and_the_frame_clamps_it():
    tui = framed("hello")
    pinned = Modal(tui, Panel("panel"), anchor=(1, 2))
    pinned.open()
    tui.paint()
    assert tui.rows[1].text.find("panel") == 2

    parked = Modal(tui, Panel("panel"), anchor=(99, 99))
    parked.open()
    tui.paint()
    assert tui.rows[4].text.find("panel") == 15


def test_a_panel_overrunning_the_frame_is_clipped():
    tui = framed()
    tall = Modal(tui, Panel(*many(9)))
    tall.open()
    tui.paint()
    assert [row.text.strip() for row in tui.rows] == many(5)
    tall.close()

    wide = Modal(tui, Panel("w" * 50))
    wide.open()
    tui.paint()
    assert tui.rows[2].text == "w" * 19 + "\u2026"


# -- routing -----------------------------------------------------------------


def test_a_press_inside_clicks_at_the_panels_own_coordinates():
    tui = framed("hello")
    panel = Panel("panel", "rows!", click_cell=(1, 1), click_value="taken")
    modal = Modal(tui, panel)
    modal.open()
    tui.paint()
    assert modal.handle(press(7, 1)) is True
    assert panel.clicks == [(0, 0)]
    assert modal.is_open is True and modal.take_result() is None

    assert modal.handle(press(8, 2)) is True
    assert panel.clicks == [(0, 0), (1, 1)]
    assert modal.is_open is False and modal.take_result() == "taken"
    assert modal.take_result() is None


def test_other_pointer_reports_are_swallowed_without_a_decision():
    tui = framed("hello")
    panel = Panel("panel", click_cell=(0, 0), click_value="taken")
    modal = Modal(tui, panel)
    modal.open()
    for kind in ("motion", "release"):
        assert modal.handle(MouseEvent("left", x=7, y=2, kind=kind)) is True
    assert modal.handle(MouseEvent("wheel_down", x=7, y=2, kind="press")) is True
    assert panel.clicks == [] and modal.is_open is True


def test_a_press_outside_dismisses_and_can_be_configured_not_to():
    tui = framed("hello")
    modal = Modal(tui, Panel("panel"))
    modal.open()
    assert modal.handle(press(0, 0)) is True
    assert modal.is_open is False and modal.take_result() is None

    held = Modal(tui, Panel("panel"), dismiss_on_click_outside=False)
    held.open()
    assert held.handle(press(0, 0)) is True
    assert held.is_open is True and held.take_result() is None


def test_the_keyboard_is_body_first_and_the_panel_takes_what_the_body_leaves():
    tui = framed("hello")
    panel = Panel("panel", decisions={"enter": "ok"}, declined=("down",))
    body = Body(takes=("x",))
    panel.body = body
    modal = Modal(tui, panel)
    modal.open()

    assert modal.handle(key("x", "x")) is True
    assert body.seen == ["x"] and panel.seen == []
    assert modal.is_open is True and modal.take_result() is None

    assert modal.handle(key("down")) is True
    assert body.seen == ["x", "down"] and panel.seen == ["down"]
    assert modal.is_open is True and modal.take_result() is None

    assert modal.handle(key("enter")) is True
    assert panel.seen == ["down", "enter"]
    assert modal.is_open is False and modal.take_result() == "ok"

    modal.open()
    assert modal.handle(PasteEvent("text")) is True
    assert body.seen == ["x", "down", "enter", "paste"]
    assert panel.seen == ["down", "enter"]


def test_escape_nobody_takes_cancels_and_other_keys_are_consumed():
    tui = framed("hello")
    modal = Modal(tui, Panel("panel"))
    modal.open()
    for name in ("tab", "c-c", "q", "c-n"):
        assert modal.handle(key(name)) is True
    assert modal.is_open is True and modal.take_result() is None
    assert modal.handle(PasteEvent("dropped")) is True
    assert modal.handle(key("escape")) is True
    assert modal.is_open is False and modal.take_result() is None


def test_a_none_valued_decision_still_closes_the_modal():
    tui = framed("hello")
    dialog = Dialog("", Text("body"), [ButtonSpec("No", None)])
    modal = Modal(tui, dialog)
    modal.open()
    assert modal.handle(key("escape")) is True
    assert modal.is_open is False
    assert modal.take_result() is None
    assert modal.take_result() is None


# -- the one-shot result and the focus trap ----------------------------------


def test_open_pushes_the_dialog_as_a_focus_trap_and_close_pops_it():
    tui = framed("hello")
    outside = Button("outside")
    focus = FocusManager([outside])
    focus.focus_next()
    panel = Panel("panel")
    modal = Modal(tui, panel, focus=focus)
    modal.open()
    assert focus.targets == (panel,)
    assert focus.focused is panel
    assert outside.focused is False
    modal.close()
    assert focus.targets == (outside,)
    assert focus.focused is outside and outside.focused is True


def test_two_stacked_modals_restore_focus_layer_by_layer():
    tui = framed("hello")
    outside = Button("outside")
    focus = FocusManager([outside])
    focus.focus_next()
    first_panel, second_panel = Panel("first"), Panel("second")
    first = Modal(tui, first_panel, focus=focus)
    second = Modal(tui, second_panel, focus=focus)
    first.open()
    second.open()
    assert focus.targets == (second_panel,)
    second.close()
    assert focus.targets == (first_panel,)
    first.close()
    assert focus.targets == (outside,)


def test_take_result_reads_once_and_open_clears_a_stale_value():
    tui = framed("hello")
    modal = Modal(tui, Panel("panel"))
    modal.open()
    modal.close("taken")
    assert modal.take_result() == "taken"
    assert modal.take_result() is None
    modal.close("stale")
    modal.open()
    assert modal.take_result() is None


def test_detach_closes_clears_and_stops_swallowing_events():
    tui = framed("hello")
    modal = Modal(tui, Panel("panel"))
    modal.open()
    modal.close("stale")
    modal.open()
    modal.detach()
    assert modal.is_open is False
    assert modal.take_result() is None
    assert modal.handle(key("x", "x")) is False
    assert modal.handle(press(7, 2)) is False

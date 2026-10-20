"""Tests for motui.interaction.modal (Modal).

The blocking layer around any panel: constructed mounted (the Toasts
lifecycle), it scrims every frame row through the attribute ``dim`` of D4,
places the panel centered or at an anchor (both clamped into the frame) and
routes every event while open -- a press inside at the panel's own
coordinates, a press outside as the dismissal, the keyboard body-first with
``escape`` as the cancel and every other key consumed and dropped.  A
closed modal is the zero-byte case: it hands the layout back and consumes
nothing.
"""

from __future__ import annotations

from _doubles import key, many

from motui.interaction.modal import Modal
from motui.kernel.events import KeyEvent, MouseEvent, PasteEvent
from motui.kernel.lines import Line, Text
from motui.kernel.style import Style
from motui.testing import headless_tui


class _Panel:
    """A modal panel double: rows, a click cell and a small key table.

    ``decisions`` maps a key name to the value the panel writes when it
    consumes it (``None`` is a legal value, the ``None``-valued button);
    ``declined`` names the keys it consumes *without* writing anything (a
    cursor move).  ``click_cell`` is the one rendered cell a click hits,
    writing ``click_value``; every other cell is a miss that writes nothing.
    """

    def __init__(
        self,
        *texts: str,
        decisions: dict | None = None,
        declined: tuple = (),
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
        self.chosen: object | None = None

    def render(self, width: int) -> list[Line]:
        return [Line.from_text(text) for text in self.texts]

    def click(self, row: int, col: int) -> bool:
        self.clicks.append((row, col))
        if self.click_cell != (row, col):
            return False
        self.chosen = self.click_value
        return True

    def handle(self, event) -> bool:
        self.seen.append(_name_of(event))
        if not isinstance(event, KeyEvent):
            return False
        if event.key in self.decisions:
            self.chosen = self.decisions[event.key]
            return True
        return event.key in self.declined


class _Body:
    """A panel body: consumes the keys it takes, records everything it saw."""

    def __init__(self, takes: tuple = ()) -> None:
        self.takes = set(takes)
        self.seen: list[str] = []

    def handle(self, event) -> bool:
        self.seen.append(_name_of(event))
        return _name_of(event) in self.takes


def _name_of(event) -> str:
    """The event's routable name (``paste`` for a paste, which carries none)."""
    return "paste" if isinstance(event, PasteEvent) else event.key


def _framed(*texts: str, width: int = 20, height: int = 5):
    """A painted headless TUI carrying the given content rows."""
    tui = headless_tui(width, height)
    for text in texts:
        tui.add(Text(text))
    tui.paint()
    return tui


def _press(x: int, y: int) -> MouseEvent:
    return MouseEvent("left", x=x, y=y, kind="press")


# --- the lifecycle ---------------------------------------------------------------


def test_a_closed_modal_hands_the_layout_back_and_consumes_nothing():
    """Constructed mounted, closed it is zero bytes -- and the host's keys pass."""
    tui = _framed("hello")
    before = [row.text for row in tui.rows]
    modal = Modal(tui, _Panel("panel"))
    assert modal in tui.frame.overlays  # the Toasts lifecycle: mounted at construction
    assert modal.is_open is False and modal.chosen is None
    tui.paint()
    assert [row.text for row in tui.rows] == before  # nothing painted, nothing scrimmed
    assert modal.handle(key("x", "x")) is False
    assert modal.handle(_press(7, 2)) is False
    assert modal.is_open is False


def test_detach_unregisters_by_identity_and_a_detached_modal_stays_out():
    """The Toasts contract: idempotent, identity-based, and final."""
    tui = _framed("hello")
    before = len(tui.frame.overlays)
    modal = Modal(tui, _Panel("panel"))
    assert len(tui.frame.overlays) == before + 1
    modal.open()
    modal.detach()
    assert modal not in tui.frame.overlays
    modal.detach()  # idempotent: the registry is not charged twice
    assert modal not in tui.frame.overlays
    modal.open()  # a detached modal never re-registers
    assert modal not in tui.frame.overlays
    tui.paint()
    assert all("panel" not in row.text for row in tui.rows)


# --- the paint -------------------------------------------------------------------


def test_open_scrims_every_row_and_centers_the_panel():
    """The D4 veil: colors kept, weight dropped, under the centered box."""
    tui = _framed("hello", "world")
    modal = Modal(tui, _Panel("panel"))
    modal.open()
    tui.paint()
    rows = tui.rows
    assert [row.text[:5] for row in rows[:2]] == ["hello", "world"]  # content kept
    assert rows[0].segments[0].style == Style(dim=True)  # the veil merges under it
    assert rows[1].segments[0].style == Style(dim=True)
    # 20 columns, a 5-wide panel: centered at column 7; 5 rows, one-row panel: row 2.
    assert rows[2].text.find("panel") == 7
    assert len(rows[2].text) == 20  # the frame row stays a full grid
    modal.close()
    tui.paint()
    assert tui.rows[0].segments[0].style == Style()  # close takes the veil with it


def test_a_scrim_off_modal_paints_the_panel_without_the_veil():
    tui = _framed("hello")
    modal = Modal(tui, _Panel("panel"), scrim=False)
    modal.open()
    tui.paint()
    assert tui.rows[0].segments[0].style == Style()
    assert tui.rows[2].text.find("panel") == 7


def test_the_anchor_pins_the_panel_and_the_frame_clamps_it():
    """``anchor=(y, x)`` places the top-left cell, clamped into the frame."""
    tui = _framed("hello")
    pinned = Modal(tui, _Panel("panel"), anchor=(1, 2))
    pinned.open()
    tui.paint()
    assert tui.rows[1].text.find("panel") == 2

    parked = Modal(tui, _Panel("panel"), anchor=(99, 99))
    parked.open()
    tui.paint()
    assert tui.rows[4].text.find("panel") == 15  # the bottom-right corner


def test_a_panel_overrunning_the_frame_is_clipped_to_it():
    """A taller-than-frame panel loses its tail rows; a wide one its tail cells."""
    tui = _framed()
    tall = Modal(tui, _Panel(*many(9)))
    tall.open()
    tui.paint()
    assert [row.text.strip() for row in tui.rows] == many(5)
    tall.close()

    wide = Modal(tui, _Panel("w" * 50))
    wide.open()
    tui.paint()
    # A row that ignored the width it was handed is fit back to the frame.
    assert tui.rows[2].text == "w" * 19 + "\u2026"


# --- the routing -----------------------------------------------------------------


def test_a_press_inside_clicks_at_the_panels_own_coordinates():
    """The modal translates the screen cell and reads the panel's decision."""
    tui = _framed("hello")
    # A two-row panel at rows 1-2, columns 7-11; its gesture sits on its second row.
    panel = _Panel("panel", "rows!", click_cell=(1, 1), click_value="taken")
    modal = Modal(tui, panel)
    modal.open()
    tui.paint()
    assert modal.handle(_press(7, 1)) is True  # inside the panel, off its gesture
    assert panel.clicks == [(0, 0)]
    assert modal.is_open is True and modal.chosen is None
    assert modal.handle(_press(8, 2)) is True  # the panel's own (1, 1) cell
    assert panel.clicks == [(0, 0), (1, 1)]
    assert modal.is_open is False and modal.chosen == "taken"
    modal.chosen = None  # the host reads the result once and resets it
    assert modal.chosen is None


def test_the_rest_of_the_pointer_reports_are_swallowed():
    """Behind a modal nothing drags, hovers or scrolls: no report gets through."""
    tui = _framed("hello")
    panel = _Panel("panel", click_cell=(0, 0), click_value="taken")
    modal = Modal(tui, panel)
    modal.open()
    for kind in ("motion", "release"):
        assert modal.handle(MouseEvent("left", x=7, y=2, kind=kind)) is True
    assert modal.handle(MouseEvent("wheel_down", x=7, y=2, kind="press")) is True
    assert panel.clicks == [] and modal.is_open is True


def test_a_press_outside_dismisses_with_nothing_chosen():
    tui = _framed("hello")
    modal = Modal(tui, _Panel("panel"))
    modal.open()
    assert modal.handle(_press(0, 0)) is True  # outside the centered panel
    assert modal.is_open is False and modal.chosen is None

    held = Modal(tui, _Panel("panel"), dismiss_on_click_outside=False)
    held.open()
    assert held.handle(_press(0, 0)) is True  # consumed, but nothing moved
    assert held.is_open is True and held.chosen is None


def test_the_keyboard_is_body_first_and_the_panel_takes_what_the_body_leaves():
    """The Textual order: the field edits, the button row answers ``enter``."""
    tui = _framed("hello")
    panel = _Panel("panel", decisions={"enter": "ok"}, declined=("down",))
    body = _Body(takes=("x",))
    panel.body = body
    modal = Modal(tui, panel)
    modal.open()

    assert modal.handle(key("x", "x")) is True
    assert body.seen == ["x"] and panel.seen == []  # the body kept it
    assert modal.is_open is True and modal.chosen is None

    assert modal.handle(key("down")) is True
    assert body.seen == ["x", "down"] and panel.seen == ["down"]
    assert modal.is_open is True and modal.chosen is None  # a cursor move decides nothing

    assert modal.handle(key("enter")) is True
    assert panel.seen == ["down", "enter"]
    assert modal.is_open is False and modal.chosen == "ok"

    modal.open()
    assert modal.handle(PasteEvent("text")) is True  # the body's paste, kept by it
    assert body.seen == ["x", "down", "enter", "paste"]
    assert panel.seen == ["down", "enter"]  # a panel with a body never sees a paste


def test_escape_nobody_takes_cancels_and_every_other_key_is_consumed_and_dropped():
    """A modal owns the keyboard: nothing falls through to the host."""
    tui = _framed("hello")
    modal = Modal(tui, _Panel("panel"))
    modal.open()
    for name in ("tab", "c-c", "q", "c-n", "c-o"):
        assert modal.handle(key(name)) is True, name
    assert modal.is_open is True and modal.chosen is None
    assert modal.handle(PasteEvent("no body takes it")) is True  # dropped too
    assert modal.handle(key("escape")) is True  # the fallback cancel
    assert modal.is_open is False and modal.chosen is None


def test_a_none_valued_decision_still_closes_the_modal():
    """A written ``None`` -- the cancel button, a miss-click's row -- is a decision."""
    tui = _framed("hello")
    panel = _Panel("panel", decisions={"enter": None})
    modal = Modal(tui, panel)
    modal.open()
    assert modal.handle(key("enter")) is True
    assert modal.is_open is False and modal.chosen is None

    tui2 = _framed("hello")
    clicking = _Panel("panel", click_cell=(0, 0), click_value=None)
    other = Modal(tui2, clicking)
    other.open()
    tui2.paint()
    assert other.handle(_press(7, 2)) is True
    assert other.is_open is False and other.chosen is None

"""The action primitives and the existing widgets' hover surface.

``Button`` / ``Checkbox`` / ``Link`` are the minimal clickable units: state
plus controller methods, no callbacks -- ``click`` / ``activate`` land the
operation in ``chosen``, which the host reads once -- and ``hover`` /
``focused`` only change rendering.  ``hover_at`` is the row-level half of
the same contract on the existing widgets: it marks the row under the
pointer and answers whether the render changed, and ``row < 0`` clears it
byte-for-byte back to the un-hovered output.
"""

from __future__ import annotations

from mocode_tui.app import TUI
from mocode_tui.core.block import Activable, Clickable, Focusable, Hoverable
from mocode_tui.core.events import MouseEvent
from mocode_tui.core.lines import Line
from mocode_tui.core.screen import HeadlessScreen
from mocode_tui.core.style import Style
from mocode_tui.core.theme import DEFAULT_THEME, Theme
from mocode_tui.focus import FocusRing
from mocode_tui.pointer import Pointer
from mocode_tui.widgets import Button, Checkbox, Link
from mocode_tui.widgets.layout import Padding


def row(component, width: int = 20) -> Line:
    """The component's first rendered row."""
    return component.render(width)[0]


def motion(x: int, y: int) -> MouseEvent:
    return MouseEvent("motion", button=0, x=x, y=y, kind="motion")


def click_event(x: int, y: int, kind: str) -> MouseEvent:
    return MouseEvent("left", button=0, x=x, y=y, kind=kind)


# --- Button ------------------------------------------------------------------


def test_button_renders_one_fitted_row_in_the_accent_band():
    button = Button("Run")
    assert row(button).text == " Run "
    assert row(button).segments[0].style == DEFAULT_THEME.accent
    assert row(button, width=3).text == " R\u2026"  # one row, never wider


def test_button_hover_and_focus_merge_their_bands():
    button = Button("Run")
    assert row(button).segments[0].style == DEFAULT_THEME.accent
    button.hover = True
    assert row(button).segments[0].style == DEFAULT_THEME.accent.merge(DEFAULT_THEME.hover)
    button.hover = False
    button.focused = True
    assert row(button).segments[0].style == DEFAULT_THEME.accent.merge(DEFAULT_THEME.cursor)
    assert row(button).text == " Run "  # the bands never change the text


def test_button_click_and_activate_both_land_in_chosen():
    button = Button("Run")
    assert button.chosen is None
    assert button.click(0, 0) is True and button.chosen is True
    button.chosen = None  # the host reads once and resets
    assert button.activate() is True and button.chosen is True
    button.chosen = None
    assert button.click(9, 40) is True  # every cell is the button
    assert button.chosen is True


def test_explicit_styles_beat_the_theme_fields():
    theme = Theme(accent=Style(fg="#ff0000"), hover=Style(bg="#00ff00"))
    button = Button("x", style=Style(underline=True), hover_style=Style(italic=True), theme=theme)
    assert row(button).segments[0].style == Style(underline=True)
    button.hover = True
    assert row(button).segments[0].style == Style(underline=True).merge(Style(italic=True))


# --- Checkbox ------------------------------------------------------------------


def test_checkbox_flips_its_mark_and_mirrors_it_into_chosen():
    box = Checkbox("Bold")
    assert row(box).text == "[ ] Bold"
    assert box.activate() is True
    assert (box.checked, box.chosen) == (True, True)
    assert row(box).text == "[x] Bold"
    assert row(box).segments[0].style == DEFAULT_THEME.accent
    box.chosen = None  # the host reads once and resets
    assert box.click(0, 0) is True
    assert (box.checked, box.chosen) == (False, False)


# --- Link ------------------------------------------------------------------


def test_link_follows_a_click_and_wears_the_link_band():
    link = Link("docs/COMPONENTS.md")
    assert row(link).text == "docs/COMPONENTS.md"
    assert row(link).segments[0].style == DEFAULT_THEME.link
    link.hover = True
    assert row(link).segments[0].style == DEFAULT_THEME.link.merge(DEFAULT_THEME.hover)
    link.hover = False
    assert link.chosen is None
    assert link.click(0, 3) is True and link.chosen is True


# --- capabilities ---------------------------------------------------------------


def test_the_action_primitives_declare_their_capabilities():
    button = Button("B")
    assert isinstance(button, Hoverable) and isinstance(button, Focusable)
    assert isinstance(button, Clickable) and isinstance(button, Activable)
    checkbox = Checkbox("C")
    for protocol in (Hoverable, Focusable, Clickable, Activable):
        assert isinstance(checkbox, protocol)
    link = Link("L")
    assert isinstance(link, Hoverable) and isinstance(link, Clickable)
    assert not isinstance(link, Activable)  # a link is not a focus main action
    assert not isinstance(link, Focusable)


# --- with the pointer and the ring ------------------------------------------------


def test_a_pointer_ring_click_completes_a_button_wrapped_in_padding():
    button = Button("Run")
    tui = TUI(screen=HeadlessScreen(40, 8, hover=True), interactive=False)
    tui.add(Padding(button, left=1, top=1))
    tui.paint()
    ring = FocusRing([button])  # a one-target ring focuses it at construction
    pointer = Pointer(tui, ring=ring)
    assert pointer.handle(motion(2, 1)) is True  # the wrapper descends to it
    assert button.hover is True and pointer.hovered is button
    pointer.handle(click_event(2, 1, "press"))
    assert pointer.handle(click_event(2, 1, "release")) is True
    assert button.chosen is True  # the focused target's click activates

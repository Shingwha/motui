"""Tests for mocode_tui.chrome.Stats (the developer overlay, D14).

The overlay's whole contract: constructed mounted and detaching by identity,
the box in the frame's top-right corner with the four readings (frames and
the window rate, the events it counted and the last one's name, the hovered
leaf and the pointer's cell), ``handle`` counting every event as a repaint
cue, the frame-rate window arithmetic under a replaced clock, and the band
following the theme.  Nothing sleeps: the clock is replaced, the frames are
painted on a headless screen.
"""

import pytest

from mocode_tui import (
    Button,
    HeadlessScreen,
    Key,
    MouseEvent,
    Paste,
    Pointer,
    Stats,
    Style,
    Theme,
    TUI,
)
from mocode_tui.core.style import sgr_prefix


def _mounted(width: int = 40, height: int = 8):
    """A headless TUI with one Button block and a mounted Stats overlay."""
    tui = TUI(screen=HeadlessScreen(width, height), interactive=False)
    tui.add(Button("Ship"))
    tui.paint()
    return tui, Stats(tui, pointer=Pointer(tui))


def _box_rows(tui: TUI) -> list[str]:
    """The three box rows' stripped text (the box is the first three rows)."""
    return [row.text.strip() for row in tui.rows[:3]]


# --- lifecycle -----------------------------------------------------------------


def test_constructing_registers_the_overlay_and_detach_unregisters_it():
    """The Tooltip contract: constructed mounted, detach() idempotent."""
    tui = TUI(screen=HeadlessScreen(40, 8), interactive=False)
    before = len(tui.frame.overlays)
    stats = Stats(tui)
    assert len(tui.frame.overlays) == before + 1
    assert stats in tui.frame.overlays
    stats.detach()
    assert stats not in tui.frame.overlays
    assert len(tui.frame.overlays) == before
    stats.detach()  # idempotent: the registry is not charged twice
    assert stats not in tui.frame.overlays


def test_a_detached_overlay_paints_nothing_again():
    """After detach the corner is the pane's own again (the zero-byte case)."""
    tui, stats = _mounted()
    tui.paint()
    assert "frames " in tui.rows[0].text
    stats.detach()
    tui.paint()
    assert "frames " not in "".join(row.text for row in tui.rows)
    assert " Ship " in tui.rows[0].text


def test_a_frame_with_no_room_for_the_box_stays_total():
    """A screen with no column cannot host the box: painting never raises."""
    tui = TUI(screen=HeadlessScreen(0, 5), interactive=False)
    Stats(tui)
    tui.paint()
    assert all(not row.text for row in tui.rows)


# --- the readings ---------------------------------------------------------------


def test_handle_counts_every_event_and_names_the_last_one():
    """Every event counts -- key, mouse report, paste -- and answers True."""
    tui = TUI(screen=HeadlessScreen(40, 8), interactive=False)
    stats = Stats(tui)
    assert stats.events == 0 and stats.last == ""  # nothing counted yet
    assert stats.handle(Key("c-g")) is True  # the repaint cue, never a claim
    assert stats.handle(MouseEvent("left", button=0, x=1, y=2, kind="press")) is True
    assert stats.handle(Paste("two\nlines")) is True
    assert stats.events == 3
    assert stats.last == "paste"  # a paste carries no name of its own


def test_the_box_paints_in_the_top_right_corner_with_every_reading():
    """Three rows, flush right, carrying frames/fps, events/last and hover."""
    tui, stats = _mounted()
    stats.handle(Key("c-g"))
    stats.handle(Paste("no name of its own"))
    stats.pointer.handle(MouseEvent("none", button=0, x=1, y=0, kind="motion"))
    tui.paint()

    lines = [row.text for row in tui.rows[:3]]
    frames = tui.painter.frames - 1  # the frame being painted is not counted yet
    assert lines[0].rstrip().endswith(f"frames {frames}    0.0 fps")  # padded to the box
    assert lines[1].strip() == "events 2  last paste"
    assert lines[2].strip() == "hover Button (1, 0)"

    # Flush right: one left edge for the box, and every row ends at the edge.
    offsets = {len(line) - len(line.lstrip()) for line in lines[1:]}
    assert len(offsets) == 1
    assert {len(line) for line in lines} == {40}


def test_the_box_reads_the_hovered_leaf_and_the_pointer_cell():
    """The hover row follows the pointer's live state, cleared to ``--``."""
    tui, stats = _mounted()
    stats.pointer.handle(MouseEvent("none", button=0, x=1, y=0, kind="motion"))
    tui.paint()
    assert _box_rows(tui)[2] == "hover Button (1, 0)"
    stats.pointer.clear()  # a pane switch, a blur: the hover is gone
    tui.paint()
    assert _box_rows(tui)[2] == "hover --"


def test_a_host_can_point_the_overlay_at_a_rebuilt_pointer():
    """The gallery rebuilds its pointer per page: the box follows the new one."""
    tui, stats = _mounted()
    fresh = Pointer(tui)
    stats.pointer = fresh  # the retarget the gallery's page switch performs
    fresh.handle(MouseEvent("none", button=0, x=1, y=0, kind="motion"))
    tui.paint()
    assert _box_rows(tui)[2] == "hover Button (1, 0)"


def test_the_frame_rate_is_sampled_over_a_window_of_at_least_a_second():
    """The session's own arithmetic, driven by a replaced clock.

    Frames painted: one per ``paint()`` call, counted at composition time,
    so each line below reads the count *before* its own frame.
    """
    tui = TUI(screen=HeadlessScreen(40, 8), interactive=False)
    now = [100.0]
    tui.clock = lambda: now[0]  # the documented seam: a test replaces the clock
    stats = Stats(tui)
    tui.paint()
    tui.paint()  # two frames before the window opens
    assert stats.fps == 0.0
    now[0] = 102.0
    tui.paint()  # the window opens: 2 frames over 2 s
    assert stats.fps == pytest.approx(1.0)
    now[0] = 102.5
    tui.paint()  # half a second since the sample: too short a window to read
    assert stats.fps == pytest.approx(1.0)
    now[0] = 103.0
    tui.paint()  # a full second since the sample: 2 more frames over 1 s
    assert stats.fps == pytest.approx(2.0)


def test_the_band_follows_a_theme_change():
    """``set_theme`` repaints the box on the theme's ``toast`` band."""
    tui, stats = _mounted()
    band = Style(bg="#123456")
    stats.set_theme(Theme(toast=band))
    marker = len(tui.screen.output)
    tui.paint()
    assert sgr_prefix(band, "truecolor") in tui.screen.output[marker:]

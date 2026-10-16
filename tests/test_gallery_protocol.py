"""The gallery's protocol wiring: the window title per page, the cursor shape.

The host half of the title / cursor-shape story: the library's ansi helpers
and :class:`TUI` methods have their own tests, and these two probes drive the
real gallery session to prove its wiring -- ``show`` titles the window after
the page, and the host loop asks for the focused leaf's shape.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "examples"))

from mocode_tui import HeadlessScreen, TUI  # noqa: E402
from mocode_tui.core.ansi import cursor_shape, set_window_title  # noqa: E402

from gallery.registry import BY_NAME  # noqa: E402
from gallery.session import Gallery  # noqa: E402


def _mounted() -> tuple[TUI, Gallery]:
    """The gallery mounted on a headless screen, with its output readable."""
    tui = TUI(screen=HeadlessScreen(100, 30), interactive=False)
    return tui, Gallery(tui)


def test_show_writes_the_page_title_and_the_focused_fields_cursor_shape():
    tui, gallery = _mounted()
    marker = len(tui.screen.output)
    gallery.show(BY_NAME["input"])  # the page's ring focuses an Editor first
    fresh = tui.screen.output[marker:]
    assert set_window_title("mocode-tui gallery \u00b7 input") in fresh
    assert cursor_shape("beam") in fresh  # the Editor declares a bar cursor


def test_a_plain_widget_ring_brings_the_block_shape_back():
    tui, gallery = _mounted()
    gallery.show(BY_NAME["input"])
    marker = len(tui.screen.output)
    gallery.show(BY_NAME["choice"])  # the ring focuses a Select, not a field
    fresh = tui.screen.output[marker:]
    assert set_window_title("mocode-tui gallery \u00b7 choice") in fresh
    assert cursor_shape("block") in fresh
    assert cursor_shape("beam") not in fresh  # and no stale shape is repeated

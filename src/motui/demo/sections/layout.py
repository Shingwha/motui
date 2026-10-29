"""The layout section: the constraint drills, driven from the keys.

Four drills share one frame, switched with the number keys:

* **split** -- two panes share the width; the arrows move the sash and both
  panes report the columns they actually got.
* **dock** -- a one-rule dock pins north, south, west or east under the
  arrows; the free area reports what it still holds.
* **scroll** -- a long source file (one measured line wider than any pane)
  in a two-axis :class:`ScrollPanel`: every arrow scrolls, and the long line
  can be scrolled to its very tail.
* **wide table** -- a ten-column manifest whose natural grid is wider than
  the pane in a horizontally scrolling panel: ``left``/``right`` walk to the
  last column.

No animation and no clock: the drills answer the keys and read back real
geometry, so a fresh scene always replays the same bytes.
"""

from __future__ import annotations

from ...kernel.cell import Line, Segment, Surface
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.layout import Constraints
from ...kernel.text import WrapMode
from ...kernel.theme import Theme
from ...widgets import Column, Editor, Panel, Row, ScrollPanel, Table, Tabs, Text
from ..scene import Scene

__all__ = ["LayoutScene"]

_CLIP = WrapMode.CLIP

#: The drills, in tour order; the number keys select them.
_DRILLS = ("split", "dock", "scroll", "wide table")

#: The dock's side-strip width, and the split sash's granularity.
_STRIP_W = 7
_SASH_STEPS = 24

#: The long file the scroll drill windows: one measured line far wider than
#: any pane, so "scroll right to the tail" is a real journey.
_LONG_CODE = '''\
"""uplink.py -- one console, both axes wide."""

UPLINK = {
    "station": "DSN-07",
    "sector": "N-42",
    # One measured line, wider than any pane -- scroll right to its tail:
    "mission": "maintain the deep-space signal through solar wind, reroute packets across the relay mesh, and recover a clean lock",
    "relays": {"andromeda": 42, "borealis": 68, "cygnus": 31},
}

def mean_ping(uplink):
    return sum(uplink["relays"].values()) / len(uplink["relays"])
'''

#: The wide table's seed manifest: ten columns, natural grid ~120 columns.
_WIDE_HEADERS = (
    "vessel",
    "home port",
    "tonnage",
    "crew",
    "range nm",
    "launched",
    "flag",
    "cargo",
    "notes",
    "outcome",
)
_WIDE_ROWS: tuple[tuple[str, ...], ...] = (
    (
        "Argo",
        "Iolcus",
        "84",
        "52",
        "1200",
        "1263 BC",
        "Thessaly",
        "wool",
        "heroic complement, one keel",
        "reached Colchis",
    ),
    (
        "Pequod",
        "Nantucket",
        "358",
        "30",
        "18000",
        "1841",
        "United States",
        "oil",
        "three-year whaling cruise",
        "sunk by the white whale",
    ),
    (
        "Nautilus",
        "Nantes",
        "1400",
        "22",
        "25000",
        "1870",
        "France",
        "specimens",
        "electric drive, library aft",
        "circumnavigated",
    ),
    (
        "Endurance",
        "London",
        "348",
        "28",
        "10000",
        "1912",
        "United Kingdom",
        "none",
        "bespoke for polar ice",
        "crushed, all hands saved",
    ),
    (
        "Rainbow",
        "Rotterdam",
        "2600",
        "35",
        "30000",
        "1928",
        "Netherlands",
        "reefer",
        "fast cargo, cold chain",
        "on schedule",
    ),
)


class LayoutScene(Scene):
    """The layout drills: split, dock and two scrolls you can drive.

    ``1``-``4`` pick the drill; the arrows mean what the drill says.  The
    split's sash and the dock's side are plain state, and both scroll
    panels answer the arrows themselves -- ``left``/``right`` step four
    columns on the horizontal axis, everything else routes into the panel's
    own key table.  ``escape`` returns to the menu, ``q`` quits.  The
    readout row under the body reads the live geometry off the last render,
    so the numbers are always what the pixels show.
    """

    name = "layout"

    def __init__(self, theme: Theme) -> None:
        super().__init__(theme)
        self._drill = 0
        self._split = 12  # of _SASH_STEPS: the west pane's share
        self._dock = "north"
        self.tabs = Tabs(list(_DRILLS), theme=theme)
        self.tabs.focused = True

        self._code = Editor(_LONG_CODE, wrap=WrapMode.OVERFLOW, theme=theme)
        self._code.focused = False
        self._code_scroll = ScrollPanel(
            self._code, bar=True, axis="both", theme=theme
        )
        self._table = Table(
            [list(row) for row in _WIDE_ROWS], headers=list(_WIDE_HEADERS),
            cell_wrap=WrapMode.OVERFLOW,
            theme=theme,
        )
        self._wide_scroll = ScrollPanel(
            self._table, bar=True, axis="x", theme=theme
        )

    def enter(self) -> None:
        super().enter()
        self._drill = 0
        self._split = 12
        self._dock = "north"
        self.tabs.select(0)
        self._code_scroll.scroll_to(0)
        self._code_scroll.scroll_to_x(0)
        self._wide_scroll.scroll_to(0)
        self._wide_scroll.scroll_to_x(0)

    @property
    def drill(self) -> int:
        return self._drill

    @property
    def wide_scroll(self):
        return self._wide_scroll

    @property
    def code_scroll(self):
        return self._code_scroll

    # -- rendering ---------------------------------------------------------------

    def render(self, c: Constraints, phase: int) -> Surface:
        self._phase = phase
        width = c.width
        height = c.max_height if c.max_height is not None else 24
        body_h = max(4, height - 5)
        self.tabs.select(self._drill)
        strip = list(self.tabs.render(Constraints(width=width)))
        tab_row = strip[0] if strip else Line()
        rows: list[Line] = [
            self._heading_line(),
            tab_row,
            *self._body(width, body_h),
        ]
        rows.append(self._readout_line(width))
        rows.append(self._hint_line())
        rows = [row.clip(_CLIP, width) for row in rows[:height]]
        return Surface.of(rows, width)

    def _heading_line(self) -> Line:
        """The one-row title: the section's name and its one-line pitch."""
        return Line(
            (
                Segment("VIEWPORT LAB", self.theme.content.accent),
                Segment(" \u00b7 one console, every constraint", self.theme.text.faint),
            )
        )

    def _body(self, width: int, height: int) -> list[Line]:
        """The active drill's body, padded to exactly ``height`` rows."""
        if self._drill == 0:
            rows = self._split_body(width)
        elif self._drill == 1:
            rows = self._dock_body(width, height)
        elif self._drill == 2:
            rows = self._scroll_body(width, height)
        else:
            rows = self._wide_body(width, height)
        rows.extend(Line() for _ in range(height - len(rows)))
        return rows[:height]

    def _split_body(self, width: int) -> list[Line]:
        """Two panes share the width at the sash's position."""
        gap = 1
        usable = max(2, width - gap)
        left_w = max(8, usable * self._split // _SASH_STEPS)
        right_w = max(1, usable - left_w)
        west = Panel(
            self._share_card("west", left_w - 4),
            title="west",
            theme=self.theme,
        )
        east = Panel(
            self._share_card("east", right_w - 4),
            title="east",
            theme=self.theme,
        )
        row = Row([west, east], widths=[left_w, None], gap=gap)
        return list(row.render(Constraints(width=width)))

    def _share_card(self, name: str, cols: int) -> Column:
        """One pane's card: what it is and the columns it really got."""
        return Column(
            [
                Text(f"the {name} pane", style=self.theme.content.accent, theme=self.theme),
                Text(
                    f"{max(1, cols)} content columns",
                    style=self.theme.text.base,
                    theme=self.theme,
                ),
                Text(
                    "resize me with the arrows",
                    style=self.theme.text.faint,
                    theme=self.theme,
                ),
            ],
            gap=1,
        )

    def _dock_body(self, width: int, height: int) -> list[Line]:
        """The dock pinned to one side; the free area carries the readout."""
        side = self._dock
        strip_w = _STRIP_W if side in ("west", "east") else 0
        strip_h = 1 if side in ("north", "south") else 0
        free_w = max(1, width - strip_w)
        free_h = max(1, height - strip_h)
        centre = Panel(
            Column(
                [
                    Text(f"docked {side}", style=self.theme.content.accent, theme=self.theme),
                    Text(
                        f"free {free_w} x {free_h}",
                        style=self.theme.text.base,
                        theme=self.theme,
                    ),
                ],
                gap=1,
            ),
            title="free area",
            theme=self.theme,
        )
        centre_rows = list(centre.render(Constraints(width=free_w)))
        free: list[Line] = []
        for row in range(free_h):
            if row < len(centre_rows) and side != "west":
                free.append(centre_rows[row])
            elif row < len(centre_rows):
                free.append(Line((Segment(" " * strip_w),)) + centre_rows[row])
            else:
                free.append(Line((Segment(" " * strip_w),)) if side == "west" else Line())
        if side == "north":
            free.insert(0, self._dock_rule(width, side))
        elif side == "south":
            free.append(self._dock_rule(width, side))
        else:
            dressed: list[Line] = []
            middle = len(free) // 2
            for index, row in enumerate(free):
                if side == "west":
                    strip = " dock " if index == middle else " " * 6
                    dressed.append(
                        Line((Segment(f"\u258e{strip}", self.theme.content.accent),)) + row
                    )
                else:
                    strip = " dock " if index == middle else " " * 6
                    dressed.append(
                        row + Line((Segment(f"{strip}\u258f", self.theme.content.accent),))
                    )
            free = dressed
        return [row.clip(_CLIP, width) for row in free]

    def _dock_rule(self, width: int, side: str) -> Line:
        """The one-row horizontal dock: an accent rule with its label inside."""
        label = f" dock \u00b7 {side} "
        left = max(0, (width - len(label)) // 2)
        text = "\u2550" * left + label + "\u2550" * max(0, width - left - len(label))
        return Line((Segment(text[:width], self.theme.content.accent),))

    def _scroll_body(self, width: int, height: int) -> list[Line]:
        """The long file in a two-axis window with both bars."""
        self._code_scroll.height = height
        rows = list(self._code_scroll.render(Constraints(width=width)))
        rows.extend(Line() for _ in range(height - len(rows)))
        return rows[:height]

    def _wide_body(self, width: int, height: int) -> list[Line]:
        """The wide manifest in a horizontally scrolling window."""
        self._wide_scroll.height = height
        rows = list(self._wide_scroll.render(Constraints(width=width)))
        rows.extend(Line() for _ in range(height - len(rows)))
        return rows[:height]

    def _readout_line(self, width: int) -> Line:
        """The live geometry row: the numbers behind the pixels."""
        faint = self.theme.text.faint
        if self._drill == 0:
            text = f"sash {self._split}/{_SASH_STEPS} \u00b7 \u2190\u2192 move it"
        elif self._drill == 1:
            text = f"dock {self._dock} \u00b7 \u2191\u2193\u2190\u2192 re-dock"
        elif self._drill == 2:
            panel = self._code_scroll
            text = (
                f"row {panel.offset}/{panel.total_rows}"
                f" \u00b7 col {panel.x_offset}/{panel.total_columns}"
                " \u00b7 \u2190\u2192 four columns"
            )
        else:
            panel = self._wide_scroll
            text = (
                f"col {panel.x_offset}/{panel.total_columns}"
                " \u00b7 \u2192 walks to the last column"
            )
        return Line((Segment(text, faint),)).clip(_CLIP, width)

    def _hint_line(self) -> Line:
        """The one-row key hint bar."""
        faint = self.theme.text.faint
        accent = self.theme.content.accent
        return Line(
            (
                Segment("esc", accent),
                Segment(" menu \u00b7 ", faint),
                Segment("q", accent),
                Segment(" quit \u00b7 1-4 pick the drill", faint),
            )
        )

    # -- behaviour ---------------------------------------------------------------

    def tick(self, phase: int) -> str | None:
        self._phase = phase
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        key = event.key
        if key == "escape":
            return "menu"
        if key == "q":
            return "quit"
        if key in ("1", "2", "3", "4"):
            self._drill = int(key) - 1
            return None
        if self._drill == 0:
            if key == "left":
                self._split = max(4, self._split - 1)
            elif key == "right":
                self._split = min(_SASH_STEPS - 4, self._split + 1)
        elif self._drill == 1:
            if key == "up":
                self._dock = "north"
            elif key == "down":
                self._dock = "south"
            elif key == "left":
                self._dock = "west"
            elif key == "right":
                self._dock = "east"
        elif self._drill == 2:
            if key == "left":
                self._code_scroll.scroll_x_by(-4)
            elif key == "right":
                self._code_scroll.scroll_x_by(4)
            else:
                self._code_scroll.on_key(event)
        else:
            if key == "left":
                self._wide_scroll.scroll_x_by(-4)
            elif key == "right":
                self._wide_scroll.scroll_x_by(4)
            else:
                self._wide_scroll.on_key(event)
        return None

    def on_click(self, pos: Pos) -> str | None:
        """A click on the drill strip selects that drill."""
        if pos.y == 1 and self.tabs.on_click(Pos(x=pos.x, y=0)):
            self._drill = self.tabs.index
        return None

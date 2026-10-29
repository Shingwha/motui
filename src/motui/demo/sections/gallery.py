"""The gallery section: real 2.0 widgets live on one page."""

from __future__ import annotations

import math

from ...kernel.cell import Line, Surface
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.layout import Constraints
from ...kernel.theme import Theme
from ...widgets import (
    Column,
    Divider,
    Input,
    Markdown,
    Panel,
    ProgressBar,
    Row,
    Slider,
    Table,
    Text,
    Tree,
    TreeNode,
)
from ..scene import Scene
from ..version import DEMO_BAND

__all__ = ["GalleryScene"]


class GalleryScene(Scene):
    """A live page of real 2.0 components, not pictures of them.

    Three panes share the width: a ``Tree`` (fold/unfold and a cursor), a
    ``Table`` (a row cursor) and a controls column holding a short
    ``Markdown`` note, an animated ``ProgressBar``, a ``Slider`` and an
    ``Input``.  ``tab`` cycles the focus between the four interactive
    widgets; the arrows and typing go to the focused one.  ``esc`` returns
    to the menu, and the layout is composed with ``Row``/``Column`` and
    real constraints, so 80x24 and 100x30 both reflow without a fixed
    width assumption.
    """

    name = "gallery"

    def __init__(self, theme: Theme) -> None:
        super().__init__(theme)
        self._focus = 0
        self._top = 0
        self.tree = Tree(
            [
                TreeNode(
                    "app",
                    [
                        TreeNode("shell"),
                        TreeNode("gallery"),
                        TreeNode("inspector"),
                    ],
                    expanded=True,
                ),
                TreeNode("workspace", [TreeNode("runtime")], expanded=True),
            ],
            theme=theme,
        )
        self.table = Table(
            ["widget", "role"],
            [
                ["Tree", "fold"],
                ["Table", "grid"],
                ["Slider", "value"],
                ["Input", "type"],
            ],
            theme=theme,
        )
        self.table.index = 1
        self.markdown = Markdown(
            f"**{DEMO_BAND} in one page**\n\n"
            "Every block here is a real widget:\n\n"
            "- `Tree` folds\n"
            "- `Table` selects\n"
            "- `Slider` steps\n"
            "- `Input` types\n",
            theme=theme,
        )
        self.progress = ProgressBar(0.6, label="render", theme=theme)
        self.slider = Slider(7, maximum=10, theme=theme)
        self.input = Input("type here", placeholder="type\u2026", theme=theme)
        self._targets = [self.tree, self.table, self.slider, self.input]
        self._set_focus(0)
        self._title = Text("COMPONENT ARCHIVE", style=theme.content.accent, theme=theme)
        self._divider = Divider(label="the widget bench", theme=theme)
        self._hint = Text(
            "tab focus \u00b7 \u2191\u2193 rows \u00b7 \u2190\u2192 value \u00b7 "
            "esc menu",
            style=theme.text.faint,
            theme=theme,
        )
        controls = Column(
            [self.markdown, self.progress, self.slider, self.input], gap=0
        )
        body = Row(
            [
                Panel(self.tree, title="tree", theme=theme),
                Panel(self.table, title="table", theme=theme),
                Panel(controls, title="controls", theme=theme),
            ],
            gap=1,
        )
        self._root = Column(
            [self._title, self._divider, body, self._hint], gap=1
        )

    @property
    def focus(self) -> int:
        """The index of the focused interactive widget."""
        return self._focus

    @property
    def origin(self) -> int:
        """The top row of the centred block in the last render."""
        return self._top

    def enter(self) -> None:
        super().enter()
        self._set_focus(0)
        self.input.text = "type here"
        self.table.index = 1

    def _set_focus(self, index: int) -> None:
        """Place the demo's own focus on one interactive widget."""
        self._focus = index % len(self._targets)
        for position, target in enumerate(self._targets):
            target.focused = position == self._focus

    def render(self, c: Constraints, phase: int) -> Surface:
        self._phase = phase
        width = c.width
        height = c.max_height if c.max_height is not None else 24
        rows = list(self._root.render(Constraints(width=width)))
        top = max(0, (height - len(rows)) // 2)
        self._top = top
        rows = [Line() for _ in range(top)] + rows
        return Surface.of(rows, width)

    def tick(self, phase: int) -> str | None:
        self._phase = phase
        self.progress.fraction = 0.55 + 0.4 * math.sin(phase / 60)
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        key = event.key
        if key == "escape":
            return "menu"
        if key in ("tab", "s-tab", "backtab"):
            step = -1 if key in ("s-tab", "backtab") else 1
            self._set_focus(self._focus + step)
            return None
        target = self._targets[self._focus]
        if key == "q" and not isinstance(target, Input):
            return "quit"
        target.on_key(event)
        return None

    def on_click(self, pos: Pos) -> str | None:
        row = pos.y - self._top
        if row < 0:
            return None
        current: object = self._root
        r, c = row, pos.x
        for _ in range(16):
            child_at = getattr(current, "child_at", None)
            if child_at is None:
                break
            found = child_at(r, c)
            if found is None:
                break
            current, r, c = found
        for index, target in enumerate(self._targets):
            if current is target:
                self._set_focus(index)
                # Route the click into the focused component, not just the
                # gallery's own focus.  A branch row in the Tree is clicked
                # to fold/unfold it (desktop-tree semantics); every other
                # widget gets its own on_click at the local cell.
                if target.on_click(Pos(x=c, y=r)) and target is self.tree:
                    target.on_action("activate")
                break
        return None

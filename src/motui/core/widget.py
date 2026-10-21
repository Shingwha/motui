"""Widget: the base every interactive component shares.

A widget owns the four mutable inputs the runtime writes -- its theme, its
:class:`~motui.core.theme.Styles` overrides, and the ``focused`` / ``hover``
flags -- and answers the interaction verbs with their no-op defaults.  It
deliberately is **not** :class:`~motui.core.theme.Themed`: the older base
resolves every style at construction, while a widget keeps the theme value
and reads the role group it paints when it renders, so assigning a new
``theme`` repaints a mounted widget without rebuilding it.

Subclasses implement :meth:`render` and override only the verbs they take.
A pure renderer need not inherit this class at all: :class:`Component` --
one ``render(width)`` -- remains the rendering obligation.
"""

from __future__ import annotations

from .events import Event
from .lines import Line
from .theme import DEFAULT_THEME, Styles, Theme

__all__ = ["Widget"]


class Widget:
    """The shared state and no-op verbs of an interactive component.

    ``theme is None`` means "inherit the App theme"; ``styles`` overrides
    whole role groups and leaves every ``None`` field to the theme.  Both
    stay readable and writable so the runtime can retheme a mounted widget,
    and :meth:`revision` implementations must include them in their value
    snapshot so a block's row cache sees the change.
    """

    __slots__ = ("theme", "styles", "focused", "hover")

    def __init__(
        self, theme: Theme | None = None, styles: Styles | None = None
    ) -> None:
        self.theme = theme
        self.styles = styles
        self.focused = False
        self.hover = False

    @property
    def _theme(self) -> Theme:
        """The effective theme: the explicit one, else :data:`DEFAULT_THEME`."""
        return self.theme or DEFAULT_THEME

    def group(self, name: str) -> object:
        """The role group ``name``: the ``styles`` override, else the theme's."""
        if self.styles is not None:
            override = getattr(self.styles, name, None)
            if override is not None:
                return override
        return getattr(self._theme, name)

    def render(self, width: int) -> list[Line]:
        """Paint the widget's rows; every concrete widget implements this."""
        raise NotImplementedError

    # -- optional interaction verbs: no-ops by default ----------------------

    def handle(self, event: Event) -> bool:
        """Consume one event; a widget that takes no events declines."""
        return False

    def click(self, row: int, col: int) -> bool:
        """Take a click on one cell; a widget that has no click declines."""
        return False

    def hover_at(self, row: int, col: int) -> bool:
        """Move the pointer onto one cell; a widget without rows declines."""
        return False

    def activate(self) -> bool:
        """Take the activation verb; a widget without one declines."""
        return False

    def take_result(self) -> object | None:
        """Read the one-shot result; a widget without one answers ``None``."""
        return None

    def revision(self) -> object | None:
        """The row cache's change token; ``None`` disables caching."""
        return None

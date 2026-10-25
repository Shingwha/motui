"""Widget: the base every interactive component shares.

A widget owns the four mutable inputs the runtime writes -- its theme, its
:class:`~motui.kernel.theme.Styles` overrides, and the ``focused`` / ``hover``
flags -- and answers the interaction verbs with their no-op defaults.  It
deliberately is **not** :class:`~motui.kernel.theme.Themed`: the older base
resolves every style at construction, while a widget keeps the theme value
and reads the role group it paints when it renders, so assigning a new
``theme`` repaints a mounted widget without rebuilding it.

Subclasses implement :meth:`render` and override only the verbs they take.
A pure renderer need not inherit this class at all: :class:`Component` --
one ``render(c) -> Surface`` -- remains the rendering obligation.

2.0 adds the explicit tree the runtime will derive facts from: ``parent`` /
``children``, :meth:`walk`, :meth:`touch` and the ``generation`` counter.
The tree is strictly additive -- the 1.x verbs keep their signatures and
defaults, no component has to adopt the tree to keep working, and
:meth:`revision` still answers ``None`` so no existing row cache changes.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import cast

from ..kernel.events import Event
from ..kernel.cell import Surface
from ..kernel.layout import Constraints
from ..kernel.theme import DEFAULT_THEME, Styles, Theme

__all__ = ["Widget"]


class Widget:
    """The shared state and no-op verbs of an interactive component.

    ``theme is None`` means "inherit the App theme"; ``styles`` overrides
    whole role groups and leaves every ``None`` field to the theme.  Both
    stay readable and writable so the runtime can retheme a mounted widget,
    and :meth:`revision` implementations must include them in their value
    snapshot so a block's row cache sees the change.

    **The tree.**  ``parent`` points at the widget that owns this one and
    ``children`` lists the widgets this one owns.  The pointers are a plain
    convention, not a registration: assigning ``children`` sets each child's
    ``parent`` (a child without a ``parent`` attribute is left alone, so a
    container may hold pure ``Component`` values), while assigning ``parent``
    never rewrites anybody's ``children``.  :meth:`walk` reads the tree
    defensively -- a shared child appears once, a cycle cannot hang it, and
    a child that is not a widget is still visited.

    **Invalidation.**  Assigning any public attribute calls :meth:`touch`,
    which bumps this widget's ``generation`` and every ancestor's -- the
    monotone counter a row cache will key on (nothing reads it in this
    wave).  Underscore attributes are internal bookkeeping and stay silent,
    and ``parent`` itself is tree plumbing, not state.  A widget that mutates
    a value in place (a list, a buffer) calls :meth:`touch` itself; the
    setter cannot see that change.
    """

    __slots__ = (
        "_generation",
        "children",
        "focused",
        "hover",
        "parent",
        "styles",
        "theme",
    )

    #: Whether this widget owns the focus of its descendants: the App
    #: registers the widget itself and skips its subtree (a ``Form`` routes
    #: every field's keys through its own ``handle``).
    owns_focus = False

    def __init__(
        self, theme: Theme | None = None, styles: Styles | None = None
    ) -> None:
        # The initial state is installed with ``object.__setattr__`` on
        # purpose: construction is not a change, so it must not bump the
        # generation or notify an ancestor (there is none yet).  The tree
        # slots come first because the setter for ``children`` reads both.
        object.__setattr__(self, "parent", None)
        object.__setattr__(self, "children", [])
        object.__setattr__(self, "_generation", 0)
        object.__setattr__(self, "theme", theme)
        object.__setattr__(self, "styles", styles)
        object.__setattr__(self, "focused", False)
        object.__setattr__(self, "hover", False)

    def __setattr__(self, name: str, value: object) -> None:
        """Assign one attribute and touch the tree for a public change.

        The three rules, in order:

        * ``parent`` is plumbing: assign it as is, never touch (a reparent
          is a structural edit, not a content change);
        * ``children`` is structural and content-bearing: materialise the
          iterable as a list, point every child that has a ``parent``
          attribute at this widget, and touch;
        * an underscore name is private bookkeeping: assign it silently;
        * anything else is state: assign it and touch.

        A widget whose class skips :meth:`__init__` still assigns safely:
        :meth:`touch` reads ``_generation`` and ``parent`` with defaults.
        """
        if name == "parent":
            object.__setattr__(self, name, value)
            return
        if name == "children":
            items = list(cast("Iterable[object]", value))
            object.__setattr__(self, name, items)
            for child in items:
                if hasattr(child, "parent"):
                    object.__setattr__(child, "parent", self)
            self.touch()
            return
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        object.__setattr__(self, name, value)
        self.touch()

    @property
    def generation(self) -> int:
        """How many changes this widget's subtree has seen (monotone).

        Every :meth:`touch` on this widget or any descendant increments it
        once.  ``0`` on a freshly constructed widget; nothing resets it, so
        an equal value between two reads proves no touch landed in between.
        """
        return getattr(self, "_generation", 0)

    def touch(self) -> None:
        """Mark this widget and every ancestor as changed.

        Adds one to :attr:`generation` along the ``parent`` chain.  The
        walk is iterative and identity-guarded, so a malformed parent cycle
        (or a child shared by two containers) cannot loop or recurse away;
        a plain object that happens to sit in the chain is not touched.
        """
        node: object | None = self
        seen: set[int] = set()
        while node is not None and id(node) not in seen:
            seen.add(id(node))
            object.__setattr__(
                node, "_generation", getattr(node, "_generation", 0) + 1
            )
            parent = getattr(node, "parent", None)
            if parent is node or not hasattr(parent, "touch"):
                break
            node = parent

    def walk(self) -> Iterator[Widget]:
        """Every node under this one, depth first, this widget first.

        Preorder (a widget, then its children left to right), including
        ``self``, with ``id``-based de-duplication: a shared child is
        visited once, at its first position, and a ``parent``/``children``
        cycle terminates.  Children are read from the ``children`` attribute
        only -- the tree is explicit, never guessed from attribute names --
        and a child that is not a :class:`Widget` (a pure ``Component``
        leaf) is yielded as well, so callers see every mounted node.
        """
        seen: set[int] = set()
        stack: list[object] = [self]
        while stack:
            node = stack.pop()
            if id(node) in seen:
                continue
            seen.add(id(node))
            yield cast("Widget", node)
            children = getattr(node, "children", None)
            if children:
                stack.extend(reversed(list(children)))

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

    def render(self, c: Constraints) -> Surface:
        """Paint the widget's rows; every concrete widget implements this."""
        raise NotImplementedError

    # -- optional interaction verbs: no-ops by default ----------------------

    def handle(self, event: Event) -> bool:
        """Consume one event; a widget that takes no events declines."""
        return False

    def click(self, row: int, col: int) -> bool:
        """Take a click on one cell; a widget that has no click declines."""
        return False

    def drag(self, row: int, col: int, kind: str) -> bool:
        """Take one step of a drag on one cell; a widget without drags declines.

        ``kind`` is ``"press"``, ``"motion"`` or ``"release"``.  The App
        routes a press to the nearest widget overriding this verb, then
        keeps sending that widget the motion and release reports -- the
        cell is in the widget's own ``render`` coordinates, like
        :meth:`click`.
        """
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

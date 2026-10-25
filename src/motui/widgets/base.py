"""Widget: the base every interactive component shares.

A widget owns the four mutable inputs the runtime writes -- its theme, its
:class:`~motui.kernel.theme.Styles` overrides, and the ``focused`` / ``hover``
flags -- and answers the interaction verbs with their no-op defaults.  It
deliberately does **not** bake its theme in at construction: a widget keeps
the theme value and reads the role group it paints when it renders (through
:meth:`~motui.kernel.theme.Theme.group`), so assigning a new ``theme``
repaints a mounted widget without rebuilding it.

Subclasses implement :meth:`render` and override only the verbs they take.
A pure renderer need not inherit this class at all: :class:`Component` --
one ``render(c) -> Surface`` -- remains the rendering obligation.

2.0 adds the explicit tree the runtime derives facts from: ``parent`` /
``children``, :meth:`walk`, :meth:`touch` and the ``generation`` counter,
and states interaction as typed hooks plus capability flags.  A subclass
overrides only the hooks it takes; a pure renderer need not inherit this
class at all, because :class:`Component` -- one ``render(c) -> Surface`` --
remains the rendering obligation.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Protocol, cast, runtime_checkable

from ..kernel.cell import Surface
from ..kernel.document import Component
from ..kernel.events import KeyEvent, MouseEvent, PasteEvent, ResizeEvent
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.theme import DEFAULT_THEME, Styles, Theme
from .cursor import Cursor
from .mark import MarkSet

__all__ = ["Container", "Cursor", "HasResult", "MarkSet", "Widget"]


@runtime_checkable
class HasResult(Protocol):
    """A widget with a one-shot result: ``take() -> object | None``.

    Reading the result **clears** it, so a host reads a pick exactly once
    and never needs a second write to reset it.  ``None`` means "nothing
    pending"; a widget whose legal result is ``None`` uses the take itself
    as the signal (a cancel), and a ``False``/``0``/``""`` answer is a real
    result (test with ``is not None``).  :meth:`Widget.take` is the default
    implementation.
    """

    def take(self) -> object | None:
        ...


class Widget:
    """The shared state and no-op verbs of an interactive component.

    ``theme is None`` means "inherit the App theme"; ``styles`` overrides
    whole role groups and leaves every ``None`` field to the theme.  Both
    stay readable and writable so the runtime can retheme a mounted widget;
    assigning either is a public attribute write, so it touches the
    generation a block's row cache keys on.

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

    # -- capability flags: what the runtime may route to this widget --------
    #
    # Class defaults, all off: a pure renderer stays out of every tier until
    # it says otherwise.  The runtime reads these flags; it never probes a
    # capability protocol.

    focusable = False
    clickable = False
    hoverable = False
    activatable = False

    #: Key -> action names for the widget's own routing.  Empty on the base;
    #: a subclass declares its table and an instance may override entries.
    #: The merge rule is ``{**type(self).keymap, **instance.keymap}`` at the
    #: routing site, not in this attribute.
    keymap: Mapping[str, str] = {}

    #: Whether focus routing stays inside this widget's subtree (a ``Form``
    #: routes its fields itself).
    focus_scope = False

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
        return self._theme.group(name, self.styles)

    def render(self, c: Constraints) -> Surface:
        """Paint the widget's rows; every concrete widget implements this."""
        raise NotImplementedError

    # -- typed interaction hooks: no-ops by default -------------------------
    #
    # The runtime routes through these hooks only; there is no untyped verb
    # fallback.  A subclass overrides the hooks it takes and answers ``True``
    # when it consumed the input.

    def on_key(self, e: KeyEvent) -> bool:
        """Handle one key press; a widget that takes no keys declines."""
        return False

    def on_mouse(self, e: MouseEvent) -> bool:
        """Handle one mouse report; a widget that takes no mouse declines."""
        return False

    def on_paste(self, e: PasteEvent) -> bool:
        """Handle one paste payload; a widget that takes no paste declines."""
        return False

    def on_resize(self, e: ResizeEvent) -> None:
        """React to a terminal resize; the base widget has nothing to size."""
        return None

    def on_focus(self, gained: bool) -> None:
        """Take or lose the focus; the default flips :attr:`focused`."""
        self.focused = gained

    def on_click(self, pos: Pos) -> bool:
        """Take a click at ``pos``; a widget without a click declines."""
        return False

    def on_hover(self, pos: Pos | None) -> bool:
        """Take the pointer at ``pos``, or its departure for ``None``.

        A widget with a hovered row reads ``None`` as "no pointer".
        """
        return False

    def on_drag(self, pos: Pos, phase: str) -> bool:
        """Take one drag step at ``pos``; a widget without drags declines."""
        return False

    def on_action(self, name: str) -> bool:
        """Run the named action; the base binds none and declines.

        An unknown action answers ``False`` so the keymap router keeps
        routing the key.
        """
        return False

    def take(self) -> object | None:
        """Read the one-shot result; a widget without one answers ``None``."""
        return None


class Container(Widget):
    """A widget whose children occupy cells of its own rendered surface.

    The base adds the coordinate door a host uses to descend into a
    composed widget: :meth:`child_at` takes a 0-based cell of this widget's
    own ``render`` output and answers ``(component, row, col)`` in the
    child's coordinates -- or ``None`` for a cell this widget owns (border,
    padding, gap).  The default declines every cell; a real container
    overrides it with the geometry of its last render.  ``Container`` does
    not proxy events, focus or results: it only routes coordinates.
    """

    __slots__ = ()

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """The child owning one of this widget's cells; ``None`` by default."""
        return None


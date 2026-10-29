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

__all__ = [
    "CURSOR_KEYMAP",
    "ActionWidget",
    "Container",
    "Cursor",
    "CursorWidget",
    "HasResult",
    "Keymap",
    "MarkSet",
    "ResultWidget",
    "Widget",
]

#: The unified cursor key table: the arrows, the edges and the page keys.
#: A cursor family declares ``keymap = Keymap({**CURSOR_KEYMAP, ...})`` on
#: its own class, so every data view routes the same action names.
CURSOR_KEYMAP: dict[str, str] = {
    "up": "prev",
    "left": "prev",
    "down": "next",
    "right": "next",
    "home": "first",
    "end": "last",
    "page_up": "page_prev",
    "page_down": "page_next",
}

#: The "nothing pending" marker of :class:`ResultWidget`.  A sentinel -- not
#: ``None`` -- so a legal ``None`` result (a cancelled dialog) stays
#: distinguishable from an empty slot.
_MISSING: object = object()


class Keymap:
    """A class-level key table every instance shadows with its own copy.

    The class body spells the family default once::

        class List(Widget):
            keymap = Keymap({"up": "prev", "down": "next"})

    ``List.keymap`` answers that default table.  ``list_widget.keymap``
    answers the instance's own copy, installed by :meth:`Widget.__init__`
    from the class table, so a host's rebind -- ``list_widget.keymap["j"] =
    "next"`` -- only touches that one widget.  Assigning a whole mapping to
    an instance replaces its copy; the class table is never mutated by an
    instance operation.
    """

    __slots__ = ("table",)

    def __init__(self, table: Mapping[str, str]) -> None:
        self.table = dict(table)

    def __get__(
        self, instance: object | None, owner: type | None = None
    ) -> dict[str, str]:
        """The class default on the class, the instance copy on an instance."""
        if instance is None:
            return self.table
        return instance._keymap  # type: ignore[attr-defined]

    def __set__(self, instance: object, value: Mapping[str, str]) -> None:
        """Replace one instance's copy (the class table is untouched)."""
        instance._keymap = dict(value)  # type: ignore[attr-defined]


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
        "_keymap",
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
    #: :class:`Keymap` answers the class table on the class and the instance
    #: copy on an instance; :meth:`__init__` installs that copy.
    keymap = Keymap({})

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
        # The instance's own key table: rebinding one entry never reaches
        # the class default.  ``type(self).keymap`` reads the class table
        # through :meth:`Keymap.__get__` (the class path), so this copies
        # and never installs a copy recursively.  A subclass that spells
        # ``keymap`` as something else -- the text fields expose a property
        # over their buffer -- keeps its own seam and gets an empty copy.
        table = type(self).keymap
        object.__setattr__(
            self, "_keymap", dict(table) if isinstance(table, Mapping) else {}
        )

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


class ResultWidget(Widget):
    """A widget with a one-shot result, read once through :meth:`take`.

    ``_result`` starts at the module sentinel :data:`_MISSING`, so "nothing
    pending" and a legal ``None`` payload -- a cancelled dialog, an empty
    pick -- stay distinguishable: :meth:`take` clears the slot either way,
    and the caller uses *having called take* as the cancel signal.  Verbs
    write with :meth:`_emit`; state-changing verbs clear with
    :meth:`_clear_result` so a stale pick never survives a cursor move.
    """

    __slots__ = ("_result",)

    def __init__(
        self, theme: Theme | None = None, styles: Styles | None = None
    ) -> None:
        super().__init__(theme, styles)
        object.__setattr__(self, "_result", _MISSING)

    def _emit(self, value: object) -> None:
        """Leave ``value`` pending (``None`` included) and touch the widget."""
        object.__setattr__(self, "_result", value)
        self.touch()

    def _clear_result(self) -> bool:
        """Drop a pending result; ``True`` when there was one to drop."""
        if self._result is _MISSING:
            return False
        object.__setattr__(self, "_result", _MISSING)
        self.touch()
        return True

    def take(self) -> object | None:
        """Read the pending result once; a spent slot answers ``None``.

        The legal ``None`` payload and the spent slot answer the same value
        here (the protocol is ``object | None``); only the caller knows
        whether it called :meth:`take` at all, which is the cancel signal.
        """
        if self._result is _MISSING:
            return None
        value = self._result
        object.__setattr__(self, "_result", _MISSING)
        return cast("object | None", value)


class ActionWidget(ResultWidget):
    """A result widget with a ``disabled`` gate, a tooltip ``hint`` and verbs.

    The shared half of :class:`~motui.widgets.action.Button`,
    :class:`~motui.widgets.action.Checkbox` and
    :class:`~motui.widgets.action.Link`: ``disabled`` refuses every door
    (each concrete verb checks it), ``hint`` is the tooltip protocol (the
    empty default means no hint), and :meth:`on_click` is the pointer door
    to :meth:`activate`.

    :meth:`on_action` routes exactly two names: ``"activate"`` delegates
    :meth:`activate` and ``"toggle"`` delegates :meth:`toggle`; every other
    name -- and a verb the subclass has not implemented, whose base answer
    is ``False`` -- declines, so the keymap router keeps routing the key.
    """

    __slots__ = ("disabled", "hint")

    #: Every action widget takes the activation verb; a concrete control
    #: implements :meth:`activate` (or :meth:`toggle`).
    activatable = True

    def __init__(
        self,
        *,
        disabled: bool = False,
        hint: str = "",
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        # Initial state installed without a touch: construction is not a
        # change (see :meth:`Widget.__init__`).
        object.__setattr__(self, "disabled", disabled)
        object.__setattr__(self, "hint", hint)

    def activate(self) -> bool:
        """Run the main operation; the base has none and declines."""
        return False

    def toggle(self) -> bool:
        """Flip a boolean or marked state; the base has none and declines."""
        return False

    def on_click(self, pos: Pos) -> bool:
        """The pointer door to the main operation; ``pos`` is ignored."""
        return self.activate()

    def on_action(self, name: str) -> bool:
        """Run ``activate``/``toggle``; unknown names decline."""
        if name == "activate":
            return self.activate()
        if name == "toggle":
            return self.toggle()
        return False


class CursorWidget(ResultWidget):
    """A result widget that walks one cursor over its entries.

    The shared half of every data view and menu: a :class:`Cursor` value
    (``_cursor``) over the entries a subclass reports, the read-only
    :attr:`index` / :attr:`selected` pair, and the ``select`` / ``move`` /
    ``home`` / ``end`` verbs.  Subclasses supply the entry hooks -- count,
    item at a visible row, disabled rows, wrap policy and page size -- and
    implement :meth:`activate` / :meth:`toggle` when they have one; the
    cursor arithmetic itself never repeats.

    **Clearing.**  Moving the cursor is a state change, not a pick: every
    cursor verb clears a pending result first (:meth:`_clear_result`), so a
    value emitted before the move can never be read as the result of the
    row the host moved to.  Only :meth:`activate` / :meth:`toggle` write a
    result.

    **Staleness.**  The hooks are re-read at the start of every verb and on
    each read of :attr:`index` / :attr:`selected` (:meth:`_sync_cursor`):
    the count, the disabled set and the wrap policy are refreshed, and an
    index the reported entries no longer answer is clamped.  An empty entry
    set always reports ``index == 0`` and ``selected is None``.
    """

    __slots__ = ("_cursor",)

    #: The cursor family's default table; a subclass merges its own keys in.
    keymap = Keymap(CURSOR_KEYMAP)

    def __init__(
        self, theme: Theme | None = None, styles: Styles | None = None
    ) -> None:
        super().__init__(theme, styles)
        object.__setattr__(self, "_cursor", Cursor(0))

    # -- entry hooks: subclasses implement these ---------------------------

    def _entry_count(self) -> int:
        """The number of entries the cursor walks; the base has none."""
        return 0

    def _entry_at(self, index: int) -> object | None:
        """The item at visible row ``index``; the base has none."""
        return None

    def _cursor_disabled(self) -> Iterable[int]:
        """The visible rows a move steps over and ``select`` refuses."""
        return ()

    def _cursor_wraps(self) -> bool:
        """Whether the cursor wraps at the ends; data views clamp."""
        return False

    def _page_size(self, size: int) -> int:
        """The step ``page_prev`` / ``page_next`` take over ``size`` entries.

        ``size`` is the entry count; a view with a smaller visible window
        overrides this to cap the page to its rows.
        """
        return size

    # -- state ------------------------------------------------------------

    @property
    def index(self) -> int:
        """The cursor position, clamped into the current entries (0 if empty)."""
        self._sync_cursor()
        return self._cursor.index

    @property
    def selected(self) -> object | None:
        """The item under the cursor, or ``None`` for an empty set."""
        self._sync_cursor()
        if self._cursor.count <= 0:
            return None
        return self._entry_at(self._cursor.index)

    def _sync_cursor(self) -> None:
        """Refresh the cursor's count, disabled set and wrap policy, clamp."""
        cursor = self._cursor
        cursor.count = max(0, self._entry_count())
        cursor.disabled = frozenset(self._cursor_disabled())
        cursor.wrap = self._cursor_wraps()
        cursor.index = cursor.clamp(cursor.index)

    # -- verbs ------------------------------------------------------------

    def select(self, index: int) -> bool:
        """Place the cursor on ``index`` (clamped); ``False`` when unchanged.

        A disabled row refuses the selection outright, and an empty entry
        set always declines.
        """
        self._clear_result()
        self._sync_cursor()
        changed = self._cursor.select(index)
        if changed:
            self.touch()
        return changed

    def move(self, delta: int) -> bool:
        """Move the cursor ``delta`` enabled rows; ``False`` when unchanged."""
        self._clear_result()
        self._sync_cursor()
        changed = self._cursor.move(delta)
        if changed:
            self.touch()
        return changed

    def home(self) -> bool:
        """Jump to the first enabled row; ``False`` when unchanged."""
        self._clear_result()
        self._sync_cursor()
        changed = self._cursor.home()
        if changed:
            self.touch()
        return changed

    def end(self) -> bool:
        """Jump to the last enabled row; ``False`` when unchanged."""
        self._clear_result()
        self._sync_cursor()
        changed = self._cursor.end()
        if changed:
            self.touch()
        return changed

    def activate(self) -> bool:
        """Run the main operation; the base has none and declines."""
        return False

    def toggle(self) -> bool:
        """Flip a boolean or marked state; the base has none and declines."""
        return False

    def on_action(self, name: str) -> bool:
        """Route the nine action names; unknown names decline.

        ``prev``/``next`` move one row, ``first``/``last`` jump to the
        enabled edges, ``page_prev``/``page_next`` step by
        :meth:`_page_size`, and ``activate``/``toggle`` delegate to their
        verbs.  ``open``/``close`` have no state on the base and decline, as
        does every other name, so the router keeps routing the key.
        """
        if name == "prev":
            return self.move(-1)
        if name == "next":
            return self.move(1)
        if name == "first":
            return self.home()
        if name == "last":
            return self.end()
        if name == "page_prev":
            return self.move(-self._page_size(self._entry_count()))
        if name == "page_next":
            return self.move(self._page_size(self._entry_count()))
        if name == "activate":
            return self.activate()
        if name == "toggle":
            return self.toggle()
        return False


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


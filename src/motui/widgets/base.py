"""Widget: the base every interactive component shares.

A widget owns its theme, ``Styles`` overrides, ``focused``/``hover`` flags,
the ``parent``/``children`` tree, a ``generation`` counter and no-op typed
interaction hooks.  Themes resolve at render time; a pure renderer need only
implement :class:`Component`.
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

    ``Class.keymap`` is the default table; ``instance.keymap`` is that
    instance's copy, so a rebind never writes through to the class.
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
    """A widget with a one-shot ``take() -> object | None`` result.

    Taking clears the slot, so the caller reads once; ``None`` means nothing
    pending, and a legal ``None`` payload is signalled by having called take.
    """

    def take(self) -> object | None:
        ...


class Widget:
    """The shared state and no-op verbs of an interactive component.

    ``theme``/``styles`` resolve at render time, so assignment repaints a
    mounted widget.  ``parent``/``children`` form the explicit tree;
    :meth:`walk` reads it defensively.  Assigning a public attribute bumps
    ``generation`` on this widget and every ancestor; in-place mutations
    require an explicit :meth:`touch`.
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

        ``parent`` never touches; ``children`` adopts children and touches;
        underscore names assign silently; everything else touches.
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
        """How many changes this widget's subtree has seen (monotone, never reset)."""
        return getattr(self, "_generation", 0)

    def touch(self) -> None:
        """Bump ``generation`` on this widget and every ancestor.

        The walk is iterative and identity-guarded, so parent cycles and
        shared children cannot loop.
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

        Identity-deduplicated: a shared child is visited once and a cycle
        terminates.  Non-widget children are yielded too.
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

    ``_result`` starts at :data:`_MISSING`, so "nothing pending" and a legal
    ``None`` stay distinguishable.  Verbs write with :meth:`_emit`;
    state-changing verbs clear with :meth:`_clear_result`.
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
        """Read the pending result once and clear the slot; spent answers ``None``.

        A legal ``None`` and a spent slot are indistinguishable here; the
        caller's having called take is the cancel signal.
        """
        if self._result is _MISSING:
            return None
        value = self._result
        object.__setattr__(self, "_result", _MISSING)
        return cast("object | None", value)


class ActionWidget(ResultWidget):
    """A result widget with a ``disabled`` gate, a ``hint`` and the action verbs.

    ``disabled`` refuses every door; ``hint`` is the tooltip.  ``on_click``
    delegates to :meth:`activate`; ``on_action`` routes only ``activate``
    and ``toggle``.
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

    Subclasses supply entry hooks (count, item at a visible row, disabled
    rows, wrap policy, page size) and implement ``activate``/``toggle``;
    ``index`` is assignable through :meth:`select`, ``selected`` is
    read-only.  Every cursor verb clears a pending result first -- moves are
    state changes, not picks.  ``_sync_cursor`` re-reads the hooks and
    clamps a stale index; an empty set reports ``index == 0``.
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
        return 0

    def _entry_at(self, index: int) -> object | None:
        return None

    def _cursor_enabled(self) -> bool:
        """Whether the whole control accepts cursor gestures."""
        return True

    def _cursor_disabled(self) -> Iterable[int]:
        return ()

    def _cursor_wraps(self) -> bool:
        """Whether the cursor wraps at the ends; data views clamp."""
        return False

    def _page_size(self, size: int) -> int:
        """The page step over ``size`` entries; a windowed view caps it."""
        return size

    # -- state ------------------------------------------------------------

    @property
    def index(self) -> int:
        """The cursor position, clamped into the current entries (0 if empty)."""
        self._sync_cursor()
        return self._cursor.index

    @index.setter
    def index(self, value: int) -> None:
        """Place the cursor through :meth:`select` (host-assignment door)."""
        self.select(int(value))

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

        Disabled rows and an empty set refuse.
        """
        self._clear_result()
        if not self._cursor_enabled():
            return False
        self._sync_cursor()
        changed = self._cursor.select(index)
        if changed:
            self.touch()
        return changed

    def move(self, delta: int) -> bool:
        """Move the cursor ``delta`` enabled rows; ``False`` when unchanged."""
        self._clear_result()
        if not self._cursor_enabled():
            return False
        self._sync_cursor()
        changed = self._cursor.move(delta)
        if changed:
            self.touch()
        return changed

    def home(self) -> bool:
        """Jump to the first enabled row; ``False`` when unchanged."""
        self._clear_result()
        if not self._cursor_enabled():
            return False
        self._sync_cursor()
        changed = self._cursor.home()
        if changed:
            self.touch()
        return changed

    def end(self) -> bool:
        """Jump to the last enabled row; ``False`` when unchanged."""
        self._clear_result()
        if not self._cursor_enabled():
            return False
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

    def on_key(self, event: KeyEvent) -> bool:
        """Route one key through :attr:`keymap`; an unbound key declines."""
        if not isinstance(event, KeyEvent):
            return False
        action = self.keymap.get(event.key)
        if action is None:
            return False
        return self.on_action(action)

    def on_action(self, name: str) -> bool:
        """Route the nine action names; unknown names decline.

        ``prev``/``next`` move, ``first``/``last`` jump, ``page_*`` step by
        :meth:`_page_size`, ``activate``/``toggle`` delegate; ``open`` and
        ``close`` decline on the base.
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

    :meth:`child_at` maps a cell of this widget's render output to
    ``(component, row, col)`` in the child, or ``None`` for an owned cell.
    The base declines every cell; containers override it from their last
    render.  It routes coordinates only -- never events, focus or results.
    """

    __slots__ = ()

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """The child owning one of this widget's cells; ``None`` by default."""
        return None


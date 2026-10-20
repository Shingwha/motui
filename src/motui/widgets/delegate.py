"""Delegate: the single-child wrapper that answers every surface itself.

One component, wrapped and handed on unchanged: :class:`Delegate` is the
urwid ``AttrMap`` door (``ref/industry.md`` §5) -- a host that puts a motui
component behind one more layer forwards nothing by hand, because the
wrapper answers the protocol surfaces itself.  The transforming siblings
stay what they are: :class:`~motui.widgets.layout.Padding` (insets plus
fill) and :class:`~motui.widgets.decor.Panel` (the frame) reshape the
child's rows, while this one is the identity.  Only the kernel is
imported: the wrapper computes no layout and reads no theme.
"""

from __future__ import annotations

from ..kernel.block import Clickable, Component, Container, Revisioned
from ..kernel.lines import Line

__all__ = ["Delegate"]


class Delegate:
    """One child component, every protocol surface answered here.

    The wrapper is the identity: :meth:`render` hands back the child's rows
    verbatim -- no fit, no fill, no theme, no style, no memo -- and
    :attr:`child` is a plain attribute, so a host reads and swaps the
    wrapped component directly.  :class:`~motui.widgets.layout.Padding`
    (insets plus fill) and :class:`~motui.widgets.decor.Panel` (the frame)
    are the transforming siblings and stay as they are.

    **The proxy door.**  Four surfaces are forwarded -- ``render``,
    ``revision``, ``click`` and ``hover_at`` -- the urwid ``AttrMap``
    pattern (``ref/industry.md`` §5), where the wrapper passes the call on
    to the widget it holds.  A host dispatching a click or a hover on the
    wrapper needs no ``isinstance`` ladder of its own.

    **The container door.**  :meth:`child_at` maps *every* cell to the
    child at the same coordinates, so
    :func:`~motui.kernel.block.descend` walks straight through to the leaf
    and the pointer tier, the focus ring's click policy and the hit test
    all reach the component that owns the cell.  Unlike
    :class:`~motui.widgets.decor.Panel` and
    :class:`~motui.widgets.layout.Padding`, whose ``child_at`` answers over
    the geometry of their last render, the identity has no geometry to
    store: a wrapper that has not rendered yet answers the child as surely
    as one that has.

    **Three degradation rules**, each answering the protocol's own
    negative rather than raising:

    * a child without ``revision`` answers ``None``.  ``None`` is the
      documented "memory off" answer, not a snapshot: a
      :class:`~motui.kernel.block.Block` decides once, at construction,
      whether its component is cacheable with ``isinstance(component,
      Revisioned)`` -- a runtime-checkable protocol, so the test is
      **method presence**, and the wrapper, which always has the method,
      always passes it.  Answering a made-up snapshot instead would key
      the block's row cache on a lie -- the cache would hand back rows the
      child had already changed.  ``None`` routes the block through its
      no-snapshot rule instead: an open block re-renders every layout, a
      sealed one caches by width alone, exactly the behaviour a component
      without the protocol has always had.
    * a child without ``click`` answers ``False``: the click landed on
      nothing the wrapper can consume, which is
      :class:`~motui.kernel.block.Clickable`'s own negative answer.
    * a child without ``hover_at`` answers ``False``: nothing repainted,
      the pointer tier's negative answer.  ``hover_at`` is an optional
      method with no protocol of its own, so the wrapper looks for it the
      way the pointer tier does.

    **What it never proxies.**  ``handle`` / ``move`` / ``activate`` /
    ``focused`` belong to the component, not to a coordinate router: a
    container routes cells and nothing else (the DESIGN.md rule), and a
    host that needs those reaches ``delegate.child`` itself.  The wrapper
    therefore holds no state beyond :attr:`child` -- no ``hover`` flag, no
    focus flag, no theme -- so a host can never mistake the wrapper's own
    markings for the child's.
    """

    __slots__ = ("child",)

    def __init__(self, child: Component) -> None:
        self.child = child

    def render(self, width: int) -> list[Line]:
        """The child's rows, verbatim: the wrapper paints nothing of its own.

        The child's own answer is handed back unchanged, list and all --
        the identity allocates nothing, the same forward
        :meth:`~motui.kernel.block.Block.render` makes.  A caller that
        keeps the list keeps whatever the child handed out.
        """
        return self.child.render(width)

    def revision(self) -> object:
        """The child's snapshot, or ``None`` when it has none.

        Forwarded when the child implements
        :class:`~motui.kernel.block.Revisioned`; ``None`` otherwise, the
        off switch that keeps a :class:`~motui.kernel.block.Block`'s row
        cache off rather than keyed on a snapshot the child never
        promised.  With a snapshot the wrapper is as cacheable as its
        child: a sealed block's hovered child repaints through it.
        """
        if isinstance(self.child, Revisioned):
            return self.child.revision()
        return None

    def click(self, row: int, col: int) -> bool:
        """The child's answer, or ``False`` when it has no ``click``.

        The row and column are the wrapper's own -- which, the wrapper
        being the identity, are the child's -- so the child absorbs its
        own layout arithmetic exactly as it would unwrapped.
        """
        if isinstance(self.child, Clickable):
            return self.child.click(row, col)
        return False

    def hover_at(self, row: int, col: int) -> bool:
        """The child's answer, or ``False`` when it has no ``hover_at``.

        ``hover_at`` is an optional method (no protocol of its own), so it
        is looked up the way the pointer tier looks it up; a child without
        one repaints nothing, and ``False`` says so.
        """
        hover_at = getattr(self.child, "hover_at", None)
        if hover_at is None:
            return False
        return hover_at(row, col)

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """The child owns every cell, at the same coordinates.

        The container door: the wrapper insets nothing, so the cell it was
        handed is the child's cell.  A negative coordinate owns nothing (the
        ``Row``/``Column`` rule): no component has a cell before the
        origin.  No geometry is consulted, hence no "not rendered yet"
        answer -- ``descend`` reaches the leaf through any number of nested
        wrappers.
        """
        if row < 0 or col < 0:
            return None
        return self.child, row, col

    def __repr__(self) -> str:
        return f"Delegate({self.child!r})"

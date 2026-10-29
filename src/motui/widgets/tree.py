"""Tree: an indented, collapsible list of :class:`TreeNode` values.

``Tree`` walks its root nodes depth-first, descending into open nodes
only, and renders one row per visible node: ``indent`` spaces per depth, a
fold indicator (the vocabulary's ``\u25be``/``\u25b8`` by default) for a node
with children -- a blank indicator column for a leaf, so every label starts
at the same offset -- and the label itself.  Guides are deliberately
minimal: plain space indentation, **no ``\u2502`` connectors**.

The two indicator glyphs come from the keyword-only ``glyphs``
vocabulary -- ``fold_open`` and ``fold_closed``.  They are content, not
style, and their column is the state pair's wider seat
(:func:`~motui.kernel.glyphs.pair_seat`): a leaf, and a node whose glyph is
``""``, keeps a blank column of that same width, so labels stay aligned; a
wide (CJK) glyph widens the column for every row, and two empty glyphs
collapse it to zero columns.

**The row-band contract.**  Every row resolves its band from the theme's row
roles through :meth:`~motui.kernel.theme.RowStyles.band`: ``rows.base`` is
the resting surface, ``rows.active`` the band under the focused cursor row
and ``rows.inactive`` the unfocused one, ``rows.hover`` the pointer token,
and ``rows.disabled`` the band under a disabled row.  A row is its
text-styled segments -- the guide and the label in their own styles, the cursor row's
run in no style of its own -- then ``.clip(WrapMode.ELLIPSIS, width).fill(fitted.width, band)``:
the W1 primitive, the band underneath, the text styles on top.  The band
merges under the row's own cells -- a pill behind the text, never a
ribbon across the pane; a full-surface band is the host's container's job
(``Padding(fill_style=...)`` / ``Panel(frame=False, style=...)``, which
fill every row to the width they are handed).  The cursor row and every
resting row (guides included) go through the same pipeline; only the
engaged row swaps the band, and an unfocused cursor row wears
``rows.inactive``.  The fill is skipped while the band is ``NONE``
-- the default theme's ground and both its engaged bands -- so resting
rows render exactly the bytes they always did, and so do the cursor row
and the hovered row until a host themes them.

``move`` clamps the cursor inside the visible enabled
rows without wrapping, and ``activate`` expands/collapses the node under
it (a no-op on a leaf or a disabled node), re-clamping the cursor when
rows disappear.  Styles resolve at render time from the theme (or a
``styles=`` group override).

Two host gestures narrow and steer the rows without the tree ever changing
its own data: ``filter(query)`` prunes the tree to the labels holding the
query (case-insensitive substring), keeps the ancestors of every hit and
renders those chains open -- the user's ``open`` flags are never
rewritten, so clearing the filter restores the tree the user built -- and
``jump(char)`` is type-ahead: the cursor hops to the next *visible* node
whose label starts with that character, case-insensitively, wrapping around
the rows.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..kernel.cell import Line, Segment, Surface, rest
from ..kernel.geom import Pos
from ..kernel.glyphs import GLYPHS, Glyphs, pair_seat, seat_width
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.theme import Styles, Theme
from ..widgets.base import CURSOR_KEYMAP, CursorWidget
from .strip import Keymap

__all__ = ["Tree", "TreeNode"]


class TreeNode:
    """One tree node: a label, child nodes, an ``open`` flag and ``disabled``.

    A plain mutable class on purpose: :meth:`Tree.activate` flips ``open``
    in place instead of rebuilding the path back to the root, which is what
    a frozen dataclass would force.  ``children`` is copied into a list; a
    node without children is a leaf and never opens.  A disabled node
    renders ``text.faint`` and every cursor gesture skips or refuses it;
    its ``open`` flag is still the user's own state.
    """

    __slots__ = ("children", "disabled", "label", "open")

    def __init__(
        self,
        label: str,
        children=(),
        *,
        open: bool = False,
        disabled: bool = False,
    ) -> None:
        self.label = label
        self.children = list(children)
        self.open = open
        self.disabled = disabled

    def __repr__(self) -> str:
        return (
            f"TreeNode({self.label!r}, children={self.children!r}, "
            f"open={self.open}, disabled {self.disabled})"
        )


class Tree(CursorWidget):
    """An indented node list with a cursor and per-node expand/collapse.

    ``nodes`` is any iterable of :class:`TreeNode`; ``indent`` is the
    per-depth space count.  ``selected`` is the visible node under the
    cursor (``None`` for an empty tree).  The guide column and indicators
    paint ``text.faint``, unselected labels ``text.base``, and the whole
    cursor row carries the ``rows.active`` band underneath (the row's own
    run carries no style of its own, the band rests underneath it).  A
    disabled node's row paints ``text.faint``.  Styles resolve at render
    time from the theme or a ``styles=`` group override; assigning
    ``theme``/``styles`` touches the widget.

    ``fold_open`` and ``fold_closed`` (default the vocabulary's ``\u25be`` and
    ``\u25b8``) are the fold glyphs: each row's indicator column is the
    pair's wider seat and a leaf keeps that column blank, so labels align
    whatever the glyphs measure; ``""`` disables a glyph (its state leaves
    the column blank) and two empty glyphs collapse the column.

    ``focused`` is the focus flag the focus tier sets
    : while it is ``True`` the
    cursor row's band is ``rows.active``; while it is ``False`` that band
    is ``rows.inactive`` -- the cursor stays legible but loses weight, and
    every other row renders unchanged.

    ``hover`` is the pointer tier's flag
    ; :meth:`on_hover` marks the
    visible node row under the pointer and that row wears
    ``rows.hover`` -- the pointer's own token, whatever row it is on
    (D3).
    The marking starts ``None``, so an un-hovered tree renders
    byte-for-byte what it always did.

    :meth:`filter` prunes the visible rows to the labels holding a query
    (case-insensitive substring) and keeps the chain to every hit, rendered
    open -- the row's own ``\u25be``/``\u25b8`` indicator included; :meth:`jump`
    is the printable-key type-ahead.  Both read the ``open`` flags,
    neither writes them: the auto-expansion a filter shows is derived from
    the match structure on every walk, so clearing the filter brings the
    user's own rows back untouched.
    """

    __slots__ = (
        "_filter",
        "_hover_index",
        "disabled",
        "glyphs",
        "indent",
        "nodes",
    )

    #: The tree owns the keyboard, clicks, the pointer's row and activation.
    focusable = True
    clickable = True
    hoverable = True
    activatable = True

    #: The cursor family's arrows plus the fold keys: left closes, right opens.
    keymap = Keymap(
        {
            **{k: v for k, v in CURSOR_KEYMAP.items() if k not in ("left", "right")},
            "left": "close",
            "right": "open",
        }
    )

    def __init__(
        self,
        nodes: Iterable[TreeNode] = (),
        *,
        indent: int = 2,
        glyphs: Glyphs = GLYPHS,
        disabled: bool = False,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.nodes = list(nodes)
        self.indent = indent
        self.glyphs = glyphs
        # The old constructor default; FocusManager/App may flip it later.
        self.focused = True
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_hover_index`` (:meth:`on_hover`).
        self.hover = False
        #: The whole tree refuses every cursor gesture when disabled.
        self.disabled = disabled
        # The active filter query (case-insensitive substring) or ``None``;
        # written by ``filter``, read by ``_visible``.  ``None`` -- the
        # default -- renders exactly the walk the tree always did.
        self._filter: str | None = None
        # The visible node row the pointer is on, or ``None``; written by
        # ``on_hover``, read by ``render``.  ``None`` renders byte-for-byte
        # what the tree always did.
        self._hover_index: int | None = None

    def _band(self, current: bool, hovered: bool, disabled: bool = False) -> Style:
        """The surface one node row rests on: :meth:`RowStyles.band`, by precedence.

        The cursor row wears ``rows.active`` while focused and
        ``rows.inactive`` while not; the pointer's row ``rows.hover`` and a
        resting row ``rows.base``.  The ``rows`` group comes from
        ``styles`` when overridden, else the theme.
        """
        return self.group("rows").band(
            active=current, hovered=hovered, focused=self.focused, disabled=disabled
        )

    # -- the cursor hooks -------------------------------------------------------

    def _entry_count(self) -> int:
        """The visible node rows the cursor walks."""
        return len(self._visible())

    def _entry_at(self, index: int) -> object | None:
        """The visible node at row ``index`` (side-effect free)."""
        return self._visible()[index][0]

    def _cursor_disabled(self) -> Iterable[int]:
        """The visible rows a move steps over and ``select`` refuses."""
        return {i for i, (node, _, _) in enumerate(self._visible()) if node.disabled}

    def _cursor_wraps(self) -> bool:
        """The tree clamps at its visible ends; it never wraps."""
        return False

    def _cursor_enabled(self) -> bool:
        """The whole-tree disabled switch gates every cursor verb."""
        return not self.disabled

    # -- the verbs ---------------------------------------------------------------

    def activate(self) -> bool:
        """Toggle the visible node under the cursor; ``True`` when it folded.

        A leaf has nothing to open, and a disabled node or tree answers
        ``False``.  A real flip writes the node through the shared result
        slot (read once by ``take``).
        """
        if self.disabled:
            return False
        node = self.selected
        if node is None or node.disabled or not node.children:
            return False
        if not self._fold(not node.open):
            return False
        self._emit(node)
        return True

    def toggle(self) -> bool:
        """Flip the cursor node's open state without emitting a result."""
        if self.disabled:
            return False
        node = self.selected
        if node is None or node.disabled or not node.children:
            return False
        return self._fold(not node.open)

    def on_action(self, name: str) -> bool:
        """Run one named tree action; ``False`` for an unknown name.

        ``open`` / ``close`` fold the node under the cursor without
        toggling; every other name is the shared cursor's (``prev`` /
        ``next`` / ``first`` / ``last`` / ``page_*`` / ``activate`` /
        ``toggle``).  An unknown name answers ``False`` without touching
        the tree.
        """
        if name == "open":
            return self._fold(True)
        if name == "close":
            return self._fold(False)
        return super().on_action(name)

    def on_click(self, pos: Pos) -> bool:
        """Place the cursor on the visible node at ``pos.y``; True on a hit.

        ``pos.y`` is a 0-based row of this component's own ``render`` -- the
        visible nodes, in draw order.  A row that is an enabled node answers
        ``True`` and moves the cursor there (even when it already was); a
        disabled node, a disabled tree, and any row past the last node
        answer ``False`` and leave the cursor alone.  ``pos.x`` is ignored:
        a node row belongs to its node from the first indent column to the
        last label column -- no column narrows the hit.
        """
        if self.disabled:
            return False
        visible = self._visible()
        if not 0 <= pos.y < len(visible):
            return False
        if visible[pos.y][0].disabled:
            return False
        self.select(pos.y)
        return True

    def _fold(self, opened: bool) -> bool:
        """Set the node under the cursor to ``opened``; ``True`` on a change.

        The half :meth:`on_action`'s ``open`` / ``close`` names share: a
        leaf, a disabled node or a disabled tree answers ``False``, an
        already-folded node answers ``False`` (nothing changed), and a real
        flip re-clamps the cursor into the rows that remain.
        """
        if self.disabled:
            return False
        node = self.selected
        if node is None or node.disabled or not node.children:
            return False
        if node.open == opened:
            return False
        node.open = opened
        self._sync_cursor()
        self.touch()
        return True

    def filter(self, query: str | None) -> bool:
        """Prune the visible rows to the labels holding ``query``; True when they moved.

        A node stays visible when its own label holds ``query`` as a
        **case-insensitive substring** *or* a node below it does -- the
        ancestors of every hit are kept, so the chain to each match is on
        screen and renders **open** (the walk descends any kept node with
        kept children, whatever that node's own ``open`` flag says).
        An empty string matches every label (the substring rule), so
        ``filter("")`` shows the whole tree with every chain open; ``None``
        clears the filter.

        The auto-expansion is **derived, never written back**: the user's
        expansion set is exactly the nodes' ``open`` flags and the
        filter's own is recomputed from the match structure on every walk,
        so the two cannot drift -- ``filter(None)`` restores the user's rows
        because nothing was ever rewritten, and the filter never interferes
        with :meth:`on_action`, whose fold simply waits for the filter to
        clear.  The cursor returns to the top row whenever the query
        changes (a new query is a new list -- the ``Autocomplete`` rule),
        and the answer says whether the *rows* changed: ``True`` for a
        query that prunes or restores, ``False`` for a no-op call (the same
        query twice, clearing an unfiltered tree).
        """
        query = None if query is None else str(query)
        if query == self._filter:
            return False  # the same list: the cursor stays where the host left it
        before = self._visible()
        self._filter = query
        # The P0: the row numbering the pointer named no longer exists (the
        # Autocomplete rule); a stale mark could otherwise band the wrong row.
        self._hover_index = None
        self._cursor.index = 0
        self.touch()
        return self._visible() != before

    def jump(self, char: str) -> bool:
        """Type-ahead: cursor to the next visible node starting with ``char``.

        ``char`` is one printable character (anything else declines without
        moving); the scan walks the **visible** rows -- the filtered ones
        included -- starting at the row *after* the cursor and wrapping
        around, so repeated presses cycle the matches and a press on a node
        already under the cursor moves on to the next hit rather than
        staying put.  The match is case-insensitive on the label's first
        character.  ``True`` when the cursor landed on a different row;
        ``False`` -- and nothing moved -- for a non-printable or multi-
        character argument, an empty tree, or a character no visible label
        starts with.

        The demo shell routes no printable to a widget, so a host that
        wants live type-ahead routes its character keys here itself::

            if isinstance(event, KeyEvent) and event.char:
                tree.jump(event.char)
        """
        if len(char) != 1 or not char.isprintable():
            return False
        visible = self._visible()
        count = len(visible)
        if count == 0:
            return False
        needle = char.lower()
        current = self.index
        for step in range(1, count + 1):
            row = (current + step) % count
            node = visible[row][0]
            if not node.disabled and node.label.lower().startswith(needle):
                moved = row != current
                if moved:
                    self.select(row)
                return moved
        return False  # no enabled visible label starts with the character

    def on_hover(self, pos: Pos | None) -> bool:
        """Mark the visible node row under the pointer; True on a change.

        The pointer tier's row-level half (D3): ``pos.y`` is a 0-based row of
        the visible nodes in draw order -- exactly what :meth:`on_click`
        consumes, minus the cursor move -- and ``pos.x`` is ignored (a node
        row owns the whole width).  A row past the last node answers "no
        node" and clears the marking; ``None`` clears it too (the pointer
        left).  The answer is whether the marked row changed, and
        :meth:`render` rests that row on the theme's ``hover`` band -- the
        pointer's own token, whatever row it is on.
        """
        if pos is None:
            target = None
        else:
            visible = self._visible()
            target = pos.y if 0 <= pos.y < len(visible) else None
        changed = target != self._hover_index
        if changed:
            self._hover_index = target
            self.touch()
        return changed

    def render(self, c: Constraints) -> Surface:
        """One row per visible node, each through the row-band contract.

        The constraint carries the width; a ``max_height`` budget
        truncates the leading visible rows (the tree never grows past the
        height it was offered).  The rows are :meth:`Surface.clipped`, not
        padded, so short rows keep the bytes they always had.
        """
        self._sync_cursor()
        visible = self._visible()
        cursor = self._cursor.index
        out: list[Line] = []
        for i, (node, depth, opened) in enumerate(visible):
            node_disabled = self.disabled or node.disabled
            out.append(
                rest(
                    self._node_row(node, depth, opened, i == cursor, node_disabled),
                    c.width,
                    self._band(i == cursor, i == self._hover_index, node_disabled),
                )
            )
        if c.max_height is not None:
            out = out[: c.max_height]
        return Surface.clipped(out, c.width)

    def _visible(self) -> list[tuple[TreeNode, int, bool]]:
        """The visible nodes as ``(node, depth, open)`` triples, in draw order.

        ``open`` is what the row's own indicator shows: the node's
        ``open`` flag on the unfiltered walk, and "this node holds a
        kept child" on the filtered one (:meth:`_visit_filtered`) -- so a
        drawn ``\\u25be`` never disagrees with the rows actually below it,
        and the filter's derived auto-expansion is visible in the indicator
        without the flag ever being written.
        """
        out: list[tuple[TreeNode, int, bool]] = []
        if self._filter is None:
            self._visit(self.nodes, 0, out)
        else:
            self._visit_filtered(self.nodes, 0, out, self._filter.lower())
        return out

    def _visit(
        self, nodes, depth: int, out: list[tuple[TreeNode, int, bool]]
    ) -> None:
        for node in nodes:
            out.append((node, depth, node.open))
            if node.open:
                self._visit(node.children, depth + 1, out)

    def _visit_filtered(
        self,
        nodes,
        depth: int,
        out: list[tuple[TreeNode, int, bool]],
        needle: str,
    ) -> None:
        """The filtered walk: keep a node when it matches or holds a match below.

        Every node is visited -- a match below a match is a match too -- and
        a node is emitted when its own label holds ``needle`` or the walk
        below it emitted anything, with that subtree following it: the
        ancestors of every hit are kept and the chains render open (the
        emitted ``open`` flag is "there is a kept child", the row the
        indicator draws).  The ``open`` flags are not read here, which
        is exactly what makes the auto-expansion derived state (and the
        user's rows restorable by simply clearing the filter).
        """
        for node in nodes:
            below: list[tuple[TreeNode, int, bool]] = []
            self._visit_filtered(node.children, depth + 1, below, needle)
            if below or needle in node.label.lower():
                out.append((node, depth, bool(below)))
                out.extend(below)

    def _node_row(
        self,
        node: TreeNode,
        depth: int,
        opened: bool,
        current: bool,
        disabled: bool = False,
    ) -> Line:
        """One node's row: the guide and the label, in their text styles.

        The cursor row is one run -- the guide, the indicator and the label
        -- in no style of its own: its band is the row pipeline's
        (:func:`~motui.kernel.cell.rest`), ``rows.active`` while focused and
        ``rows.inactive`` while not.
        Every other row carries the guide in ``text.faint`` and the label
        in ``text.base`` and rests on the ground.  A disabled node (or a
        disabled tree) paints the whole row in ``text.faint``.  ``opened``
        is what the indicator draws -- the node's own ``open`` flag, or
        the filter's derived chain state -- and a leaf keeps the indicator
        column blank so labels align.  The column is the glyph pair's wider
        seat (:func:`~motui.kernel.glyphs.pair_seat`), so a wide glyph
        widens every row's column and a node whose state glyph is ``""``
        leaves a blank column of that width.
        """
        guide = " " * (self.indent * depth)
        pair_width = max(
            seat_width(self.glyphs.fold_open), seat_width(self.glyphs.fold_closed)
        )
        if node.children:
            glyph, other = (
                (self.glyphs.fold_open, self.glyphs.fold_closed)
                if opened
                else (self.glyphs.fold_closed, self.glyphs.fold_open)
            )
            indicator = pair_seat(glyph, other)
        else:  # a leaf keeps the indicator column blank so labels align
            indicator = " " * pair_width
        if disabled:
            return Line((Segment(guide + indicator + node.label, self.group("text").faint),))
        if current:
            return Line((Segment(guide + indicator + node.label),))
        text = self.group("text")
        return Line(
            (
                Segment(guide + indicator, text.faint),
                Segment(node.label, text.base),
            )
        )

    def __repr__(self) -> str:
        return f"Tree({self.nodes!r}, index={self.index})"

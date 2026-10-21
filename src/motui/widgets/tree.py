"""Tree: an indented, collapsible list of :class:`TreeNode` values.

``Tree`` walks its root nodes depth-first, descending into expanded nodes
only, and renders one row per visible node: ``indent`` spaces per depth, a
fold indicator (the vocabulary's ``\u25be``/``\u25b8`` by default) for a node
with children -- a blank indicator column for a leaf, so every label starts
at the same offset -- and the label itself.  Guides are deliberately
minimal: plain space indentation, **no ``\u2502`` connectors**.

The two indicator glyphs come from the keyword-only ``glyphs``
vocabulary -- ``fold_open`` and ``fold_closed``.  They are content, not
style, and their column is the state pair's wider seat
(:func:`~motui.core.glyphs.pair_seat`): a leaf, and a node whose glyph is
``""``, keeps a blank column of that same width, so labels stay aligned; a
wide (CJK) glyph widens the column for every row, and two empty glyphs
collapse it to zero columns.

**The row-band contract.**  Every row resolves its band from the theme's row
roles through :meth:`~motui.core.theme.RowStyles.band`: ``rows.base`` is
the resting surface, ``rows.active`` the band under the focused cursor row
and ``rows.inactive`` the unfocused one, ``rows.hover`` the pointer token,
and ``rows.disabled`` the band under a disabled row.  A row is its
text-styled segments -- the guide and the label in their own styles, the cursor row's
run in no style of its own -- then ``.fit(width).fill(fitted.width, band)``:
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
rows disappear.  Styles
resolve once, at construction, as explicit > theme > ``DEFAULT_THEME``.

Two host gestures narrow and steer the rows without the tree ever changing
its own data: ``filter(query)`` prunes the tree to the labels holding the
query (case-insensitive substring), keeps the ancestors of every hit and
renders those chains open -- the user's ``expanded`` flags are never
rewritten, so clearing the filter restores the tree the user built -- and
``jump(char)`` is type-ahead: the cursor hops to the next *visible* node
whose label starts with that character, case-insensitively, wrapping around
the rows.
"""

from __future__ import annotations

from dataclasses import replace

from ..core.cursor import Cursor
from ..core.glyphs import GLYPHS, Glyphs, pair_seat, seat_width
from ..core.lines import Line, Segment, rest
from ..core.style import NONE, Style
from ..core.theme import Theme, Themed

__all__ = ["Tree", "TreeNode"]


class TreeNode:
    """One tree node: a label, child nodes, an ``expanded`` flag and ``disabled``.

    A plain mutable class on purpose: :meth:`Tree.activate` flips
    ``expanded`` in place instead of rebuilding the path back to the root,
    which is what a frozen dataclass would force.  ``children`` is copied
    into a list; a node without children is a leaf and never expands.  A
    disabled node renders ``disabled_style`` and every cursor gesture skips
    or refuses it; its ``expanded`` flag is still the user's own state.
    """

    __slots__ = ("children", "disabled", "expanded", "label")

    def __init__(
        self,
        label: str,
        children=(),
        *,
        expanded: bool = False,
        disabled: bool = False,
    ) -> None:
        self.label = label
        self.children = list(children)
        self.expanded = expanded
        self.disabled = disabled

    def __repr__(self) -> str:
        return (
            f"TreeNode({self.label!r}, children={self.children!r}, "
            f"expanded={self.expanded}, disabled {self.disabled})"
        )


class Tree(Themed):
    """An indented node list with a cursor and per-node expand/collapse.

    ``root_nodes`` is any iterable of :class:`TreeNode`; ``indent`` is the
    per-depth space count.  ``selected`` is the visible node under the
    cursor (``None`` for an empty tree).  ``guide_style`` (default
    ``text.faint``) paints the indent and indicators, ``label_style``
    (default: plain) the unselected labels, and ``active_style`` (default
    ``rows.active``) is the band under the whole cursor row
    -- the row's own run carries no style of its own, the band rests
    underneath it.  ``disabled_style`` (default ``text.faint``)
    paints a disabled node's row.

    ``expanded`` and ``collapsed`` (default the vocabulary's ``\u25be`` and
    ``\u25b8``) are the fold glyphs: each row's indicator column is the
    pair's wider seat and a leaf keeps that column blank, so labels align
    whatever the glyphs measure; ``""`` disables a glyph (its state leaves
    the column blank) and two empty glyphs collapse the column.

    ``focused`` is the focus flag the focus tier sets
    (:class:`~motui.core.block.Focusable`): while it is ``True`` the
    cursor row's band is ``active_style``; while it is ``False`` that band
    is ``rows.inactive`` -- the cursor stays legible but loses weight, and
    every other row renders unchanged.

    ``hover`` is the pointer tier's flag
    (:class:`~motui.core.block.Hoverable`); :meth:`hover_at` marks the
    visible node row under the pointer and that row wears
    ``rows.hover`` -- the pointer's own token, whatever row it is on
    (D3).
    The marking starts ``None``, so an un-hovered tree renders
    byte-for-byte what it always did.

    :meth:`filter` prunes the visible rows to the labels holding a query
    (case-insensitive substring) and keeps the chain to every hit, rendered
    open -- the row's own ``\u25be``/``\u25b8`` indicator included; :meth:`jump`
    is the printable-key type-ahead.  Both read the ``expanded`` flags,
    neither writes them: the auto-expansion a filter shows is derived from
    the match structure on every walk, so clearing the filter brings the
    user's own rows back untouched.
    """

    __slots__ = (
        "_cursor",
        "_disabled_style",
        "_filter",
        "_guide_style",
        "_hover_index",
        "_label_style",
        "_row_styles",
        "disabled",
        "focused",
        "glyphs",
        "hover",
        "indent",
        "root_nodes",
        "theme",
    )

    def __init__(
        self,
        root_nodes,
        *,
        indent: int = 2,
        glyphs: Glyphs = GLYPHS,
        guide_style: Style | None = None,
        label_style: Style | None = None,
        active_style: Style | None = None,
        ground_style: Style | None = None,
        focused: bool = True,
        disabled: bool = False,
        disabled_style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.root_nodes = list(root_nodes)
        self.indent = indent
        self.glyphs = glyphs
        self.focused = focused
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_hover_index`` (:meth:`hover_at`).
        self.hover = False
        #: The whole tree refuses every cursor gesture when disabled.
        self.disabled = disabled
        self._cursor = 0
        # The active filter query (case-insensitive substring) or ``None``;
        # written by ``filter``, read by ``_visible``.  ``None`` -- the
        # default -- renders exactly the walk the tree always did.
        self._filter: str | None = None
        # The visible node row the pointer is on, or ``None``; written by
        # ``hover_at``, read by ``render``.  ``None`` renders byte-for-byte
        # what the tree always did.
        self._hover_index: int | None = None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._guide_style = self.pick(guide_style, self._theme.text.faint)
        self._label_style = label_style if label_style is not None else NONE
        self._disabled_style = self.pick(disabled_style, self._theme.text.faint)
        # The row bands: the theme's row roles, with the explicit style
        # parameters overriding their token.
        rows = self._theme.rows
        overrides: dict[str, Style] = {}
        if ground_style is not None:
            overrides["base"] = ground_style
        if active_style is not None:
            overrides["active"] = active_style
        if disabled_style is not None:
            overrides["disabled"] = disabled_style
        self._row_styles = replace(rows, **overrides) if overrides else rows

    def _band(self, current: bool, hovered: bool, disabled: bool = False) -> Style:
        """The surface one node row rests on: :meth:`RowStyles.band`, by precedence.

        The cursor row wears ``rows.active`` while focused and
        ``rows.inactive`` while not; the pointer's row ``rows.hover`` and a
        resting row ``rows.base``.  An explicit ``active_style`` /
        ``ground_style`` / ``disabled_style`` wins over its token.
        """
        return self._row_styles.band(
            active=current, hovered=hovered, focused=self.focused, disabled=disabled
        )

    @property
    def selected(self) -> TreeNode | None:
        """The visible node under the cursor, or ``None`` for an empty tree."""
        visible = self._visible()
        if not visible:
            return None
        return visible[self._cursor_index(visible)][0]

    def move(self, delta: int) -> bool:
        """Move the cursor by ``delta`` visible rows, skipping disabled nodes.

        Disabled rows are **stepped over**; a direction with no enabled
        visible row left clamps where it was (the data-view rule).  A
        disabled tree moves nowhere.
        """
        if self.disabled or delta == 0:
            return False
        visible = self._visible()
        if not visible:
            return False
        cursor = Cursor(
            len(visible),
            index=self._cursor,
            disabled={i for i, (node, _, _) in enumerate(visible) if node.disabled},
        )
        # The stored cursor may be stale after a collapse: start from the
        # clamped row, exactly as the render does, and report the clamping
        # itself as a move (the old raw-index comparison).
        cursor.index = cursor.clamp(self._cursor)
        moved = cursor.move(delta) or cursor.index != self._cursor
        self._cursor = cursor.index
        return moved

    def click(self, row: int, col: int) -> bool:
        """Place the cursor on the visible node at rendered row ``row``; True on a hit.

        ``row`` is a 0-based row of this component's own ``render`` -- the
        visible nodes, in draw order.  A row that is an enabled node answers
        ``True`` and moves the cursor there (even when it already was); a
        disabled node, a disabled tree, and any row past the last node
        answer ``False`` and leave the cursor alone.  ``col`` is ignored: a
        node row belongs to its node from the first indent column to the
        last label column -- no column narrows the hit.
        """
        if self.disabled:
            return False
        visible = self._visible()
        if not 0 <= row < len(visible):
            return False
        if visible[row][0].disabled:
            return False
        self._cursor = row
        return True

    def activate(self) -> bool:
        """Expand/collapse the node under the cursor; True when it changed.

        The tree's :class:`~motui.core.block.Activable` verb: with the
        cursor on a node, expanding or collapsing *is* the main operation.
        A leaf has nothing to expand, so activating one is a no-op and
        answers False; a disabled node or tree refuses activation.  A
        ``Tree`` deliberately has **no** ``take_result`` -- its activation
        is a fold, not a one-shot pick.  Collapsing can shrink the visible
        rows, so the cursor is clamped back into range afterwards.  While a
        :meth:`filter` is up the flag still flips -- it is the user's own
        state -- but the rendered chains follow the matches, so the fold
        becomes visible once the filter clears.
        """
        if self.disabled:
            return False
        node = self.selected
        if node is None or node.disabled or not node.children:
            return False
        node.expanded = not node.expanded
        self._cursor = Cursor(len(self._visible())).clamp(self._cursor)
        return True

    def filter(self, query: str | None) -> bool:
        """Prune the visible rows to the labels holding ``query``; True when they moved.

        A node stays visible when its own label holds ``query`` as a
        **case-insensitive substring** *or* a node below it does -- the
        ancestors of every hit are kept, so the chain to each match is on
        screen and renders **open** (the walk descends any kept node with
        kept children, whatever that node's own ``expanded`` flag says).
        An empty string matches every label (the substring rule), so
        ``filter("")`` shows the whole tree with every chain open; ``None``
        clears the filter.

        The auto-expansion is **derived, never written back**: the user's
        expansion set is exactly the nodes' ``expanded`` flags and the
        filter's own is recomputed from the match structure on every walk,
        so the two cannot drift -- ``filter(None)`` restores the user's rows
        because nothing was ever rewritten, and the filter never interferes
        with :meth:`activate`, whose fold simply waits for the filter to
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
        self._cursor = 0
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
        current = self._cursor_index(visible)
        for step in range(1, count + 1):
            row = (current + step) % count
            node = visible[row][0]
            if not node.disabled and node.label.lower().startswith(needle):
                self._cursor = row
                return row != current
        return False  # no enabled visible label starts with the character

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the visible node row under a cell; True when the marking changed.

        The pointer tier's row-level half (D3): ``row`` is a 0-based row of
        the visible nodes in draw order -- exactly what :meth:`click`
        consumes, minus the cursor move -- and ``col`` is ignored like
        ``click``'s (a node row owns the whole width).  A row past the last
        node answers "no node" and clears the marking; a negative ``row``
        clears it too (the pointer left).  The answer is whether the marked
        row changed, and :meth:`render` rests that row on the theme's
        ``hover`` band -- the pointer's own token, whatever row it is on.
        """
        if row < 0:
            target = None
        else:
            visible = self._visible()
            target = row if 0 <= row < len(visible) else None
        changed = target != self._hover_index
        self._hover_index = target
        return changed

    def revision(self) -> object:
        """The tree's value snapshot: the node shape, cursor, marks, bands.

        The one non-trivial part is :meth:`_node_shape`: every node's
        ``(label, expanded, disabled)`` in document order, because a node's
        flag can be flipped in place (that is what :meth:`activate` does)
        and the labels decide both the rows the unfiltered walk draws and
        the matches the filtered one keeps -- a *reference* to the root list
        would compare equal to itself after such a flip, which is exactly
        the freeze the snapshot exists to prevent.  The walk is the price:
        it costs one node visit per snapshot, far below the render it
        guards (which visits every node *and* builds a row for each visible
        one).  Beside it go the filter query, the cursor, the pointer's
        mark, the focus and disabled flags, the indent, the two fold glyphs,
        the disabled text style and the band value.
        """
        return (
            self._node_shape(),
            self._filter,
            self._cursor,
            self._hover_index,
            self.focused,
            self.disabled,
            self.indent,
            self.glyphs,
            self._guide_style,
            self._label_style,
            self._disabled_style,
            self._row_styles,
        )

    def _node_shape(self) -> tuple[tuple[str, bool, bool], ...]:
        """The whole tree as ``(label, expanded, disabled)`` triples, depth-first.

        A value view of the mutable :class:`TreeNode` graph: whatever a host
        or an :meth:`activate` does to the roots -- a flip, a re-label, a
        disabled toggle, a child added or removed, a subtree reordered --
        moves this tuple, and two equal tuples describe two trees whose
        walks can only agree.
        """
        out: list[tuple[str, bool, bool]] = []

        def walk(nodes) -> None:
            for node in nodes:
                out.append((node.label, node.expanded, node.disabled))
                walk(node.children)

        walk(self.root_nodes)
        return tuple(out)

    def render(self, width: int) -> list[Line]:
        """One row per visible node, each through the row-band contract."""
        visible = self._visible()
        cursor = self._cursor_index(visible)
        out: list[Line] = []
        for i, (node, depth, opened) in enumerate(visible):
            node_disabled = self.disabled or node.disabled
            out.append(
                rest(
                    self._node_row(node, depth, opened, i == cursor, node_disabled),
                    width,
                    self._band(i == cursor, i == self._hover_index, node_disabled),
                )
            )
        return out

    def _visible(self) -> list[tuple[TreeNode, int, bool]]:
        """The visible nodes as ``(node, depth, open)`` triples, in draw order.

        ``open`` is what the row's own indicator shows: the node's
        ``expanded`` flag on the unfiltered walk, and "this node holds a
        kept child" on the filtered one (:meth:`_walk_filtered`) -- so a
        drawn ``\\u25be`` never disagrees with the rows actually below it,
        and the filter's derived auto-expansion is visible in the indicator
        without the flag ever being written.
        """
        out: list[tuple[TreeNode, int, bool]] = []
        if self._filter is None:
            self._walk(self.root_nodes, 0, out)
        else:
            self._walk_filtered(self.root_nodes, 0, out, self._filter.lower())
        return out

    def _walk(
        self, nodes, depth: int, out: list[tuple[TreeNode, int, bool]]
    ) -> None:
        for node in nodes:
            out.append((node, depth, node.expanded))
            if node.expanded:
                self._walk(node.children, depth + 1, out)

    def _walk_filtered(
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
        indicator draws).  The ``expanded`` flags are not read here, which
        is exactly what makes the auto-expansion derived state (and the
        user's rows restorable by simply clearing the filter).
        """
        for node in nodes:
            below: list[tuple[TreeNode, int, bool]] = []
            self._walk_filtered(node.children, depth + 1, below, needle)
            if below or needle in node.label.lower():
                out.append((node, depth, bool(below)))
                out.extend(below)

    def _cursor_index(self, visible: list[tuple[TreeNode, int, bool]]) -> int:
        """The cursor clamped into the visible rows (hosts may mutate roots)."""
        return Cursor(len(visible)).clamp(self._cursor)

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
        (:func:`~motui.core.lines.rest`), ``rows.active`` while focused and
        ``rows.inactive`` while not.
        Every other row carries the guide in ``guide_style`` and the label
        in ``label_style`` and rests on the ground.  A disabled node (or a
        disabled tree) paints the whole row in ``disabled_style``.  ``opened``
        is what the indicator draws -- the node's own ``expanded`` flag, or
        the filter's derived chain state -- and a leaf keeps the indicator
        column blank so labels align.  The column is the glyph pair's wider
        seat (:func:`~motui.core.glyphs.pair_seat`), so a wide glyph
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
            return Line((Segment(guide + indicator + node.label, self._disabled_style),))
        if current:
            return Line((Segment(guide + indicator + node.label),))
        return Line(
            (
                Segment(guide + indicator, self._guide_style),
                Segment(node.label, self._label_style),
            )
        )

    def __repr__(self) -> str:
        return f"Tree({self.root_nodes!r}, cursor={self._cursor})"

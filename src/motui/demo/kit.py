"""The demo's kit: the exhibit grammar and the action protocol, one home.

A page is one template: its title rule (``── forms ────``) and one dim
blurb line, then its groups -- each a section rule (`` ── input ──``), the
group's components and an optional one-line dim caption -- and every pick
a component lands is one :class:`Pick`: the component it came from, the
:class:`Action` it means when it carries one, and its raw value.
:class:`Exhibit` builds that list, the page's focus ring and its hooks; the
host resolves picks through :meth:`Exhibit.resolve_picks` -- which runs the
action, or reports what only reports itself -- so the demo's routing is
data, never a page's name in host code (D3)::

    index = Table(["page", "group", "what"], rows=[...])
    exhibit.section("the index", index, caption="enter opens the row's page")

The grammar the old module-level ``header`` / ``try_line`` / ``section`` /
``api_note`` helpers spelled lives in :meth:`Exhibit.section` alone (D3):
the free-prose channel is gone -- signatures and the full story live on the
notes page, and a page keeps at most the one factual caption line
:meth:`Exhibit.show`'s group carries.  :class:`Echo` owns the one-line pick
readout a page used to format by hand.

Nothing here subclasses a component: a ``Button``, a ``Checkbox``, a
``Slider``, a ``Select`` and a text block's inline payloads all reduce to
the same :class:`Pick`.  Page data a generic host gesture needs but no
widget can hold (the widgets' ``__slots__`` refuse new attributes) rides
:attr:`Slot.meta`, which ``build`` forwards as the body's ``slot_meta``
lookup -- the views page's ``c-t`` queries are the one user of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Sequence

from motui import FocusRing, Option, Text
from motui.kernel import Line
from motui.kernel.block import Component
from motui.kernel.text import visible_width
from motui.kernel.theme import Theme
from motui.widgets import Divider, Padding

from .page import PageBody

if TYPE_CHECKING:
    from .session import Session

__all__ = ["Action", "Echo", "Exhibit", "Pick", "Section", "Slot"]


@dataclass(frozen=True)
class Action:
    """A pick that says what it does: the demo's one action vocabulary.

    A page hands an ``Action`` to a component as the *payload* of the row
    it belongs to (an ``Option``'s value, a ``Radio`` label, a
    ``Markdown`` ``todo:`` payload...).  The session reads the pick and
    runs it with itself: ``run(session)``.  ``id`` is the row's identity
    in the inventory (the old payload string); ``label`` the text a report
    prints; ``run`` the effect, or ``None`` for a pick that only reports
    itself.

    The demo's routing is therefore data: a page that wants a row to open
    another page writes ``Action(repr(page.name), page.name,
    lambda s: s.show(page))`` and the session needs no knowledge of it.
    """

    id: str
    label: str
    run: Callable[["Session"], None] | None = None


@dataclass(frozen=True)
class Pick:
    """One read pick: the component it came from and what it means.

    ``value`` is the pick's value, unwrapped: an ``Option``'s payload (or
    the option itself when it carries none), a list's items (the
    multi-selection family), a ``Radio``'s value, a button's ``True``.
    ``action`` is the :class:`Action` the pick carries -- the value itself,
    an option's payload, or the slot's fallback -- or ``None`` when the
    pick only reports itself.
    """

    source: Component
    action: Action | None
    value: object


@dataclass
class Slot:
    """One exhibit's component and what its pick means.

    ``meta`` is the page's own data for the exhibit -- the kit never reads
    it, and :meth:`Exhibit.build` hands the host a lookup for it
    (``body.slot_meta``), so a page can seed a generic gesture the host
    runs without knowing the page: the views page hangs its canned ``c-t``
    queries there.  Components themselves cannot carry such data -- the
    widgets' ``__slots__`` refuse new attributes -- so the slot is the
    seat.
    """

    component: Component
    action: Action | None = None      # fallback when the component carries none
    note: str = ""                    # the echo's line prefix ("shipped", ...)
    meta: object = None               # the page's own data; the kit never reads it
    _ring: list[Component] | None = field(default=None, repr=False, compare=False)

    def focus(self) -> Slot:
        """Register the component in the page's ring, in this call's order."""
        if self._ring is not None:
            self._ring.append(self.component)
        return self

    def hint(self, text: str) -> Slot:
        """Hand the component the tooltip band's one-line hint."""
        self.component.hint = text
        return self


@dataclass
class Section:
    """One demo group: a spec, its blocks, an optional caption, its focus targets.

    ``spec`` is the group's one-line subject (``"input -- an empty one and
    a filled one"``), rendered into the `` ── spec ──`` rule that opens the
    group; ``blocks`` are the components it mounts, in order; ``caption``
    the group's one dim line, written after the blocks when it is not
    empty (a page may set it on the returned record while it streams the
    blocks in); ``focus`` the components this group registers in the
    page's ring, in the order given.  ``width`` records the width the
    group asked its blocks to render at (``None``: the page's own -- the
    blocks mount bare so the host's flat pick scan still sees them);
    ``draft`` marks a caption W1 only compressed out of an old section
    title or a component fact, for W2's pass over the captions.
    """

    spec: str
    blocks: list[Component] = field(default_factory=list)
    caption: str = ""
    focus: list[Component] = field(default_factory=list)
    width: int | None = None
    draft: bool = False


def _spec_rule(spec: str, theme: Theme) -> Component:
    """The section rule: a leading space, the spec, a short closing run.

    ``Divider`` spells the rule itself (``── spec ──``); the one-column
    ``Padding`` insets it so the section reads as subordinate to the page
    rule above it, and the divider's capped width keeps the closing run
    two cells long instead of a second full-width rule.  A spec too long
    for the paint width ellipsizes through ``Divider``'s own rule; nothing
    here rewrites or wraps the text.
    """
    return Padding(
        Divider(theme=theme, label=spec, max_width=visible_width(spec) + 6),
        left=1,
    )


class Echo:
    """The pick readout: one self-updating line over ``Text``.

    Empty until the first report -- ``render`` answers no rows, so a page
    carries the echo without paying for it before anything is played with
    -- and :meth:`set` writes ``"<label> ▸ <value>"`` into the wrapped
    line.  ``set(None)`` clears it back to empty.  The page mounts the
    echo like any other component; the exhibit writes it on every report
    (:meth:`Exhibit.resolve_picks` -> the session's report -> the body's
    ``note``).
    """

    __slots__ = ("_line", "label")

    def __init__(self, label: str = "echo") -> None:
        self.label = label
        self._line = Text("")

    @property
    def text(self) -> str:
        """The line's current text, ``""`` while nothing was reported."""
        return self._line.text

    def set(self, value: object, label: str | None = None) -> None:
        """Write one report onto the line; ``None`` clears it back to empty."""
        prefix = self.label if label is None else label
        self._line.text = "" if value is None else f"{prefix} \u25b8 {value}"

    def render(self, width: int) -> list[Line]:
        """The line's own rows -- none while nothing was reported."""
        return [] if not self._line.text else self._line.render(width)

    def __repr__(self) -> str:
        return f"Echo({self.label!r}, text={self._line.text!r})"


class Exhibit:
    """One page's exhibit: the grammar, the ring and the pick resolution.

    The constructor mounts the page's opening rows (the title rule and the
    one blurb line) and reads the theme off the session then;
    :meth:`section` opens the page's groups, :meth:`show` mounts one
    component into the open group and :meth:`text` writes the rare dim line
    a page must say itself; :meth:`build` closes the page into a
    :class:`~motui.demo.page.PageBody` -- the blocks, a focus ring over the
    components the page registered, the pick note, and whichever of
    ``modal`` / ``tick`` / ``enter`` / ``leave`` the page armed.

    The pick read is the session's door: ``build`` hangs
    :meth:`resolve_picks` on the body as ``resolve_picks``, and a host that
    finds one uses it instead of scanning the blocks itself.
    """

    def __init__(
        self,
        session: Session,
        *,
        title: str,
        blurb: str,
        echo_label: str = "echo",
    ) -> None:
        self.session = session
        self.theme = session.theme
        #: The page's blocks, in mounting order (``build`` copies the list).
        #: The title rule opens the page, the blurb line under it (D3).
        self.blocks: list[Component] = [
            Divider(theme=self.theme, label=title, label_style=self.theme.accent),
            Text(blurb, style=self.theme.dim),
        ]
        #: The page's groups, in mounting order, as :class:`Section` records.
        self.sections: list[Section] = []
        #: The pick readout: the page shows it where it wants it.
        self.echo = Echo(echo_label)
        #: The page's open modal, if it has one; ``build`` forwards it.
        self.modal: Component | None = None
        #: The page's round beat, if it has one; ``build`` forwards it.
        self.tick: Callable[[], None] | None = None
        #: The page's pane hooks, if it has any; ``build`` forwards them.
        self.enter: Callable[[Session], None] | None = None
        self.leave: Callable[[Session], None] | None = None
        self._section: Section | None = None  # the open group show() streams into
        self._slots: list[Slot] = []
        self._targets: list[Component] = []
        self._watchers: list[Callable[[Pick], None]] = []

    # -- the grammar -------------------------------------------------------------

    def section(
        self,
        spec: str,
        *blocks: Component,
        caption: str = "",
        focus: Sequence[Component] = (),
        width: int | None = None,
        draft: bool = False,
    ) -> Section:
        """Open one group; answer its :class:`Section` record.

        Closes the previous group first (its caption line lands between the
        two groups), then mounts the section rule `` ── spec ──`` and
        ``blocks``; further :meth:`show` calls stream into this group.
        ``focus`` registers ring targets in the order given -- the same
        seat as :meth:`focus`, for a group whose order is the section
        order -- and ``caption`` is the group's one dim line, written after
        the last block (empty for none).
        """
        self._close_section()
        group = Section(spec=spec, caption=caption, width=width, draft=draft)
        self.sections.append(group)
        self._section = group
        self.blocks.append(_spec_rule(spec, self.theme))
        for component in blocks:
            self.show(component)
        self.focus(*focus)
        return group

    def caption(self, text: str) -> None:
        """Set the open group's one-line caption (the same seat as the parameter).

        The line is written when the group closes, so a page can stream a
        group's blocks with :meth:`show` and caption it afterwards.
        """
        if self._section is not None:
            self._section.caption = text

    def show(
        self,
        component: Component,
        *,
        note: str | None = None,
        action: Action | None = None,
        hint: str | None = None,
    ) -> Slot:
        """Mount one exhibit in the open group; answer its :class:`Slot` for chaining.

        The component goes into the page's blocks, right after the group's
        own rule and whatever mounted before it.  ``note`` is the slot's
        report prefix, ``action`` the fallback the slot's pick means when
        the component carries none, and ``hint`` the one-line tooltip the
        component is handed.
        """
        slot = Slot(component, action=action, note=note or "", _ring=self._targets)
        if hint is not None:
            slot.hint(hint)
        self.blocks.append(component)
        if self._section is not None:
            self._section.blocks.append(component)
        self._slots.append(slot)
        return slot

    def focus(self, *components: Component) -> None:
        """Register ring targets, in call order (``section(focus=…)`` is the same).

        The ring is the registration order, not the mounting order: a page
        that walks its ring the way its own story reads calls this once
        with the order spelled out.
        """
        self._targets.extend(components)

    def text(self, text: str) -> Text:
        """Mount one dim line between exhibits; answer the block.

        The seat for the rare line that is neither a component nor a
        caption -- one line, a fact, never a paragraph: the full story
        lives on the ``notes`` page.
        """
        block = Text(text, style=self.theme.dim)
        self.blocks.append(block)
        return block

    def watch(self, fn: Callable[[Pick], None]) -> None:
        """Register a hook called with every pick the page resolves."""
        self._watchers.append(fn)

    # -- the build and the picks -------------------------------------------------

    def build(self) -> PageBody:
        """Close the page; the body carries the kit's pick resolver."""
        self._close_section()
        body = PageBody(
            blocks=list(self.blocks),
            focus=FocusRing(self._targets),
            note=self._note,
            tick=self.tick,
            enter=self.enter,
            leave=self.leave,
            modal=self.modal,
        )
        body.resolve_picks = self.resolve_picks  # type: ignore[attr-defined]
        #: The page's own slot metadata, by component (:meth:`slot_meta`):
        #: the second seam the host reads a page through, beside the picks.
        body.slot_meta = self.slot_meta  # type: ignore[attr-defined]
        return body

    def slot_meta(self, component: Component) -> object:
        """The page's own ``meta`` for the slot ``component`` was shown as.

        ``None`` for a component no slot of this page introduced, and for
        a slot that registered none: the host answers "this page seeded
        nothing here" the same way for both.
        """
        slot = self._slot_of(component)
        return None if slot is None else slot.meta

    def resolve_picks(self, report: Callable[[Pick], None]) -> bool:
        """Read every pending pick once, clearing it; run it, or report it.

        The page's own blocks are the inventory -- the exhibit holds the
        components, so no container is ever descended -- and each
        component's non-``None`` ``chosen`` becomes one :class:`Pick`
        (:meth:`_picked` unwraps an ``Option``, a list, and reads the
        slot's action fallback).  A pick that means an action with a
        ``run`` is run with the session and is **not** reported -- a row
        that says what it does does not have to echo it; anything else --
        a bare value, an action that only reports itself -- goes through
        ``report`` as it is.  Every resolved pick then reaches the page's
        :meth:`watch` hooks, whatever it meant.
        Answers whether any pick was read; each ``chosen`` is reset before
        it is used, so no pick is ever read twice.
        """
        resolved = False
        for component in self.blocks:
            chosen = getattr(component, "chosen", None)
            if chosen is None:
                continue  # nothing pending: not a pick
            component.chosen = None  # the host reads a pick exactly once
            resolved = True
            pick = self._picked(component, chosen)
            if pick.action is not None and pick.action.run is not None:
                pick.action.run(self.session)
            else:
                report(pick)
            for watcher in self._watchers:
                watcher(pick)
        return resolved

    # -- internals ---------------------------------------------------------------

    def _close_section(self) -> None:
        """Write the open group's caption line, when it has one, and close it."""
        group = self._section
        self._section = None
        if group is not None and group.caption:
            self.blocks.append(Text(group.caption, style=self.theme.dim))

    def _note(self, pick: Pick) -> None:
        """One report landed: write the echo line.

        The session's ``report`` shows the toast and hands the pick to this
        body's ``note``; the slot's own ``note`` is the line's prefix when
        it carries one (the echo's label otherwise).  The page's own
        reactions are ``watch`` hooks, called by :meth:`resolve_picks`.
        """
        slot = self._slot_of(pick.source)
        prefix = None if slot is None or not slot.note else slot.note
        self.echo.set(pick.value, prefix)

    def _picked(self, component: Component, chosen: object) -> Pick:
        """Reduce one read ``chosen`` to its :class:`Pick`."""
        value = _unwrapped(chosen)
        slot = self._slot_of(component)
        action = (
            value if isinstance(value, Action)
            else None if slot is None else slot.action
        )
        return Pick(component, action, value)

    def _slot_of(self, component: Component) -> Slot | None:
        """The slot ``component`` was shown as, by identity."""
        return next(
            (slot for slot in self._slots if slot.component is component), None
        )


def _unwrapped(chosen: object) -> object:
    """A read ``chosen`` as the pick's value: options unwrap to their payloads."""
    if isinstance(chosen, Option):
        return chosen.value if chosen.value is not None else chosen
    if isinstance(chosen, list):
        return [_unwrapped(item) for item in chosen]
    return chosen

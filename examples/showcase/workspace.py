"""The workspace exhibit: a chat on the left, a tabbed inspector on the right.

The page is a **layout** rather than a list of rows.  The transcript -- the
page's own blocks, on the main document -- is a canned working session
(``Message`` turns, a ``ToolBlock`` running the suite, an ``EditBlock``
landing the change), and beside it the page opens a right pane of its own
through :attr:`~showcase.page.PageBody.aside`: a four-label ``Tabs`` strip
pinned at the pane's top (``tools / edits / reads / agent``) and **one**
content block below it, swapped as the strip moves.

The switch is deterministic.  :meth:`Inspector.sync` -- run by the host
once after every event round -- compares the strip's ``active`` with the
view on screen and, when they differ, removes the old content block **by
id**, adds the new one and scrolls the pane back to its top
(``scroll_up(1 << 20)``).  Both roads end there: a click resolves through
``hit_test`` -> ``FocusRing.click`` -> ``Tabs.click``, and ``tab`` focuses
the strip while ``\u2190\u2192`` drive ``Tabs.move`` (clamped at the ends).
No ``tick`` is involved in a switch, so a piped replay or a ``--pages``
dump shows exactly the view the last event picked.

Three of the four views are factories of the theme, kept in :data:`VIEWS`
by tab name: a tool call with its whole output (``tools``), a small diff
(``edits``), and a real excerpt from ``src/mocode_tui/focus.py`` rendered
by ``Markdown``'s python fence (``reads``).  The fourth, ``agent``, is
**live**: an :class:`AgentStream` -- the page-side controller, shaped
after the streaming exhibit's -- holds a canned seven-beat subagent
report and grows it one beat per page tick, so the view opens as a
progress row (``agent: k/7 messages``) over the messages that have
arrived and ends ``done``.  The tick touches the view's content only;
which tab is mounted stays :meth:`Inspector.sync`'s business, one event
behind no clock.  That column is the extension point: a host growing it
live appends a message and invalidates the frame, the same road the chat
layer's transcript takes.

**Wiring a real subagent.**  The beats here are canned, but the road is the
one a host would take for real: a message arriving from a subagent is
appended to the column the view mounts (an ``AgentStream``'s ``view`` --
its ``children`` list), the frame is invalidated (``tui.invalidate()``),
and the next paint shows the message.  The components are the chat
layer's own ``Message`` / ``ToolBlock``, the same batch the transcript
beside this pane mounts, so a real report reads exactly like the canned
one.  ``Transcript.stream``'s ``StreamHandle`` road applies unchanged: a
handle per message as it arrives, appended where a beat's block goes.
**No callback, no event bus and no async component** is involved -- the
view is a list the host owns, exactly as the transcript's is, and the
page tick is only this demo's own clock.

The right pane is the page's own: the host opens it from
:meth:`~showcase.session.Showcase.show` and closes it when the page is
left, so ``/split`` -- which shares that one slot -- yields on this page
with a toast instead of stacking a third pane.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from mocode_tui import (
    Column,
    Component,
    EditBlock,
    FocusRing,
    Markdown,
    Message,
    Pane,
    Tabs,
    Text,
    ToolBlock,
    Theme,
)

from .page import PageBody, api_note, header, section, try_line

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["AGENT_BEATS", "NAMES", "VIEWS", "AgentStream", "Inspector", "page"]

#: The inspector's tab labels, in order -- short on purpose, so the whole
#: strip renders inside the right pane's 37 columns without truncation (a
#: truncated label cannot be clicked).
NAMES: tuple[str, ...] = ("tools", "edits", "reads", "agent")

#: The tools view's body: one run, its whole output -- the narrow rows a
#: 37-column pane can hold without wrapping.
TOOL_OUTPUT: tuple[str, ...] = (
    "collected 949 items",
    "",
    "948 passed, 1 skipped in 4.60s",
    "",
    "1 skipped: no pty in this harness",
    "probe: 2 panes on, 1 after",
    "probe: /split toasts, slot taken",
    "probe: click 'reads' -> new view",
    "probe: offset 0 after the swap",
)


#: The reads view: a real excerpt from ``src/mocode_tui/focus.py`` -- the
#: focus move and the one-line flag rewrite -- kept to the narrow rows the
#: right pane can hold without wrapping (35 columns at most here).
READS_SNIPPET = '''\
```python
# focus.py -- FocusRing.focus()
if not self._registered(target):
    return False
self._set_focused(target)
return True

# the flags, rewritten in one move
self._focused = target
for known in self._targets:
    known.focused = known is target
```
'''


def _tools_view(theme: Theme) -> Component:
    """The ``tools`` view: one command and its output, the whole call."""
    return ToolBlock(
        "$ uv run pytest -q",
        TOOL_OUTPUT,
        tone="tool",
        footer="Took 4.6s",
        theme=theme,
    )


def _edits_view(theme: Theme) -> Component:
    """The ``edits`` view: the diff the conversation produced.

    A small one, in the layer's own voice: the hook changed from comparing
    a cached index to reading the strip -- which is the road this page's
    ``sync`` actually takes.
    """
    return EditBlock(
        "examples/showcase/workspace.py",
        context=["def sync(self) -> None:"],
        removed=["    if index == self.index:"],
        added=["    index = self.strip.active", "    self._swap(index)"],
        theme=theme,
    )


def _reads_view(theme: Theme) -> Component:
    """The ``reads`` view: a file's body, syntax-highlighted by the fence.

    The text is :data:`READS_SNIPPET` -- ``Markdown``'s python fence is the
    highlighter, so the view costs one component and no new renderer.
    """
    return Markdown(READS_SNIPPET, theme=theme)


#: The canned subagent report, beat by beat: ``(kind, text, lines)``.
#: ``kind`` is a ``Message`` role (``thinking`` / ``assistant``) or a
#: ``ToolBlock`` tone (``tool`` / ``code`` -- ``text`` its title, ``lines``
#: its output).  Seven beats is one small job: read the frame layer,
#: conclude, check the two roads, run the suite, file the report.  The rows
#: stay narrow: the pane the report grows in is 36 columns wide.
AGENT_BEATS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("thinking", "subagent: reading the frame layer before answering\u2026", ()),
    ("code", "read src/mocode_tui/core/frame.py",
     ("Pane.split -> children", "Pane.close -> collapse")),
    ("assistant", "The right pane is a leaf: split once, close it on the way out.", ()),
    ("code", "$ rg -n _open_aside examples",
     ("218: self._close_aside()", "224: self._open_aside()")),
    ("thinking", "the strip pins, the view swaps by id, the pane parks at its top\u2026", ()),
    ("tool", "$ pytest tests/test_frame.py -q", ("34 passed in 0.31s",)),
    ("assistant", "Report filed: the pane is a leaf, closed on the way out -- "
     "the rest is routing.", ()),
)


def _beat_block(beat: tuple[str, str, tuple[str, ...]], theme: Theme) -> Component:
    """One beat as its component: a ``Message``, or a ``ToolBlock`` for a tool.

    The same two shapes the chat layer draws with: ``kind`` in
    :data:`AGENT_BEATS` is the message's role or the tool block's tone, so
    one canned tuple builds the component the beat mounts.
    """
    kind, text, lines = beat
    if kind in ("tool", "code"):
        return ToolBlock(text, list(lines), tone=kind, theme=theme)
    return Message(kind, text, theme=theme)


class AgentStream:
    """The agent view's page-side controller: one canned message per beat.

    The streaming exhibit's pattern, one level down: this controller owns
    the view -- a ``Column`` whose first row is the progress line and whose
    rows below are the beats that have arrived -- plus a cursor and a state
    (``playing`` or ``done``).  :meth:`beat` is the whole beat, called by
    the page's tick; :meth:`advance` and :meth:`finish` are the raw moves
    beneath it.  Nothing here sleeps or repaints: the host invalidates the
    frame after the tick, so the growth is painted with the beat that made
    it, and the whole controller is a state a dump can read rather than a
    task a dump must wait for.

    **A non-interactive stream is a finished one.**  ``interactive=False``
    (the piped replay, ``--pages``) builds the view whole, and
    :meth:`restart` -- the entry into the tab -- restarts it whole there
    too: no clock runs on those paths, so a partial report would be a dump
    that lies, not a promise.  On a real terminal the paragraph above is
    literal: the tab opens on the progress row and the beats arrive one per
    beat of :data:`~showcase.session.PAGE_TICK`.

    **The view is one block.**  The pane's swap removes and adds the column
    as a single component, and the stream mutates its rows in place, so
    entering the tab is still one remove and one add -- of a column that
    :meth:`restart` has just refilled from its first beat.
    """

    __slots__ = ("_beats", "_column", "_progress", "cursor", "interactive", "playing")

    def __init__(self, theme: Theme, *, interactive: bool) -> None:
        self._beats = [_beat_block(beat, theme) for beat in AGENT_BEATS]
        self._progress = Text("", style=theme.dim)
        self._column = Column([self._progress])
        self.cursor = 0
        self.interactive = interactive
        # A tab the user opens is a stream that runs; a dump is a report.
        self.playing = interactive
        if interactive:
            self._render()  # the progress row over nothing, about to grow
        else:
            self.finish()  # no clock on this path: the report is whole

    @property
    def view(self) -> Component:
        """The one content block: the progress row over the grown beats."""
        return self._column

    @property
    def total(self) -> int:
        """How many beats the canned report holds."""
        return len(self._beats)

    @property
    def done(self) -> bool:
        """Whether every beat is on screen."""
        return self.cursor >= self.total

    def advance(self, count: int = 1) -> None:
        """Mount the next ``count`` beats, never past the end; landing there stops.

        The auto-stop is the completing beat's: the report is whole, so the
        stream is no longer playing -- and the beat repaints the progress
        row with the ``done`` that stop puts there.
        """
        self.cursor = min(self.cursor + max(count, 0), self.total)
        if self.done:
            self.playing = False
        self._render()

    def finish(self) -> None:
        """Put every beat on screen in one step, and hold."""
        self.cursor = self.total
        self.playing = False
        self._render()

    def restart(self) -> None:
        """Back to the first beat, running -- or whole, with no clock to run it.

        The entry rule: every swap into the ``agent`` tab opens through
        :meth:`open_view`, which restarts here, so leaving and coming back
        replays the report.  A non-interactive stream cannot be replayed by
        a clock that does not run, so it restarts finished.
        """
        if self.interactive:
            self.cursor = 0
            self.playing = True
            self._render()
        else:
            self.finish()

    def beat(self) -> None:
        """One page beat: mount one message while playing."""
        if self.playing:
            self.advance(1)

    def open_view(self, _theme: Theme) -> Component:
        """The view as a factory: restart, then hand the column over.

        The shape a :data:`VIEWS` entry has, so the pane's view table reads
        the same for all four names -- and this call **is** entering the
        tab: the swap goes through the factory, and the report replays from
        its first beat.  The theme goes unused: the stream already built
        its beats on the theme in force, and a theme switch rebuilds the
        whole page (hence a fresh stream).
        """
        self.restart()
        return self._column

    def status(self) -> str:
        """The progress row: how far the report is, and whether it is done."""
        state = " \u00b7 done" if self.done and not self.playing else ""
        return f"agent: {self.cursor}/{self.total} messages{state}"

    def _render(self) -> None:
        """Publish the cursor's prefix: the progress row, then the beats."""
        self._progress.text = self.status()
        self._column.children = [self._progress, *self._beats[: self.cursor]]


#: The inspector's static views, by tab name -- each a factory of the theme,
#: so a swap builds fresh components on the theme in force.  The fourth
#: name, ``agent``, is the live view and is not in this table: its factory
#: needs the pane's stream and the session's clock, so
#: :class:`Inspector` splices :meth:`AgentStream.open_view` into its own
#: per-pane table under the same name -- one seam, one call per swap.
VIEWS: dict[str, Callable[[Theme], Component]] = {
    "tools": _tools_view,
    "edits": _edits_view,
    "reads": _reads_view,
}


class Inspector:
    """The right pane's controller: the strip, the view, the status row.

    ``strip`` is the pane's only interactive widget -- the page's
    :class:`~mocode_tui.focus.FocusRing` holds exactly it -- and the host
    hands the controller's :meth:`mount` to
    :attr:`~showcase.page.PageBody.aside` and its :meth:`sync` to
    :attr:`~showcase.page.PageBody.sync`.  The controller is built before
    the pane exists (the ring needs the strip at construction) and is
    filled in by ``mount`` when the host's ``show`` opens the pane.

    The switch is the state machine the strip drives and ``sync`` lands:
    ``index`` is the view **on screen**, ``strip.active`` the one the user
    picked -- a click or an arrow moves the strip, and the very next
    ``sync`` (one per event round) sees the two disagree, swaps the content
    block and scrolls the pane back to its top.  No ``tick`` is involved,
    so the screen is never a frame behind the pick and a dump is exact.

    ``views`` is the pane's own view table: :data:`VIEWS`'s static
    factories with :meth:`AgentStream.open_view` spliced into the
    ``agent`` slot, because the live view is this pane's (one stream per
    build of the page).  The table is the switch's only source, so a swap
    never asks which view it is building -- and ``tick``, the page's beat,
    is the one hook that touches a view's **content** (the report growing),
    never which view is mounted.
    """

    def __init__(self, theme: Theme, *, interactive: bool) -> None:
        self.theme = theme
        self.strip = Tabs(list(NAMES), theme=theme)
        self.index = 0
        #: The live view's controller: it owns the agent column and grows it.
        self.agent = AgentStream(theme, interactive=interactive)
        #: The view table, by tab name: :data:`VIEWS` plus the stream's
        #: factory -- the one name whose "fresh component" is a column the
        #: stream keeps (and refills on every entry).
        self.views: dict[str, Callable[[Theme], Component]] = {
            **VIEWS,
            "agent": self.agent.open_view,
        }
        self.view: Component = self.views[NAMES[0]](theme)
        self.status = Text(self._label(0), style=theme.dim)
        self.pane: Pane | None = None
        self.block_id: str | None = None

    def mount(self, pane: Pane) -> None:
        """Fill the pane the host opened: the strip pinned, one content block.

        The strip goes in first with ``pin="top"`` so it holds the pane's
        first row while the content scrolls under it; the content block
        below it is the current view plus its status row -- one block, so a
        swap is one remove and one add.  The pane is parked at its top, the
        way :meth:`~showcase.session.Showcase.show` parks the transcript: a
        fresh pane whose content overflows a short terminal must open on the
        view's first row, not its last (a no-op when the view fits).
        """
        self.pane = pane
        pane.document.add(self.strip, pin="top")
        self.block_id = pane.document.add(self.content()).id
        pane.viewport.scroll_up(1 << 20)

    def content(self) -> Component:
        """The one content block: the current view, then its status row."""
        return Column([self.view, self.status])

    def tick(self) -> None:
        """The page's beat: grow the report while ``agent`` is on screen.

        The tick owns the view's content -- one beat, one message -- and
        never the tab: which view is mounted changes only in :meth:`sync`,
        an event's business, behind no clock.  A page beat with the strip
        on any other view is a no-op.
        """
        if NAMES[self.index] == "agent":
            self.agent.beat()

    def sync(self) -> None:
        """The once-per-event hook: land the strip's state on the pane.

        Both roads to a switch end here: the click policy ran
        ``Tabs.click`` and the ring's arrow ran ``Tabs.move``, either way
        against the strip alone -- the host then calls this once, and the
        pane follows.  A strip that still names the view on screen answers
        nothing, so an unrelated event is a no-op.
        """
        if self.pane is None:
            return
        index = self.strip.active
        if index != self.index:
            self._swap(index)

    def _swap(self, index: int) -> None:
        """Replace the content block for tab ``index`` and scroll back up.

        The documented ``Document`` pair -- remove the old block **by id**
        (``remove`` takes the id string), add the new one -- then
        ``viewport.scroll_up(1 << 20)`` parks the pane at its top, so the
        new view opens where a view opens.  The factory builds the new
        component on the theme in force (the ``agent`` one is the live
        column, restarted by its factory); the auto ids only ever move
        forward, so the replacement never collides with what it replaced.
        """
        self.index = index
        self.view = self.views[NAMES[index]](self.theme)
        self.status.text = self._label(index)
        if self.block_id is None or self.pane is None:
            return
        self.pane.document.remove(self.block_id)
        self.block_id = self.pane.document.add(self.content()).id
        self.pane.viewport.scroll_up(1 << 20)

    @staticmethod
    def _label(index: int) -> str:
        """The status row: the view on screen, and where the strip stands."""
        return f"view: {NAMES[index]} ({index + 1}/{len(NAMES)})"


def page(session: Showcase) -> PageBody:
    """The transcript, the inspector, and the wiring between them.

    The inspector is built with the session's own mode: on a real terminal
    its agent view opens empty and grows on the page beat; on a
    non-interactive path (the piped replay, ``--pages``) the stream is
    built finished, so the dump is whole however the strip was played with.
    The page's beat is the inspector's ``tick`` -- the content half of the
    live view -- while :meth:`Inspector.sync`, the page's once-per-event
    hook, keeps the mounted view exact.
    """
    theme = session.theme
    inspector = Inspector(theme, interactive=session.tui.interactive)
    return PageBody(
        [
            *header("workspace",
                    "A chat beside an inspector: the transcript scrolls on the left, "
                    "the tabs on the right switch one view at a time.", theme),
            try_line("click a tab on the right -- or press tab, then \u2190\u2192 -- to "
                     "switch the inspector's view", theme),
            section("the transcript", theme),
            Message("user", "Run the suite, then wire the aside into session.show().",
                    theme=theme),
            Message("thinking", "Plan: run pytest, read show()'s order, then open the "
                     "right pane after the blocks mount\u2026", theme=theme),
            ToolBlock("$ uv run pytest -q", TOOL_OUTPUT, tone="tool", footer="Took 4.6s",
                      theme=theme),
            EditBlock(
                "examples/showcase/session.py",
                context=["self.body = page.build(self)"],
                removed=["self.main.focus()"],
                added=["self._open_aside()", "self.main.focus()"],
                theme=theme,
            ),
            Message("assistant",
                    "Green. show() now closes the previous aside first, mounts the blocks, "
                    "then opens this page's pane -- and /split steps aside while it is open.",
                    theme=theme),
            api_note("PageBody.aside -> pane; PageBody.sync -> document.remove/add + "
                     "scroll_up", theme),
        ],
        focus=FocusRing([inspector.strip]),
        hint="inspector tabs",
        aside=inspector.mount,
        sync=inspector.sync,
        tick=inspector.tick,
    )

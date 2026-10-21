"""The demo session: the shell, the browser state and the host loop.

:class:`Session` mounts the header/footer docks and the catalog | stage
split, owns the navigation state (section, topic, theme), and routes each
event through the same tiers a user's own host would mount:

    stats (counting only) -> global palette -> the topic's modal -> find
    -> scrollbar -> toasts -> selection gesture -> pointer -> focus ring
    -> the host's own keys

The focus ring is rebuilt per topic: ``[catalog, *topic targets]``.  The
first click focuses, the second activates (``FocusManager``'s policy), the
arrows and ``enter`` drive the focused leaf, and ``escape`` returns the
focus to the catalog.

**Picks are generic.**  After a round the session walks every mounted
component (containers included), reads each one's one-shot ``take_result()``
exactly once, writes the value to the footer inspector and hands the
topic's ``note`` hook a :class:`~motui.demo.model.Report`.  A topic reacts
to its own picks -- opening a dialog or palette, flipping a Markdown task
box, advancing a stream -- without the session naming a component class.
"""

from __future__ import annotations

from motui import (
    FocusManager,
    KeyEvent,
    MouseEvent,
    Pointer,
    Scrollbar,
    SelectionGesture,
    Text,
    Theme,
    Toasts,
    TUI,
)
from motui.app.commands import Command, CommandRegistry
from motui.app import CommandPalette, Find, Stats, Tooltip
from motui.core import (
    Document,
    FocusEvent,
    ScreenClipboard,
    Selection,
    extract,
)

from .assets import THEMES
from .model import Report, Section, Topic, TopicBody
from .registry import BY_KEY, SECTION_BY_KEY, SECTIONS, TOPICS, topics_for
from .shell import CATALOG_RATIOS, Header, mount_catalog, mount_footer, mount_header
from .stage import display, walk_objects

__all__ = ["Session"]

#: The topic animation beat, in seconds (interactive sessions only).
TICK = 0.12


class Session:
    """The demo session, mounted at construction."""

    def __init__(self, tui: TUI) -> None:
        self.tui = tui
        self.theme_index = 0
        self.tui.theme = self.theme  # the split separator follows the skin
        self.section_index = 0
        self.topic_key = TOPICS[0].key
        self.body: TopicBody | None = None
        self.last_pick = "-"
        self.stats: Stats | None = None
        self.header: Header | None = None
        self.catalog = None
        self.footer_bar = None
        self.footer_status = None
        self._stage_ids: list[str] = []
        self._modal_was_open = False
        self._palette_was_open = False
        self._in_show = False

        # The real frame: two docks outside the split, catalog | stage inside.
        # ``TUI.dock`` builds each dock's document around the placeholder
        # component; ``_mount_shell`` clears it and mounts the real shell on
        # every topic switch.  (W4b replaces this placeholder dance with the
        # App's document facade.)
        self.header_doc = self.tui.dock(Text(""), edge="top", size=1).document
        self.footer_doc = self.tui.dock(Text(""), edge="bottom", size=2).document
        self.catalog_pane, self.stage = self.tui.split(
            "vertical", ratios=CATALOG_RATIOS
        )
        self.stage.focus()

        # The tiers, mounted explicitly (the library never self-attaches).
        self.scrollbar = Scrollbar(self.tui, pane=self.stage.id, theme=self.theme)
        self.toasts = Toasts(self.tui, theme=self.theme)
        self.gesture = SelectionGesture(self.tui, on_end=self._copy_toast)
        self.clipboard = ScreenClipboard(self.tui.screen)
        self.find = Find(self.tui, theme=self.theme)
        self.commands = self._build_commands()
        self.palette = CommandPalette(
            self.tui, self.commands.options(), theme=self.theme, max_rows=10
        )
        self.ring = FocusManager(())
        self.pointer = Pointer(self.tui, ring=self.ring)
        self.tooltip = Tooltip(self.tui, self.pointer, theme=self.theme)
        self.tui.every(TICK, self._tick)
        self.show_topic(TOPICS[0].key, toast=False)
        self.tui.paint()

    # -- state ------------------------------------------------------------------

    @property
    def theme(self) -> Theme:
        """The current :data:`~motui.demo.assets.THEMES` variant."""
        return THEMES[self.theme_index][1]

    @property
    def theme_name(self) -> str:
        return THEMES[self.theme_index][0]

    @property
    def topic(self) -> Topic:
        return BY_KEY[self.topic_key]

    @property
    def section(self) -> Section:
        return SECTION_BY_KEY[self.topic.section]

    def _section_topics(self) -> tuple[Topic, ...]:
        return topics_for(self.topic.section)

    def focus_name(self) -> str:
        """The focused leaf's short name for the inspector."""
        target = self.ring.focused
        return "-" if target is None else type(target).__name__.lower()

    # -- navigation -------------------------------------------------------------

    def show(self, section: str | Section, topic: str | Topic) -> None:
        """Switch to ``section``/``topic`` (either keys or values)."""
        section_key = section.key if isinstance(section, Section) else section
        topic_key = topic.key if isinstance(topic, Topic) else topic
        candidate = BY_KEY[topic_key]
        if candidate.section != section_key:
            raise KeyError(f"{topic_key!r} is not in section {section_key!r}")
        self.show_topic(topic_key)

    def show_topic(self, key: str, *, toast: bool = True) -> None:
        """Mount the topic ``key``: clear the stage, build it, retarget the tiers."""
        topic = BY_KEY.get(key)
        if topic is None:
            raise KeyError(f"no topic named {key!r}")
        self.topic_key = key
        self.section_index = next(
            index for index, section in enumerate(SECTIONS) if section.key == topic.section
        )
        self._in_show = True
        try:
            self._clear_stage()
            self.body = topic.build(self)
            for block in self.body.blocks:
                self._stage_ids.append(self.stage.document.add(block).id)
            self._mount_shell()
            self._build_ring()
            self.stage.viewport.scroll_to(0)
            self.stage.focus()
            self.tui.set_title(f"motui \u00b7 {topic.section}/{topic.key}")
            self._update_status()
        finally:
            self._in_show = False
        if toast:
            self._toast(f"{self.section.title} \u00b7 {topic.title}")
        self.tui.refresh()

    def show_section(self, index: int) -> None:
        """Switch to section ``index`` (wrapping) and open its first topic."""
        section = SECTIONS[index % len(SECTIONS)]
        topics = topics_for(section)
        if topics:
            self.show_topic(topics[0].key)

    def next_topic(self, delta: int = 1) -> None:
        """Step the topic cursor within the current section (wrapping)."""
        topics = self._section_topics()
        if not topics:
            return
        current = next(
            (index for index, topic in enumerate(topics) if topic.key == self.topic_key),
            0,
        )
        self.show_topic(topics[(current + delta) % len(topics)].key)

    def next_section(self, delta: int = 1) -> None:
        self.show_section(self.section_index + delta)

    # -- theme ------------------------------------------------------------------

    def set_theme(self, index: int, *, toast: bool = True) -> None:
        """Switch themes; rebuild the shell and the topic on the new skin."""
        self.theme_index = index % len(THEMES)
        theme = self.theme
        self.tui.theme = theme
        self.find.set_theme(theme)
        self.scrollbar.detach()
        self.scrollbar = Scrollbar(self.tui, pane=self.stage.id, theme=theme)
        previous_toasts = self.toasts
        self.toasts = Toasts(self.tui, theme=theme)
        previous_toasts.detach()
        self.palette.detach()
        self.palette = CommandPalette(
            self.tui, self.commands.options(), theme=theme, max_rows=10
        )
        self._palette_was_open = False
        if self.stats is not None:
            self.stats.set_theme(theme)
        self.show_topic(self.topic_key, toast=False)
        if toast:
            self._toast(f"theme: {self.theme_name}")

    def toggle_stats(self) -> None:
        """``c-g``: mount or unmount the dev stats overlay."""
        if self.stats is None:
            self.stats = Stats(self.tui, pointer=self.pointer, theme=self.theme)
        else:
            self.stats.detach()
            self.stats = None
        self.tui.refresh()

    def open_palette(self) -> None:
        self.palette.open()

    def open_find(self) -> None:
        self.find.open()

    # -- the loop ---------------------------------------------------------------

    async def run(self, _tui: TUI) -> None:
        """The host loop: read, route, repaint -- until quit or end of input."""
        running = True
        while running:
            if not self.tui.interactive:
                # The replay outruns the pump: compose between events, or a
                # scripted click would hit-test the frame from two events ago.
                self.tui.paint()
            event = await self.tui.read_event()
            if event is None:
                break
            running = self._round(event)
            self._after_round()
        self.tui.exit()

    def _round(self, event) -> bool:
        """One event round's dispatch; ``False`` when the round asked to quit."""
        if isinstance(event, KeyEvent) and event.key == "c-c":
            return False  # the one quit gesture no modal outranks
        if isinstance(event, KeyEvent):
            self.stage.focus()  # find/reveal/scroll address the stage document
        if self.stats is not None and self.stats.handle(event):
            self.tui.refresh()
        if self.palette.is_open and self.palette.handle(event):
            return True
        modal = self._modal()
        if modal is not None:
            modal.handle(event)
            return True  # an open panel owns every event it sees
        if self.find.is_open and self.find.handle(event):
            return True
        if self.scrollbar.handle(event):
            return True
        if self.toasts.handle(event):
            return True
        # The pointer goes before the gesture: a press only remembers (False),
        # a drag motion drops the pending click (False), and a stationary
        # click's release is the pointer's to dispatch.  The gesture then sees
        # every press/motion/release it owns -- drags -- while a click never
        # starts a selection in the header dock.
        if self.pointer.handle(event):
            if isinstance(event, MouseEvent) and event.kind == "release":
                self.gesture.handle(event)  # close the zero-width press it anchored
            self.tui.refresh()
            return True
        if self.gesture.handle(event):
            return True
        if isinstance(event, FocusEvent):
            if not event.focused:
                self.pointer.clear()
            return True
        if not isinstance(event, KeyEvent):
            return True
        if self.ring.handle(event):
            return True
        return self._host_key(event.key)

    def _host_key(self, name: str) -> bool:
        """The keys the ring declined: navigation, overlays and quit."""
        if name == "tab":
            self.ring.focus_next()
        elif name == "escape":
            if self.catalog is not None:
                self.ring.focus(self.catalog)
            self._toast("focus: catalog")
        elif name == "c-n":
            self.next_topic(1)
        elif name == "c-p":
            self.next_topic(-1)
        elif name == "]":
            self.next_section(1)
        elif name == "[":
            self.next_section(-1)
        elif name in ("c-1", "c-2", "c-3", "c-4", "c-5", "c-6"):
            self.show_section(int(name[-1]) - 1)
        elif name in ("/", "c-k"):
            self.open_palette()
        elif name == "c-f":
            self.open_find()
        elif name == "c-t":
            self.set_theme(self.theme_index + 1)
        elif name == "c-g":
            self.toggle_stats()
        elif name == "space":
            self._toggle_focused()
        elif name == "q":
            return False
        return True

    def _after_round(self) -> None:
        """A round's own work, exactly once, whatever tier dispatched it."""
        if self._in_show:
            return
        self._follow_shell()
        self._read_picks()
        self._read_modal_result()
        self._read_palette_result()
        self._update_status()
        self.tui.refresh()

    # -- the shell follows the pointer -------------------------------------------

    def _follow_shell(self) -> None:
        """A header or catalog click lands on the section/topic it selected."""
        if self.header is not None and self.header.menu.index != self.section_index:
            self.show_section(self.header.menu.index)
            return
        topics = self._section_topics()
        if self.catalog is None or not topics:
            return
        index = self.catalog.index
        if 0 <= index < len(topics) and topics[index].key != self.topic_key:
            self.show_topic(topics[index].key)

    def _mount_shell(self) -> None:
        """Rebuild the three shell regions on the current theme and state."""
        self._clear_document(self.header_doc)
        self.header = mount_header(
            self.header_doc,
            theme=self.theme,
            sections=SECTIONS,
            index=self.section_index,
            theme_name=self.theme_name,
        )
        self._clear_document(self.footer_doc)
        self.footer_bar, self.footer_status = mount_footer(
            self.footer_doc,
            theme=self.theme,
            left=self._status_left(),
            right=self._status_right(),
        )
        self._clear_document(self.catalog_pane.document)
        topics = self._section_topics()
        index = next(
            (position for position, topic in enumerate(topics) if topic.key == self.topic_key),
            0,
        )
        self.catalog = mount_catalog(
            self.catalog_pane.document,
            theme=self.theme,
            topics=topics,
            index=index,
        )

    def _build_ring(self) -> None:
        """The ring is the catalog plus the topic's own targets, in that order."""
        targets = [] if self.catalog is None else [self.catalog]
        if self.body is not None and self.body.focus is not None:
            targets.extend(self.body.focus.targets)
        self.ring = FocusManager(targets)
        if self.body is not None and self.body.focus is not None and self.body.focus.targets:
            self.ring.focus(self.body.focus.targets[0])
        elif self.catalog is not None:
            self.ring.focus(self.catalog)
        self._retarget_pointer()

    def _retarget_pointer(self) -> None:
        self.pointer.detach()
        self.tooltip.detach()
        self.pointer = Pointer(self.tui, ring=self.ring)
        self.tooltip = Tooltip(self.tui, self.pointer, theme=self.theme)
        if self.stats is not None:
            self.stats.pointer = self.pointer

    def _clear_stage(self) -> None:
        """Detach the old body's overlays and remove its blocks."""
        body = self.body
        if body is not None:
            for controller in body.overlays:
                close = getattr(controller, "close", None)
                if close is not None:
                    close()
                detach = getattr(controller, "detach", None)
                if detach is not None:
                    detach()
            if body.leave is not None:
                body.leave(self)
        self.body = None
        for block_id in self._stage_ids:
            try:
                self.stage.document.remove(block_id)
            except KeyError:
                pass
        self._stage_ids = []
        self._modal_was_open = False
        if self.find.is_open:
            self.find.close()
        if self.palette.is_open:
            self.palette.close()

    @staticmethod
    def _clear_document(document: Document) -> None:
        for block in tuple(document.blocks()):
            document.remove(block.id)

    # -- picks ------------------------------------------------------------------

    def _read_picks(self) -> None:
        """Read every mounted component's one-shot result, once, in mount order."""
        body = self.body
        if body is None:
            return
        seen: set[int] = set()
        for block in body.blocks:
            for component in walk_objects(block):
                if id(component) in seen:
                    continue
                seen.add(id(component))
                take = getattr(component, "take_result", None)
                if take is None:
                    continue
                value = take()
                if value is None:
                    continue
                self._report(Report(component, value))

    def _report(self, report: Report) -> None:
        self.last_pick = display(report.value)
        body = self.body
        if body is not None and body.note is not None:
            body.note(report)

    def _read_modal_result(self) -> None:
        body = self.body
        modal = None if body is None else body.modal
        open_now = bool(modal is not None and getattr(modal, "is_open", False))
        if self._modal_was_open and not open_now and modal is not None:
            value = modal.take_result()
            self._report(Report(modal, "closed" if value is None else value))
            modal = None if body is None else body.modal
            open_now = bool(modal is not None and getattr(modal, "is_open", False))
        self._modal_was_open = open_now

    def _read_palette_result(self) -> None:
        if self.palette.is_open:
            self._palette_was_open = True
            return
        if not self._palette_was_open:
            return
        self._palette_was_open = False
        command = self.palette.take_result()
        if command is None:
            self._toast("palette closed")
            return
        name = getattr(command, "name", None)
        if name is not None:
            self.last_pick = name
            self.commands.invoke(name)

    def _modal(self):
        body = self.body
        modal = None if body is None else body.modal
        if modal is not None and getattr(modal, "is_open", False):
            return modal
        return None

    def _toggle_focused(self) -> bool:
        target = self.ring.focused
        toggle = None if target is None else getattr(target, "toggle", None)
        if toggle is None:
            return False
        toggle()
        return True

    # -- the shell's own data ----------------------------------------------------

    def _build_commands(self) -> CommandRegistry:
        """One palette command per topic, named ``Section · Title``."""
        registry = CommandRegistry()
        for topic in TOPICS:
            section = SECTION_BY_KEY[topic.section]
            registry.add(
                Command(
                    topic.command_name(section.title),
                    topic.group,
                    handler=lambda key=topic.key: self.show_topic(key),
                )
            )
        return registry

    def _status_left(self) -> str:
        return (
            f"theme {self.theme_name} \u00b7 focus {self.focus_name()} "
            f"\u00b7 last {self.last_pick}"
        )

    def _status_right(self) -> str:
        topic = BY_KEY[self.topic_key]
        return f"{topic.section}/{topic.key}"

    def _update_status(self) -> None:
        if self.footer_status is None:
            return
        self.footer_status.left = (self._status_left(),)
        self.footer_status.right = (self._status_right(),)

    def _toast(self, text: str) -> None:
        self.toasts.show(text, style=self.theme.overlays.toast)

    def _tick(self) -> None:
        if self.body is not None and self.body.tick is not None:
            self.body.tick()
            self.tui.refresh()

    # -- copy -------------------------------------------------------------------

    def _copy_toast(self, tui: TUI, selection: Selection) -> None:
        """The gesture's ``on_end``: extract the range and copy it."""
        pane = tui.selection_pane or tui.frame.focused_pane
        if pane is None:
            return
        region = tui.frame.region(pane.id)
        width = tui.screen.width if region is None else region.width
        text = extract(pane.document, selection, width=width)
        if self.clipboard.copy(text):
            self.toasts.show(
                f"copied {len(text.splitlines())} lines", style=self.theme.overlays.toast
            )

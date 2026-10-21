"""The demo session: the shell, the browser state and the App subclass.

The App owns the driver and the default tiers; the session adds the frame,
the browser state, navigation, the stage ``Scrollbar``/``Stats`` controllers
and the per-round pick scan.  The ring is rebuilt per topic as
``[catalog, *topic targets]``, the topic's first target focused."""

from __future__ import annotations

from motui import KeyEvent, Scrollbar, Text, Theme
from motui.app import App, Stats
from motui.app.commands import Command, CommandRegistry
from motui.core import FocusEvent, ScreenClipboard, Selection, extract

from .assets import THEMES
from .model import Report, Section, Topic, TopicBody
from .registry import BY_KEY, SECTION_BY_KEY, SECTIONS, TOPICS, topics_for
from .shell import CATALOG_RATIOS, Header, follow_shell, mount_shell, refresh_status
from .stage import display, walk_objects

__all__ = ["Session"]
TICK = 0.12  # the topic animation beat, in seconds (interactive sessions only)


class Session(App):
    """The demo session: an App plus the browser's shell and navigation."""

    def __init__(self, *, theme: Theme | None = None, **options: object) -> None:
        options.setdefault("on_selection", self._copy_toast)
        super().__init__(theme=THEMES[0][1] if theme is None else theme, **options)
        self.theme_index = self.section_index = 0
        self.topic_key = TOPICS[0].key
        self.body: TopicBody | None = None
        self.last_pick = "-"
        self.stats: Stats | None = None
        self.header: Header | None = None
        self.catalog = self.footer_bar = self.footer_status = None
        self._stage_ids: list[str] = []
        self._modal_was_open = self._palette_was_open = self._in_show = False
        # The frame: two docks outside the split, catalog | stage inside.
        self.dock(Text(""), edge="top", size=1)
        self.dock(Text(""), edge="bottom", size=2)
        self.catalog_pane, self.stage = self.split("vertical", ratios=CATALOG_RATIOS)
        self.stage.focus()
        self.scrollbar = Scrollbar(self.tui, pane=self.stage.id, theme=self.theme)
        self.mount(self.scrollbar)
        self.clipboard = ScreenClipboard(self.tui.screen)
        self.commands = self._build_commands()
        self.tui.every(TICK, self._tick)
        self.show_topic(TOPICS[0].key, toast=False)
        self.tui.paint()

    def show(self, section: "str | Section", topic: "str | Topic") -> None:
        """Switch to ``section``/``topic`` (either keys or values)."""
        section_key = section.key if isinstance(section, Section) else section
        topic_key = topic.key if isinstance(topic, Topic) else topic
        if BY_KEY[topic_key].section != section_key:
            raise KeyError(f"{topic_key!r} is not in section {section_key!r}")
        self.show_topic(topic_key)

    def show_topic(self, key: str, *, toast: bool = True) -> None:
        """Mount ``key``: clear the stage, build it, rebuild the shell and ring."""
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
                self._stage_ids.append(self.add(block, pane=self.stage))
            mount_shell(self)
            self._build_ring()
            self.stage.viewport.scroll_to(0)
            self.stage.focus()
            self.tui.set_title(f"motui \u00b7 {topic.section}/{topic.key}")
            refresh_status(self)
        finally:
            self._in_show = False
        if toast:
            self._toast(f"{SECTION_BY_KEY[topic.section].title} \u00b7 {topic.title}")
        self.tui.refresh()

    def show_section(self, index: int) -> None:
        """Switch to section ``index`` (wrapping) and open its first topic."""
        topics = topics_for(SECTIONS[index % len(SECTIONS)])
        if topics:
            self.show_topic(topics[0].key)

    def next_topic(self, delta: int = 1) -> None:
        """Step the topic cursor within the current section (wrapping)."""
        topics = topics_for(BY_KEY[self.topic_key].section)
        if topics:
            current = next((i for i, t in enumerate(topics) if t.key == self.topic_key), 0)
            self.show_topic(topics[(current + delta) % len(topics)].key)

    def set_theme(self, index: int, *, toast: bool = True) -> None:
        """Switch themes; the App re-skins its overlays, the shell rebuilds."""
        self.theme_index = index % len(THEMES)
        self.theme = THEMES[self.theme_index][1]
        self.scrollbar.set_theme(self.theme)
        if self.stats is not None:
            self.stats.set_theme(self.theme)
        self._palette_was_open = False
        self.show_topic(self.topic_key, toast=False)
        if toast:
            self._toast(f"theme: {THEMES[self.theme_index][0]}")

    def toggle_stats(self) -> None:
        """``c-g``: mount or unmount the dev stats overlay."""
        if self.stats is None:
            self.stats = Stats(self.tui, pointer=self.pointer, theme=self.theme)
            self.mount(self.stats, dispatch=False)  # the session feeds it itself
        else:
            self.unmount(self.stats)
            self.stats.detach()
            self.stats = None
        self.tui.refresh()

    def dispatch(self, event) -> bool:
        """The demo's pre-tiers, then the App's tiers, then the round's picks."""
        if isinstance(event, KeyEvent) and event.key == "c-c":
            self.quit()  # the one quit gesture no modal outranks
            return True
        if isinstance(event, KeyEvent):
            self.stage.focus()  # find/reveal address the stage document
        if self.stats is not None:
            self.stats.handle(event)  # a repaint cue, never a claim
        body = self.body
        modal = None if body is None else body.modal
        if modal is not None and getattr(modal, "is_open", False):
            modal.handle(event)  # a topic's own blocking panel owns every event
            self._after_round()
            return True
        consumed = super().dispatch(event)
        self._after_round()
        return consumed

    def on_key(self, event: KeyEvent) -> bool:
        """The keys the App tiers declined: navigation, overlays and quit."""
        name = event.key
        if name == "escape":
            if self.catalog is not None:
                self.focus(self.catalog)
            self._toast("focus: catalog")
        elif name == "space":
            manager = self.focus_manager
            target = None if manager is None else manager.focused
            toggle = None if target is None else getattr(target, "toggle", None)
            if toggle is not None:
                toggle()
        elif name == "q":
            self.quit()
        elif name in ("c-1", "c-2", "c-3", "c-4", "c-5", "c-6"):
            self.show_section(int(name[-1]) - 1)
        elif name in ("c-n", "c-p"):
            self.next_topic(1 if name == "c-n" else -1)
        elif name in ("]", "["):
            self.show_section(self.section_index + (1 if name == "]" else -1))
        elif name in ("/", "c-k"):
            super().open_palette(self.commands.options(), max_rows=10)
        elif name == "c-f":
            self.find()
        elif name == "c-t":
            self.set_theme(self.theme_index + 1)
        elif name == "c-g":
            self.toggle_stats()
        return True

    def on_event(self, event) -> bool:
        """The lost-focus scrub: drop the hover the pointer can no longer see."""
        if isinstance(event, FocusEvent):
            if not event.focused and self.pointer is not None:
                self.pointer.clear()
            return True
        return False

    def _after_round(self) -> None:
        """A round's own work, exactly once, whatever tier dispatched it."""
        if self._in_show:
            return
        follow_shell(self)
        self._read_picks()
        self._read_modal_result()
        self._read_palette_result()
        refresh_status(self)
        self.tui.refresh()

    def _build_ring(self) -> None:
        targets = [] if self.catalog is None else [self.catalog]
        body_targets: tuple = ()
        if self.body is not None and self.body.focus is not None:
            body_targets = self.body.focus.targets
            targets.extend(body_targets)
        self.set_focus_targets(targets)
        manager = self.focus_manager
        if manager is not None:
            if body_targets:
                manager.focus(body_targets[0])  # the topic's first target, not the catalog
            elif self.catalog is not None:
                manager.focus(self.catalog)

    def _clear_stage(self) -> None:
        body = self.body
        if body is not None:
            for controller in body.overlays:
                for name in ("close", "detach"):
                    method = getattr(controller, name, None)
                    if method is not None:
                        method()
            if body.leave is not None:
                body.leave(self)
        self.body = None
        for block_id in self._stage_ids:
            try:
                self.remove(block_id)
            except KeyError:
                pass
        self._stage_ids = []
        self._modal_was_open = False
        for overlay in (self.find_bar, self.palette):
            if overlay is not None and overlay.is_open:
                overlay.close()

    def _read_picks(self) -> None:
        """Read every mounted component's one-shot result, once, in mount order."""
        body = self.body
        if body is None:
            return
        seen: set[int] = set()
        for block in body.blocks:
            for component in walk_objects(block):
                take = getattr(component, "take_result", None)
                if take is None or id(component) in seen:
                    continue
                seen.add(id(component))
                if (value := take()) is not None:
                    self.last_pick = display(value)
                    if body.note is not None:
                        body.note(Report(component, value))

    def _read_modal_result(self) -> None:
        body = self.body
        modal = None if body is None else body.modal
        open_now = bool(modal is not None and getattr(modal, "is_open", False))
        if self._modal_was_open and not open_now and modal is not None:
            value = modal.take_result()
            self.last_pick = display("closed" if value is None else value)
            if body is not None and body.note is not None:
                body.note(Report(modal, "closed" if value is None else value))
            modal = None if body is None else body.modal
            open_now = bool(modal is not None and getattr(modal, "is_open", False))
        self._modal_was_open = open_now
    def _read_palette_result(self) -> None:
        palette = self.palette
        if palette is None:
            return
        if palette.is_open:
            self._palette_was_open = True
            return
        if not self._palette_was_open:
            return
        self._palette_was_open = False
        command = palette.take_result()
        if command is None:
            self._toast("palette closed")
            return
        name = getattr(command, "name", None)
        if name is not None:
            self.last_pick = name
            self.commands.invoke(name)

    def _build_commands(self) -> CommandRegistry:
        registry = CommandRegistry()
        for topic in TOPICS:
            section = SECTION_BY_KEY[topic.section]
            registry.add(Command(
                topic.command_name(section.title), topic.group,
                handler=lambda key=topic.key: self.show_topic(key),
            ))
        return registry
    def _toast(self, text: str) -> None:
        self.toast(text, style=self.theme.overlays.toast)
    def _tick(self) -> None:
        if self.body is not None and self.body.tick is not None:
            self.body.tick()
            self.tui.refresh()
    def _copy_toast(self, tui, selection: Selection) -> None:
        pane = tui.selection_pane or tui.frame.focused_pane
        if pane is None:
            return
        region = tui.frame.region(pane.id)
        width = tui.screen.width if region is None else region.width
        text = extract(pane.document, selection, width=width)
        if self.clipboard.copy(text):
            self._toast(f"copied {len(text.splitlines())} lines")

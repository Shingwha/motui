"""The demo's value model: sections, topics, reports and the built body.

A **section** is one top-level group of the browser (``overview``,
``components``, ...).  A **topic** is one screen of the detail pane: a value
that names itself, describes itself in one line, declares the components it
shows, and knows how to build its live body.  The registry owns the order;
this module owns the shapes.

``TopicBody`` is what a topic builder answers: the blocks to mount, the
focus targets, the optional modal controller, the optional tick hook, and
the report/enter/leave hooks.  ``Report`` is one one-shot value read from a
component (``take_result()``), handed to the topic's ``note`` hook.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Sequence

from motui.kernel import Component

if TYPE_CHECKING:  # pragma: no cover - the imports are type-only by design
    from motui.app import FocusManager

    from .session import Session

__all__ = ["Report", "Section", "Topic", "TopicBody"]


@dataclass(frozen=True, slots=True)
class Section:
    """One top-level section: its key and the label the header shows."""

    key: str
    title: str


@dataclass(frozen=True, slots=True)
class Topic:
    """One detail screen: the value the catalog, palette and replay share.

    ``key`` is globally unique and is the last path segment of the golden
    file name (``<section>--<key>.txt``); ``group`` is the catalog's group
    label and must form contiguous runs in registry order.  ``components``
    names the public classes this topic puts on screen -- the coverage test
    reads it, so it is part of the topic's contract, not documentation.
    """

    key: str
    title: str
    summary: str
    group: str
    section: str
    build: Callable[["Session"], TopicBody] = field(compare=False)
    try_line: str = ""
    api_line: str = ""
    components: tuple[str, ...] = ()

    def command_name(self, section_title: str) -> str:
        """The palette's label: ``"Components · Select"``."""
        return f"{section_title} \u00b7 {self.title}"


@dataclass(frozen=True, slots=True)
class Report:
    """One value read from a component's ``take_result()`` door."""

    source: object
    value: object


@dataclass
class TopicBody:
    """One built topic: what the session mounts and what hooks it runs.

    ``overlays`` lists every controller the topic registered on the frame
    (``Modal``, ``CommandPalette``, ...), so a topic switch can detach them; a
    closed modal still owns its overlay registration for the frame's life
    otherwise.
    """

    blocks: Sequence[Component]
    focus: "FocusManager | None" = None
    modal: object | None = None
    tick: Callable[[], None] | None = None
    note: Callable[[Report], None] | None = None
    enter: Callable[["Session"], None] | None = None
    leave: Callable[["Session"], None] | None = None
    overlays: tuple[object, ...] = ()

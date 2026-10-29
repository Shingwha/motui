"""Form: labelled fields, navigation, validation and one-shot submission.

A form stacks :class:`Field` components with optional labels, mirrors the
cursor onto their ``focused`` flags, validates on activate and leaves a
``{name: value}`` mapping pending.  ``child_at`` descends into fields.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ..kernel.cell import Line, Surface
from ..kernel.document import Component
from ..kernel.events import Event, KeyEvent, MouseEvent, PasteEvent
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.text import WrapMode
from ..kernel.theme import Styles, Theme
from ..widgets.base import CursorWidget

__all__ = ["Field", "Form"]


@dataclass
class Field:
    """One form field: a component plus its name, label and hooks.

    ``validate`` returns an error string or ``None`` and the form stores it
    in ``error``; ``value`` overrides the component's own extractor.
    """

    name: str
    component: Component
    label: str = ""
    validate: Callable[[object], str | None] | None = None
    value: Callable[[], object] | None = None
    error: str | None = None



class Form(CursorWidget):
    """A vertical stack of fields with focus, validation and a submit result.

    ``index`` walks the fields and is mirrored onto their ``focused`` flags.
    Values come from ``Field.value`` or the component's ``value``/``text``/
    ``checked``/``selected``/``marked``; ``take()`` is never called.
    ``activate`` validates every field, writes errors back and emits the
    mapping (or returns ``False``).  An empty form submits ``{}``.
    """

    __slots__ = (
        "_fields",
        "_gap",
        "_on_submit",
        "_spans",
    )

    #: The form owns its fields' focus: App registers the form, not each
    #: field, and every field's keys route through :meth:`on_key`.
    focus_scope = True

    def __init__(
        self,
        fields: Sequence[Field],
        *,
        gap: int = 0,
        index: int = 0,
        on_submit: Callable[[dict[str, object]], object] | None = None,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self._fields = tuple(fields)
        # The explicit tree: each field's component is this form's child, so
        # ``walk()`` covers the fields without guessing ``_fields``.
        self.children = [field.component for field in self._fields]
        self._gap = max(0, gap)
        self._on_submit = on_submit
        #: The last render's component-row geometry: ``(start_row, count)``
        #: per field, in field order.
        self._spans: list[tuple[int, int]] = []
        # The constructor's index is installed directly: construction moves
        # nothing and writes no result (the W4b precedent).
        self._sync_cursor()
        self._cursor.index = (
            max(0, min(index, len(self._fields) - 1)) if self._fields else 0
        )
        self._sync_focus()

    # -- cursor hooks ------------------------------------------------------------

    def _entry_count(self) -> int:
        return len(self._fields)

    def _entry_at(self, index: int) -> object | None:
        return self._fields[index]

    def _cursor_enabled(self) -> bool:
        return True

    def _cursor_wraps(self) -> bool:
        return False

    # -- state ------------------------------------------------------------------

    @property
    def fields(self) -> tuple[Field, ...]:
        """The fields in form order (the tuple the form was built with)."""
        return self._fields

    def _sync_focus(self) -> None:
        """Mirror ``index`` onto every focusable field."""
        current = self.index
        for position, field in enumerate(self._fields):
            component = field.component
            if getattr(component, "focusable", False):
                component.focused = position == current

    def focus(self, target: int | str) -> bool:
        """Focus a field by position or name; ``True`` when the focus moved.

        Unknown names, out-of-range positions and the current field answer
        ``False``.
        """
        if isinstance(target, str):
            position = next(
                (i for i, field in enumerate(self._fields) if field.name == target),
                None,
            )
            if position is None:
                return False
        else:
            position = int(target)
            if not 0 <= position < len(self._fields):
                return False
        return self.select(position)

    def select(self, index: int) -> bool:
        """Place the field cursor on ``index`` and mirror the focus flags."""
        changed = super().select(index)
        self._sync_focus()
        return changed

    def move(self, delta: int) -> bool:
        """Move the field cursor ``delta`` places and mirror the focus flags."""
        changed = super().move(delta)
        self._sync_focus()
        return changed

    # -- events -----------------------------------------------------------------

    @staticmethod
    def _event_handler(component: Component, event: Event):
        """The typed hook one child answers ``event`` with, or ``None``.

        Keys go to ``on_key``, pastes to ``on_paste``, mouse to ``on_mouse``.
        """
        hook = None
        if isinstance(event, KeyEvent):
            hook = getattr(component, "on_key", None)
        elif isinstance(event, PasteEvent):
            hook = getattr(component, "on_paste", None)
        elif isinstance(event, MouseEvent):
            hook = getattr(component, "on_mouse", None)
        return hook if callable(hook) else None

    def on_key(self, event: Event) -> bool:
        """Route one event; ``True`` when the form consumed it.

        The focused field's typed hook wins; then tab/down and s-tab/up move
        (True only on a real move) and ``enter`` activates and is consumed.
        """
        if not self._fields:
            return False
        component = self._fields[self.index].component
        handler = self._event_handler(component, event)
        if handler is not None and handler(event):
            return True
        if not isinstance(event, KeyEvent) or event.kind == "release":
            return False
        key = event.key
        if key in ("tab", "down"):
            return self.move(1)
        if key in ("s-tab", "up"):
            return self.move(-1)
        if key == "enter":
            self.activate()
            return True
        return False

    def on_focus(self, gained: bool) -> None:
        """Take or lose focus, mirroring it onto the fields (losing clears all)."""
        self.focused = gained
        if gained:
            self._sync_focus()
            return
        for field in self._fields:
            component = field.component
            if getattr(component, "focusable", False):
                component.focused = False

    # -- values and submission ----------------------------------------------------

    @staticmethod
    def _value(field: Field) -> object:
        """Extract a field's value: its hook first, then the component's state.

        The fallback order is ``value``/``text``/``checked``/``selected``/
        ``marked`` (callables are called); ``take()`` is never consulted.
        """
        if field.value is not None:
            return field.value()
        component = field.component
        for name in ("value", "text", "checked", "selected", "marked"):
            if hasattr(component, name):
                attribute = getattr(component, name)
                return attribute() if callable(attribute) else attribute
        return None

    def activate(self) -> bool:
        """Validate every field and submit: the form's one action.

        Errors are written back; any error clears the result and answers
        ``False``.  Success emits ``{name: value}`` and calls ``on_submit``.
        """
        values: dict[str, object] = {}
        failed = False
        for field in self._fields:
            value = self._value(field)
            values[field.name] = value
            error = field.validate(value) if field.validate is not None else None
            field.error = error
            if error is not None:
                failed = True
        self.touch()  # the errors are row inputs; the fields are not widgets
        if failed:
            self._clear_result()
            return False
        self._emit(values)
        if self._on_submit is not None:
            self._on_submit(values)
        return True

    # -- rendering ----------------------------------------------------------------

    def render(self, c: Constraints) -> Surface:
        """Stack label, component and error rows per field, with gaps between.

        The untruncated component-row spans feed ``child_at``; ``max_height``
        truncates only the returned rows.
        """
        width = c.width
        label_style = self.group("content").accent
        error_style = self.group("status").danger
        out: list[Line] = []
        spans: list[tuple[int, int]] = []
        for position, field in enumerate(self._fields):
            if position and self._gap:
                out.extend(Line() for _ in range(self._gap))
            if field.label:
                out.append(Line.from_text(field.label, label_style).clip(WrapMode.ELLIPSIS, width))
            rows = list(field.component.render(Constraints(width=width)))
            spans.append((len(out), len(rows)))
            out.extend(row.clip(WrapMode.ELLIPSIS, width) for row in rows)
            if field.error:
                out.append(Line.from_text(field.error, error_style).clip(WrapMode.ELLIPSIS, width))
        self._spans = spans
        if c.max_height is not None:
            out = out[: c.max_height]
        return Surface.clipped(out, c.width)

    def _field_at(self, row: int, col: int) -> tuple[int, int] | None:
        """The ``(field position, local row)`` owning a rendered cell, or ``None``."""
        if row < 0 or col < 0:
            return None
        for position, (start, count) in enumerate(self._spans):
            if start <= row < start + count:
                return position, row - start
        return None

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """Map a rendered component row to its field's component.

        Label rows, error rows, gaps and every cell outside the painting
        answer ``None``; the geometry is the last :meth:`render`'s.
        """
        hit = self._field_at(row, col)
        if hit is None:
            return None
        position, local = hit
        return self._fields[position].component, local, col

    def focus_at(self, row: int, col: int) -> bool:
        """Move the form's field cursor onto the field under a cell.

        This is the focus half of a click: the leaf (the field's own input)
        still gets its ``click``, while the form updates :attr:`index` and
        the fields' focused flags.  A label, an error row, a gap or a blank
        cell belongs to the form and answers ``False``.
        """
        hit = self._field_at(row, col)
        if hit is None:
            return False
        position, _local = hit
        self.select(position)
        return True

    def on_click(self, pos: Pos) -> bool:
        """Focus the field under a rendered cell and forward the click to it.

        A direct host click keeps its one-gesture meaning: move the field
        cursor, then hand the field-local cell to the field component's own
        ``on_click``.  The focus tier uses :meth:`focus_at` beside the
        leaf's own click instead, so the action is never applied twice.
        """
        hit = self._field_at(pos.y, pos.x)
        if hit is None:
            return False
        position, local = hit
        self.focus_at(pos.y, pos.x)
        hook = getattr(self._fields[position].component, "on_click", None)
        if hook is not None:
            hook(Pos(y=local, x=pos.x))
        return True

    def __repr__(self) -> str:
        return (
            f"Form({len(self._fields)} fields, index={self.index}, "
            f"gap={self._gap})"
        )

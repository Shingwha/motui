"""Form: labelled fields, navigation, validation and one-shot submission.

A :class:`Form` composes ordinary components into a vertical form.  Each
:class:`Field` pairs a component with a name, an optional label and two
hooks: ``validate(value) -> str | None`` for the submit check and
``value() -> object`` for a custom extractor.  Without an extractor the
value comes from the component's own state by duck typing -- the first of
``value``, ``text``, ``checked``, ``selected`` or ``marked`` that the
component exposes (a callable attribute is called).  ``take()`` is
never touched: reading a field must not consume its pending result.

Rendering is one vertical stack per field -- an optional label row, the
component's rows at the form width, and an error row after a failed
submit -- with ``gap`` blank rows between fields.  Every row is fitted to
the painting width, and the geometry of the last render feeds
``child_at`` so a host's hit test descends into the field component.

Focus is the form's own: :meth:`Form.focus` and :meth:`Form.move` track
``index`` and mirror it onto every focusable
field (the new one ``True``, all others ``False``).  The keyboard routes
the focused field first -- its own typed hook wins over navigation -- then
``tab``/``down`` step forward, ``s-tab``/``up`` step back and ``enter``
runs :meth:`Form.on_action`: validate every field, write each error back to
its :class:`Field`, and on success leave ``{name: value}`` pending for
:meth:`Form.take` and call ``on_submit`` once.  Navigation answers
``True`` only when the index moved, so a host keeps Tab at the ends.
``focus_scope`` says the form routes its subtree's focus itself.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ..kernel.document import Component
from ..kernel.events import Event, KeyEvent, MouseEvent, PasteEvent
from ..kernel.cell import Line, Surface
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.theme import Styles, Theme
from ..kernel.text import WrapMode
from ..widgets.base import Widget

__all__ = ["Field", "Form"]


@dataclass
class Field:
    """One form field: a component plus its name, label and hooks.

    ``validate`` receives the extracted value and answers an error string
    (``None`` when valid); :class:`Form` stores the answer back in
    ``error``.  ``value``, when given, is the extractor and wins over the
    component's own attributes.  ``error`` is form-managed state -- a host
    may read it after a failed submit and clear it by editing the field.
    """

    name: str
    component: Component
    label: str = ""
    validate: Callable[[object], str | None] | None = None
    value: Callable[[], object] | None = None
    error: str | None = None


def _child_key(component: Component) -> object:
    """A field component's revision when it has one, else its identity."""
    revision = getattr(component, "revision", None)
    if revision is not None:
        snapshot = revision()
        if snapshot is not None:
            return ("revision", snapshot)
    return id(component)


class Form(Widget):
    """A vertical stack of fields with focus, validation and a submit result.

    ``fields`` is copied to a tuple at construction; the :class:`Field`
    values stay live, because ``error`` is form-managed.  ``index`` starts
    at the requested field (clamped; ``0`` for an empty form) and is
    read-only -- move it with :meth:`focus` or :meth:`move`, which also
    mirror the position onto the fields' ``focused`` flags.  A form
    without fields consumes nothing and submits an empty mapping when
    activated directly.
    """

    __slots__ = (
        "_fields",
        "_gap",
        "_index",
        "_on_submit",
        "_pending",
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
        self._index = max(0, min(index, len(self._fields) - 1)) if self._fields else 0
        self._on_submit = on_submit
        self._pending: dict[str, object] | None = None
        #: The last render's component-row geometry: ``(start_row, count)``
        #: per field, in field order.
        self._spans: list[tuple[int, int]] = []
        self._sync_focus()

    # -- state ------------------------------------------------------------------

    @property
    def index(self) -> int:
        """The focused field's position."""
        return self._index

    @property
    def fields(self) -> tuple[Field, ...]:
        """The fields in form order (the tuple the form was built with)."""
        return self._fields

    def _sync_focus(self) -> None:
        """Mirror ``index`` onto every focusable field."""
        for position, field in enumerate(self._fields):
            component = field.component
            if getattr(component, "focusable", False):
                component.focused = position == self._index

    def focus(self, target: int | str) -> bool:
        """Focus a field by position or name; ``True`` when the focus moved.

        An unknown name or an out-of-range position answers ``False`` and
        moves nothing; focusing the current field answers ``False`` too
        (nothing changed), like :meth:`~motui.app.focus.FocusManager.focus`.
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
        if position == self._index:
            return False
        self._index = position
        self._sync_focus()
        return True

    def move(self, delta: int) -> bool:
        """Move the focused field ``delta`` places, clamped; ``True`` when it moved."""
        if not self._fields or delta == 0:
            return False
        target = max(0, min(self._index + delta, len(self._fields) - 1))
        if target == self._index:
            return False
        self._index = target
        self._sync_focus()
        return True

    # -- events -----------------------------------------------------------------

    @staticmethod
    def _event_handler(component: Component, event: Event):
        """The typed hook one child answers ``event`` with, or ``None``.

        The tree routes by event kind: a key goes to ``on_key``, a paste to
        ``on_paste`` and a mouse report to ``on_mouse``.  ``None`` means the
        component takes no events.
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

        The focused field's own typed hook goes first (a controller keeps
        its keys -- including a ``PasteEvent``, which the field's own paste
        hook consumes).  Then the form's navigation: ``tab``/``down``
        and ``s-tab``/``up`` move the field cursor and answer ``True`` only
        on a real move, so the ends hand Tab back to the host; ``enter``
        activates the form and is always consumed (a validation failure is
        still the form's answer -- the errors are now on screen).
        """
        if not self._fields:
            return False
        component = self._fields[self._index].component
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
            self.on_action("activate")
            return True
        return False

    def on_focus(self, gained: bool) -> None:
        """Take or lose the form focus, mirroring it onto the fields.

        Gaining re-applies the cursor's field ``focused`` flag (the flags
        can have been cleared while the form was out of the ring); losing
        clears every field's flag, so no field keeps a stale caret after
        the form left the ring.
        """
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

        The attribute fallback is the read-only duck-typing order
        ``value``, ``text``, ``checked``, ``selected``, ``marked``; a
        callable attribute is called.  A field with none of them answers
        ``None``.  ``take()`` is deliberately not consulted.
        """
        if field.value is not None:
            return field.value()
        component = field.component
        for name in ("value", "text", "checked", "selected", "marked"):
            if hasattr(component, name):
                attribute = getattr(component, name)
                return attribute() if callable(attribute) else attribute
        return None

    def on_action(self, name: str) -> bool:
        """Run the form's one action (``"activate"``): validate and submit.

        Each field's error is written back (``None`` clears it).  Any
        error answers ``False`` and leaves nothing pending.  Otherwise the
        ``{name: value}`` mapping becomes the one-shot result and
        ``on_submit`` runs once, with the same mapping.  Other names decline.
        """
        if name != "activate":
            return False
        self._pending = None
        values: dict[str, object] = {}
        failed = False
        for field in self._fields:
            value = self._value(field)
            values[field.name] = value
            error = field.validate(value) if field.validate is not None else None
            field.error = error
            if error is not None:
                failed = True
        if failed:
            return False
        self._pending = values
        if self._on_submit is not None:
            self._on_submit(values)
        return True

    def take(self) -> dict[str, object] | None:
        """Read the submitted mapping once and clear it."""
        result = self._pending
        self._pending = None
        return result

    # -- rendering ----------------------------------------------------------------

    def render(self, c: Constraints) -> Surface:
        """Stack label, component and error rows per field, with gaps between.

        The label and error styles are the theme's ``content.accent`` and
        ``status.danger`` read on every call, so a rethemed form repaints.
        The field components render at the constraint's width.  ``_spans`` records the untruncated
        component-row geometry :meth:`child_at` maps through (the W2a
        container precedent), while a ``max_height`` budget truncates only
        the returned rows.  The surface is clipped, not padded.
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
        if position != self._index:
            self._index = position
            self._sync_focus()
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

    def revision(self) -> object:
        """The row cache's snapshot: field identity, label, error and child state.

        Each field contributes its name, label, current error and the
        child's own snapshot (identity when it has none); the gap, the
        focused index and the theme/``Styles`` complete the inputs the rows
        read.
        """
        fields = tuple(
            (
                field.name,
                field.label,
                field.error,
                field.value,
                _child_key(field.component),
            )
            for field in self._fields
        )
        return (fields, self._gap, self._index, self.theme, self.styles)

    def __repr__(self) -> str:
        return (
            f"Form({len(self._fields)} fields, index={self._index}, "
            f"gap={self._gap})"
        )

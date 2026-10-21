"""Form: labelled fields, navigation, validation and one-shot submission.

A :class:`Form` composes ordinary components into a vertical form.  Each
:class:`Field` pairs a component with a name, an optional label and two
hooks: ``validate(value) -> str | None`` for the submit check and
``value() -> object`` for a custom extractor.  Without an extractor the
value comes from the component's own state by duck typing -- the first of
``value``, ``text``, ``checked``, ``selected`` or ``marked`` that the
component exposes (a callable attribute is called).  ``take_result()`` is
never touched: reading a field must not consume its pending result.

Rendering is one vertical stack per field -- an optional label row, the
component's rows at the form width, and an error row after a failed
submit -- with ``gap`` blank rows between fields.  Every row is fitted to
the painting width, and the geometry of the last render feeds
``child_at`` so a host's hit test descends into the field component.

Focus is the form's own: :meth:`Form.focus` and :meth:`Form.move` track
``index`` and mirror it onto every :class:`~motui.core.block.Focusable`
field (the new one ``True``, all others ``False``).  The keyboard routes
the focused field first -- its own ``handle`` wins over navigation -- then
``tab``/``down`` step forward, ``s-tab``/``up`` step back and ``enter``
runs :meth:`Form.activate`: validate every field, write each error back to
its :class:`Field`, and on success leave ``{name: value}`` pending for
:meth:`Form.take_result` and call ``on_submit`` once.  Navigation answers
``True`` only when the index moved, so a host keeps Tab at the ends.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ..core.block import Component, Controller, Focusable, Revisioned
from ..core.events import Event, KeyEvent
from ..core.lines import Line
from ..core.theme import Styles, Theme
from ..core.widget import Widget

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
    if isinstance(component, Revisioned):
        snapshot = component.revision()
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
        """Mirror ``index`` onto every Focusable field."""
        for position, field in enumerate(self._fields):
            component = field.component
            if isinstance(component, Focusable):
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

    def handle(self, event: Event) -> bool:
        """Route one event; ``True`` when the form consumed it.

        The focused field's own ``handle`` goes first (a controller keeps
        its keys -- including a ``PasteEvent``, which the field's own
        handle consumes).  Then the form's navigation: ``tab``/``down``
        and ``s-tab``/``up`` move the field cursor and answer ``True`` only
        on a real move, so the ends hand Tab back to the host; ``enter``
        activates the form and is always consumed (a validation failure is
        still the form's answer -- the errors are now on screen).
        """
        if not self._fields:
            return False
        component = self._fields[self._index].component
        if isinstance(component, Controller) and component.handle(event):
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

    # -- values and submission ----------------------------------------------------

    @staticmethod
    def _value(field: Field) -> object:
        """Extract a field's value: its hook first, then the component's state.

        The attribute fallback is the read-only duck-typing order
        ``value``, ``text``, ``checked``, ``selected``, ``marked``; a
        callable attribute is called.  A field with none of them answers
        ``None``.  ``take_result()`` is deliberately not consulted.
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
        """Validate every field and submit when all pass.

        Each field's error is written back (``None`` clears it).  Any
        error answers ``False`` and leaves nothing pending.  Otherwise the
        ``{name: value}`` mapping becomes the one-shot result and
        ``on_submit`` runs once, with the same mapping.
        """
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

    def take_result(self) -> dict[str, object] | None:
        """Read the submitted mapping once and clear it."""
        result = self._pending
        self._pending = None
        return result

    # -- rendering ----------------------------------------------------------------

    def render(self, width: int) -> list[Line]:
        """Stack label, component and error rows per field, with gaps between.

        The label and error styles are the theme's ``content.accent`` and
        ``status.danger`` read on every call, so a rethemed form repaints.
        """
        label_style = self.group("content").accent
        error_style = self.group("status").danger
        out: list[Line] = []
        spans: list[tuple[int, int]] = []
        for position, field in enumerate(self._fields):
            if position and self._gap:
                out.extend(Line() for _ in range(self._gap))
            if field.label:
                out.append(Line.from_text(field.label, label_style).fit(width))
            rows = list(field.component.render(width))
            spans.append((len(out), len(rows)))
            out.extend(row.fit(width) for row in rows)
            if field.error:
                out.append(Line.from_text(field.error, error_style).fit(width))
        self._spans = spans
        return out

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """Map a rendered component row to its field's component.

        Label rows, error rows, gaps and every cell outside the painting
        answer ``None``; the geometry is the last :meth:`render`'s.
        """
        if row < 0 or col < 0:
            return None
        for position, (start, count) in enumerate(self._spans):
            if start <= row < start + count:
                return self._fields[position].component, row - start, col
        return None

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

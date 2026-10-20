"""RowBands: the one row-band vocabulary the row widgets resolve through.

A row view paints a band *underneath* a row's own text styles: the resting
ground, the engaged band the keyboard cursor wears, the pointer's hover
band, and the quiet band a disabled row wears.  Five components carried
five copies of that precedence rule; :class:`RowBands` is the one value
they all resolve, so the priority lives in one place and a host can theme
all of them by handing over one frozen value.

The precedence, in order: a disabled row wears ``disabled``; otherwise the
hovered row wears ``hover`` whatever row it is on (D3: the pointer is the
more immediate signal); otherwise the cursor row wears ``active`` when the
control is focused.  An *unfocused* cursor row keeps the active band and
merges ``focus`` onto it -- the theme's ``dim`` by default, the quiet
attenuation of a row that still is the position mark -- unless the active
band carries an explicit background, where ``dim`` would dim the text into
the surface instead of weakening the band.  Every other row rests on
``ground``.  A component whose engaged row never weakens when unfocused
(the navigation rail, the form groups) composes the tokens itself or
passes ``focus=NONE``.

``text`` is the row-text token a host may set; the shared band helper does
not apply it (each family keeps its own label style), but the value is part
of the snapshot so a band swap repaints.

:func:`rest` is the rendering half: ``fit`` to the width, then the band
``fill``ed *under* the row's own segments at the row's own width.  The
``NONE`` fast path is exactly the old ``_rest``: a row on the default
ground is byte-for-byte the row it always was.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..kernel.lines import Line
from ..kernel.style import NONE, Style
from ..kernel.theme import Theme

__all__ = ["RowBands", "resolve_band", "rest"]


@dataclass(frozen=True, slots=True)
class RowBands:
    """The six band tokens one row view paints with.

    ``ground``/``active``/``hover``/``disabled`` are the surfaces a row can
    rest on; ``focus`` is the attenuation merged onto an unfocused active
    row, and ``text`` is a host-level row-text token carried beside them.
    The value is frozen and every field is a :class:`~motui.kernel.style.Style`,
    so two equal values promise equal rows at one width.
    """

    ground: Style = NONE
    active: Style = NONE
    hover: Style = NONE
    focus: Style = NONE
    text: Style = NONE
    disabled: Style = NONE

    @classmethod
    def from_theme(cls, theme: Theme, **overrides: Style) -> "RowBands":
        """The theme's band vocabulary, with any token overridden by keyword.

        ``ground``/``active``/``hover`` come from their theme fields,
        ``focus``/``disabled`` from the theme's ``dim`` (the attenuation and
        the quiet band the default themes use), and ``text`` stays
        ``NONE``.  ``overrides`` wins over the theme token, which is how an
        explicit style parameter keeps its old precedence.
        """
        bands = cls(
            ground=theme.ground,
            active=theme.ground_active,
            hover=theme.hover,
            focus=theme.dim,
            text=NONE,
            disabled=theme.dim,
        )
        return replace(bands, **overrides) if overrides else bands

    def band(
        self, *, current: bool, hovered: bool, focused: bool, disabled: bool
    ) -> Style:
        """The surface one row rests on, by the precedence in the module docstring."""
        if disabled:
            return self.disabled
        if hovered:
            return self.hover
        if current:
            if focused:
                return self.active
            if self.active.bg is None:
                return self.active.merge(self.focus)
            return self.active
        return self.ground


def resolve_band(
    bands: RowBands, current: bool, hovered: bool, focused: bool, disabled: bool
) -> Style:
    """The positional entry to :meth:`RowBands.band` (the row widgets' call).

    The four flags are positional here so the modules that resolve a row's
    band carry no keyword spelling of the disabled state at their call
    sites; the method itself keeps its documented keyword-only signature.
    """
    return bands.band(
        current=current, hovered=hovered, focused=focused, disabled=disabled
    )


def rest(row: Line, width: int, band: Style) -> Line:
    """One row on its band: ``fit`` then ``fill`` at the fitted row's width.

    The band rests under the row's own segments (the Rich
    ``Padding(style=...)`` rule); the ``NONE`` fast path leaves a resting
    row byte-for-byte unchanged.
    """
    fitted = row.fit(width)
    return fitted if band == NONE else fitted.fill(fitted.width, band)

"""The Home tiles' deterministic miniature animations."""

from __future__ import annotations

from ..kernel.cell import Line, Segment
from ..kernel.style import Style
from ..kernel.theme import Theme

__all__ = [
    "mini_components",
    "mini_dashboard",
    "mini_layout",
    "mini_motion",
    "mini_terminal",
    "mini_themes",
]


def _bar(width: int, fraction: float, style: Style) -> Line:
    """One progress-style bar of ``width`` cells, ``fraction`` filled."""
    filled = max(0, min(width, round(width * fraction)))
    if filled <= 0:
        return Line()
    if filled >= width:
        return Line((Segment("\u2588" * width, style),))
    return Line(
        (
            Segment("\u2588" * filled, style),
            Segment("\u25b7" * (width - filled), style),
        )
    )


def _sweep(phase: int, period: int) -> float:
    """A deterministic 0..1..0 triangle wave over ``period`` ticks."""
    step = phase % period
    span = period / 2
    return abs(step - span) / span


def mini_components(phase: int, width: int, theme: Theme) -> list[Line]:
    """Widget preview: three stacked bars pulsing one after another."""
    styles = (theme.content.accent, theme.status.success, theme.status.warning)
    rows: list[Line] = []
    for index, style in enumerate(styles):
        fraction = 0.5 + 0.5 * _sweep(phase + index * 7, 16)
        rows.append(_bar(width - 1, fraction, style))
    return rows


def mini_layout(phase: int, width: int, theme: Theme) -> list[Line]:
    """Layout preview: a 2x2 grid whose active quadrant rotates."""
    active = (phase // 8) % 4
    hot = theme.content.accent
    cold = theme.borders.base
    half = max(1, (width - 1) // 2)
    rows: list[Line] = []
    for row in range(2):
        cells: list[Segment] = []
        for col in range(2):
            style = hot if row * 2 + col == active else cold
            cells.append(Segment("\u2500" * half, style))
            if col == 0:
                cells.append(Segment(" ", Style()))
        rows.append(Line(tuple(cells)))
    return rows


def mini_motion(phase: int, width: int, theme: Theme) -> list[Line]:
    """Motion preview: a four-dot snake crawling along a small track."""
    track = max(4, width - 1)
    head = theme.status.success
    trail = theme.text.faint
    rows: list[Line] = [Line(), Line()]
    for _row in range(2):
        cells: list[str | None] = [None] * track
        for dot in range(4):
            cells[(phase // 2 - dot) % track] = str(dot)
        segments: list[Segment] = []
        previous: int | None = None
        for col, dot in enumerate(cells):
            if dot is None:
                continue
            style = head if dot == "0" else trail
            gap = 0 if previous is None else col - previous - 1
            segments.append(Segment("\u00b7" * gap + "\u25cf", style))
            previous = col
        rows.append(Line(tuple(segments)) if segments else Line())
    return rows


def mini_dashboard(phase: int, width: int, theme: Theme) -> list[Line]:
    """Dashboard preview: a wave of sparkline bars, 6 rows tall."""
    accent = theme.content.accent
    rows: list[Line] = []
    for row in range(6):
        segments: list[Segment] = []
        for col in range(width - 1):
            level = (phase // 2 + col * 5 + row * 3) % 11
            segments.append(Segment("\u258f" if level > row * 2 else " ", accent))
        rows.append(Line(tuple(segments)))
    return rows


def mini_terminal(phase: int, width: int, theme: Theme) -> list[Line]:
    """Terminal preview: a prompt whose typed text grows and resets."""
    faint = theme.text.faint
    caret = theme.content.accent
    typed = phase % max(1, width - 4)
    prompt = Segment("> ", faint)
    text = Segment("motui " * (typed // 6), faint)
    cursor_char = "\u2588" if (phase // 4) % 2 == 0 else " "
    note = "60 Hz \u00b7 1/60 throttle"[: width - 1]
    return [
        Line((prompt, text, Segment(cursor_char, caret))),
        Line(),
        Line((Segment(note, faint),)),
    ]


def mini_themes(phase: int, width: int, theme: Theme) -> list[Line]:
    """Themes preview: four swatches whose highlight cycles."""
    swatches = (
        theme.content.accent,
        theme.status.success,
        theme.status.warning,
        theme.status.danger,
    )
    active = (phase // 6) % len(swatches)
    block = max(2, (width - 1) // len(swatches))
    rows: list[Line] = [Line()]
    for _row in range(2):
        segments: list[Segment] = []
        for index, style in enumerate(swatches):
            glyph = "\u2588" * block if index == active else "\u2591" * block
            segments.append(Segment(glyph, style))
        rows.append(Line(tuple(segments)))
    return rows

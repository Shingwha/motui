"""Large, low-frequency previews for the selected Home experiment."""

from __future__ import annotations

import math

from ..kernel.cell import Line, Segment
from ..kernel.layout import Constraints
from ..kernel.theme import Theme
from ..widgets import Sparkline

__all__ = [
    "mini_components",
    "mini_dashboard",
    "mini_layout",
    "mini_motion",
    "mini_terminal",
    "mini_themes",
]


def _text(text: str, theme: Theme, accent: bool = False) -> Line:
    return Line.from_text(text, theme.content.accent if accent else theme.text.muted)


def _bar(width: int, fraction: float, theme: Theme) -> Line:
    filled = max(0, min(width, round(width * fraction)))
    return Line(
        (
            Segment("█" * filled, theme.content.accent),
            Segment("░" * (width - filled), theme.text.faint),
        )
    )


def mini_components(phase: int, width: int, theme: Theme) -> list[Line]:
    value = 4 + (phase // 24) % 7
    focused = (phase // 90) % 3
    fields = ("callsign", "channel", "gain")
    rows = [_text("COMPOSE A LIVE CONSOLE", theme, True), Line()]
    for index, label in enumerate(fields):
        cursor = ">" if index == focused else " "
        rows.append(_text(f"{cursor} {label:<9} {'─' * max(2, width - 15)}", theme))
    rows.extend(
        [
            Line(),
            _text(f"  gain {value:02d}/10", theme),
            _bar(max(4, width - 4), value / 10, theme),
            Line(),
            _text("  [ arm signal ]   every control is real", theme, True),
        ]
    )
    return rows


def mini_layout(phase: int, width: int, theme: Theme) -> list[Line]:
    split = 0.35 + 0.15 * math.sin(phase / 90)
    left = max(6, round((width - 3) * split))
    right = max(6, width - 3 - left)
    rows = [_text(f"CONSTRAINTS  {width} x 10  ·  split {split:.2f}", theme, True), Line()]
    for row in range(6):
        if row in (0, 5):
            left_corner, right_corner = ("┌", "┐") if row == 0 else ("└", "┘")
            rows.append(
                _text(
                    f"{left_corner}{'─' * (left - 2)}{right_corner} "
                    f"{left_corner}{'─' * (right - 2)}{right_corner}",
                    theme,
                )
            )
        else:
            left_text = " FLOW " if row == 2 else ""
            right_text = " DOCK " if row == 3 else ""
            rows.append(
                _text(
                    f"│{left_text:<{left - 2}}│ │{right_text:<{right - 2}}│",
                    theme,
                )
            )
    rows.extend([Line(), _text("One tree. Every size. No fixed canvas.", theme)])
    return rows


def mini_motion(phase: int, width: int, theme: Theme) -> list[Line]:
    rows = [_text("SUB-CELL PARTICLE FIELD", theme, True)]
    height = 9
    cx, cy = (width - 1) / 2, 4
    for y in range(height):
        cells = [" "] * width
        for orbit in range(3):
            radius_x = 5 + orbit * max(3, width // 8)
            radius_y = 1.5 + orbit
            angle = phase * (0.008 + orbit * 0.003) + orbit * 2
            x = round(cx + math.cos(angle) * radius_x)
            py = round(cy + math.sin(angle) * radius_y)
            if 0 <= x < width and 0 <= py < height:
                cells[py] = "●" if orbit == 0 else "○"
        if 0 <= round(cx) < width and y == cy:
            cells[round(cx)] = "✦"
        style = theme.content.accent if y % 2 else theme.content.inline_code
        rows.append(Line.from_text("".join(cells).rstrip(), style))
    return rows


def mini_dashboard(phase: int, width: int, theme: Theme) -> list[Line]:
    values = [
        0.5 + 0.28 * math.sin((phase + index) / 22) + 0.12 * math.cos((phase + index) / 9)
        for index in range(48)
    ]
    spark = Sparkline(values, marker="braille", style=theme.status.success)
    graph = list(spark.render(Constraints(width=max(4, width - 2), max_height=4)))
    signal = round(92 + 6 * math.sin(phase / 45))
    return [
        _text("DSN-07 / LIVE UPLINK", theme, True),
        _text(f"SIGNAL LOCKED  {signal}%  ·  42 ms  ·  0 drops", theme),
        Line(),
        *graph,
        Line(),
        _text("02:14:21  route  traffic moved to relay-04", theme),
        _text("02:14:29  signal lock recovered", theme),
    ]


def mini_terminal(phase: int, width: int, theme: Theme) -> list[Line]:
    stages = ("KEY", "EVENT", "WIDGET", "DIFF", "CELLS")
    active = (phase // 45) % len(stages)
    rows = [_text("FOLLOW ONE KEYSTROKE", theme, True), Line()]
    for index, stage in enumerate(stages):
        marker = "●" if index == active else "○"
        rows.append(_text(f"  {marker} {stage:<8} {'→' if index < 4 else '✓'}", theme))
    rows.extend(
        [
            Line(),
            _text("enter  →  KeyEvent('enter')", theme),
            _text("3 rows changed  →  one synchronized flush", theme),
            Line(),
            _text("16.7 ms budget · unchanged rows write zero bytes", theme, True),
        ]
    )
    return rows


def mini_themes(phase: int, width: int, theme: Theme) -> list[Line]:
    names = ("signal", "aurora", "ember", "paper", "mono")
    active = (phase // 120) % len(names)
    rows = [_text("ONE UI / FIVE GLOBAL SKINS", theme, True), Line()]
    styles = (
        theme.content.accent,
        theme.content.inline_code,
        theme.status.success,
        theme.status.warning,
        theme.status.danger,
    )
    for index, name in enumerate(names):
        marker = ">" if index == active else " "
        rows.append(Line((Segment(f"{marker} {name:<9}"),)))
        rows.append(
            Line(
                tuple(
                    Segment("████" if index == active else "▒▒▒▒", style)
                    for style in styles
                )
            )
        )
    return rows

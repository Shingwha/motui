"""Terminal capability probes: size, color mode and the environment's theme.

The only place that reads the process environment or the terminal's
geometry."""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping

from ..kernel.style import ColorMode
from ..kernel.theme import Theme

__all__ = ["auto_theme", "detect_color_mode", "terminal_size"]


def terminal_size() -> tuple[int, int]:
    """Current terminal size as ``(columns, rows)``, falling back to 80x24."""
    size = shutil.get_terminal_size(fallback=(80, 24))
    return (size.columns, size.lines)


def detect_color_mode(env: Mapping[str, str] | None = None) -> ColorMode:
    """The color capability the environment asks for: NO_COLOR or ``TERM=dumb``
    means none, COLORTERM truecolor wins, then 256color, else truecolor."""
    if env is None:
        env = os.environ
    if env.get("NO_COLOR") or env.get("TERM") == "dumb":
        return "none"
    if env.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return "truecolor"
    if "256color" in env.get("TERM", "").lower():
        return "256"
    return "truecolor"


def auto_theme(env: Mapping[str, str] | None = None) -> Theme:
    """The shipped light or dark theme the environment asks for;
    :meth:`Theme.auto` itself never reads the process environment."""
    return Theme.auto(os.environ if env is None else env)

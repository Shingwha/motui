"""Terminal capability probes: size, color mode, and the environment's theme.

These are the only modules in the toolkit that read the process environment or
the terminal's geometry.  The pure values live in the kernel; the probes live
here, so a kernel import can never reach ``os`` or a terminal ioctl.

``Theme.auto(env)`` takes an explicit mapping; :func:`auto_theme` is the
convenience that reads :data:`os.environ` for a host that wants the shipped
choice without naming the process environment itself.
"""

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
    """The color capability the environment asks for.

    ``NO_COLOR`` set to a **non-empty** value (the no-color.org convention:
    an empty variable is no preference) or ``TERM=dumb`` answers ``"none"``;
    a ``COLORTERM`` of ``truecolor``/``24bit`` answers ``"truecolor"``; a
    ``TERM`` naming ``256color`` answers ``"256"``; anything else keeps the
    toolkit's historical answer, ``"truecolor"`` -- the palette the styles
    are authored in.  ``env`` defaults to :data:`os.environ` and is read as
    a plain mapping, so a caller (or a test) can pass its own.
    """
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
    """The shipped light or dark theme the environment asks for.

    ``env`` defaults to :data:`os.environ`; :meth:`Theme.auto` itself never
    reads the process environment, so a caller that wants that convenience
    takes this door.
    """
    return Theme.auto(os.environ if env is None else env)

"""The single source of ANSI escape sequences in the toolkit.

Every escape byte the toolkit emits is constructed here; no other module
builds escape strings by hand.  Also hosts the Windows VT-capability probe
(:func:`enable_vt`) whose boolean result decides whether a screen is live.
"""

from __future__ import annotations

import base64
import os

__all__ = [
    "CLEAR_LINE",
    "ESC",
    "begin_sync_update",
    "clear_screen",
    "copy_clipboard",
    "cursor_position",
    "disable_bracketed_paste",
    "disable_focus_events",
    "disable_mouse_tracking",
    "enable_bracketed_paste",
    "enable_focus_events",
    "enable_mouse_tracking",
    "enable_vt",
    "end_sync_update",
    "enter_alt_screen",
    "hide_cursor",
    "leave_alt_screen",
    "show_cursor",
]

#: The escape byte every sequence starts with.
ESC = "\x1b"

#: Erase from the cursor to the end of the line (what a row rewrite emits).
CLEAR_LINE = "\x1b[K"


def begin_sync_update() -> str:
    """Open a synchronized update (DECSET 2026): the terminal holds the frame.

    From here until :func:`end_sync_update` the terminal collects what it
    receives and swaps it in with one repaint, so a mid-frame stream of row
    rewrites is never shown half-painted.  A terminal that does not know the
    mode ignores it -- the bytes around a frame are harmless everywhere --
    which is why the painter may send the pair unconditionally.
    """
    return f"{ESC}[?2026h"


def end_sync_update() -> str:
    """Close the synchronized update: the held frame is rendered, once."""
    return f"{ESC}[?2026l"


def clear_screen() -> str:
    """Erase the whole screen."""
    return f"{ESC}[2J"


def cursor_position(row: int, col: int) -> str:
    """Move the cursor to 1-based ``(row, col)``; the top-left corner is 1;1.

    ``row < 1`` or ``col < 1`` emits nothing (an invalid coordinate).
    """
    if row < 1 or col < 1:
        return ""
    return f"{ESC}[{row};{col}H"


def hide_cursor() -> str:
    return f"{ESC}[?25l"


def show_cursor() -> str:
    return f"{ESC}[?25h"


def enter_alt_screen() -> str:
    """Switch to the alternate screen buffer (vim/htop-style full screen)."""
    return f"{ESC}[?1049h"


def leave_alt_screen() -> str:
    """Restore the primary screen buffer."""
    return f"{ESC}[?1049l"


def enable_mouse_tracking(*, hover: bool = False) -> str:
    """Ask the terminal to report mouse input: 1000 + (1003|1002) + SGR 1006.

    ``1000h`` reports button presses and wheel motion, ``1006h`` puts the
    reports in SGR form, and the middle mode is the motion one: ``1002h``
    (the default) reports motion only while a button is held -- the
    button-event tracking a drag gesture consumes -- while ``1003h``
    reports **all** motion, which is what hover needs (a pointer that only
    moves is never reported under 1002).  Hover is opt-in: a host that
    never builds a :class:`~mocode_tui.pointer.Pointer` keeps the smaller
    mode, and every default call emits exactly the bytes it always did.
    """
    mode = "1003" if hover else "1002"
    return f"{ESC}[?1000h{ESC}[?{mode}h{ESC}[?1006h"


def disable_mouse_tracking(*, hover: bool = False) -> str:
    """Stop mouse reporting: disable 1006 + 1003 + 1002 + 1000, in that order.

    All of them, always: the reverse-order contract forbids leaving a mode
    on (a terminal left in 1003 floods the shell with motion reports after
    the session ends), and the call cannot know which mode the enable side
    chose -- disabling a mode that was never set is a no-op, so the
    robust answer is every off.  ``hover`` is accepted for signature
    symmetry with :func:`enable_mouse_tracking` and never changes the
    bytes.
    """
    return f"{ESC}[?1006l{ESC}[?1003l{ESC}[?1002l{ESC}[?1000l"


def enable_bracketed_paste() -> str:
    """Ask the terminal to wrap a paste in ``CSI 200~`` / ``CSI 201~``.

    This is DECSET 2004: with it on, the terminal hands over a paste as one
    bracketed unit of bytes instead of replaying it as keystrokes, so a
    multi-line paste decodes to one
    :class:`~mocode_tui.core.events.Paste` event -- never a run of ``enter``
    keys, one per line break.
    """
    return f"{ESC}[?2004h"


def disable_bracketed_paste() -> str:
    """Stop bracketed paste (reverse of :func:`enable_bracketed_paste`)."""
    return f"{ESC}[?2004l"


def enable_focus_events() -> str:
    """Ask the terminal to report window focus changes (DECSET 1004).

    With the mode on the terminal sends ``CSI I`` when its window gains
    focus and ``CSI O`` when it loses it; the decoder names those
    ``focus_in`` / ``focus_out``.  Opt-in: the reports are the host's to
    interpret -- the toolkit's :class:`~mocode_tui.pointer.Pointer` still
    watches mouse reports only, and a host scrubs its own state on
    ``focus_out`` (clearing a hover, pausing an animation) itself.
    """
    return f"{ESC}[?1004h"


def disable_focus_events() -> str:
    """Stop focus reporting (reverse of :func:`enable_focus_events`)."""
    return f"{ESC}[?1004l"


def copy_clipboard(text: str) -> str:
    """Set the terminal's clipboard to ``text`` (OSC 52), explicitly.

    ``\\x1b]52;c;<base64>\\x07``: the ``c`` selects the system clipboard and
    the payload is the base64 of the UTF-8 bytes (stdlib :mod:`base64`,
    nothing hand-rolled), so any text travels -- newlines, CJK, emoji --
    as one unit.  Best-effort by design (D6): terminals may refuse it or
    lack the clipboard for an application to write, so callers treat a
    write as a courtesy, never a guarantee.
    """
    payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"{ESC}]52;c;{payload}\a"


# Windows console VT processing.
_STD_OUTPUT_HANDLE = 0xFFFFFFF5  # (DWORD)-11
_ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004


def enable_vt() -> bool:
    """Best-effort Windows virtual-terminal enablement.

    Returns ``True`` on non-Windows platforms (VT is native there) and on
    Windows when ``ENABLE_VIRTUAL_TERMINAL_PROCESSING`` is already set or was
    just set successfully.  Any failure — no console, ctypes unavailable,
    access denied — returns ``False`` so callers can treat the screen as
    non-live instead of emitting garbled escapes.
    """
    if os.name != "nt":
        return True
    try:
        return _windows_vt_enabled()
    except Exception:
        return False


def _windows_vt_enabled() -> bool:
    """Set/observe ``ENABLE_VIRTUAL_TERMINAL_PROCESSING`` on the stdout console.

    Only called on Windows.  Propagates unexpected failures to
    :func:`enable_vt`, which converts them to ``False``.
    """
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetStdHandle.restype = wintypes.HANDLE
    kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel32.GetConsoleMode.restype = wintypes.BOOL
    kernel32.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.SetConsoleMode.restype = wintypes.BOOL
    kernel32.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]

    handle = kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)
    if not handle:  # NULL: process has no standard output handle
        return False
    mode = wintypes.DWORD()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        return False  # not a console (pipe/file) or access denied
    if mode.value & _ENABLE_VIRTUAL_TERMINAL_PROCESSING:
        return True
    desired = mode.value | _ENABLE_VIRTUAL_TERMINAL_PROCESSING
    return bool(kernel32.SetConsoleMode(handle, desired))

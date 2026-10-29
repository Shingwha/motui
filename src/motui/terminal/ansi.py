"""The single source of ANSI escape sequences in the toolkit.

Every escape byte is constructed here; no other module builds escape
strings. Also hosts the Windows VT probe."""

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
    "cursor_shape",
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
    "hyperlink_close",
    "hyperlink_open",
    "leave_alt_screen",
    "set_window_title",
    "show_cursor",
]

#: The escape byte every sequence starts with.
ESC = "\x1b"

#: Erase from the cursor to the end of the line (what a row rewrite emits).
CLEAR_LINE = "\x1b[K"


def begin_sync_update() -> str:
    """Open a synchronized update (DECSET 2026): the terminal holds the frame
    until :func:`end_sync_update`, so a mid-frame stream is never shown
    half-painted."""
    return f"{ESC}[?2026h"


def end_sync_update() -> str:
    """Close the synchronized update: the held frame is rendered, once."""
    return f"{ESC}[?2026l"


def clear_screen() -> str:
    """Erase the whole screen."""
    return f"{ESC}[2J"


def cursor_position(row: int, col: int) -> str:
    """Move the cursor to 1-based ``(row, col)``; an invalid coordinate emits
    nothing."""
    if row < 1 or col < 1:
        return ""
    return f"{ESC}[{row};{col}H"


#: DECSCUSR parameter per shape name: STEADY variants (2 = block, 4 =
#: underline, 6 = beam) so the cursor never blinks, and 0 = the terminal's
#: own default.
_CURSOR_SHAPES = {"default": 0, "block": 2, "underline": 4, "beam": 6}


def cursor_shape(shape: str) -> str:
    """Set the cursor shape (DECSCUSR) with the steady variant; an unknown
    shape raises ``KeyError``."""
    return f"{ESC}[{_CURSOR_SHAPES[shape]} q"


def set_window_title(text: str) -> str:
    """Set the window title (OSC 2), dropping C0 controls so a title cannot
    inject escape sequences or truncate at a bell."""
    clean = "".join(ch for ch in text if ord(ch) >= 0x20)
    return f"{ESC}]2;{clean}\a"


def hyperlink_open(url: str) -> str:
    """Open an OSC 8 hyperlink over the following text; C0 controls are dropped
    from ``url``."""
    clean = "".join(ch for ch in url if ord(ch) >= 0x20)
    return f"{ESC}]8;;{clean}{ESC}\\"


def hyperlink_close() -> str:
    """Close the OSC 8 hyperlink :func:`hyperlink_open` opened."""
    return f"{ESC}]8;;{ESC}\\"


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
    """Ask for mouse input: 1000 + (1003 hover | 1002 drag) + SGR 1006; 1003 is
    what motion-only hover needs."""
    mode = "1003" if hover else "1002"
    return f"{ESC}[?1000h{ESC}[?{mode}h{ESC}[?1006h"


def disable_mouse_tracking(*, hover: bool = False) -> str:
    """Disable 1006/1003/1002/1000 in reverse order, so no mode is left on."""
    return f"{ESC}[?1006l{ESC}[?1003l{ESC}[?1002l{ESC}[?1000l"


def enable_bracketed_paste() -> str:
    """Ask the terminal to wrap a paste in CSI 200~/201~, so it decodes as one
    PasteEvent instead of replayed keystrokes."""
    return f"{ESC}[?2004h"


def disable_bracketed_paste() -> str:
    """Stop bracketed paste (reverse of :func:`enable_bracketed_paste`)."""
    return f"{ESC}[?2004l"


def enable_focus_events() -> str:
    """Ask for window focus reports (DECSET 1004); opt-in, and the host
    interprets them."""
    return f"{ESC}[?1004h"


def disable_focus_events() -> str:
    """Stop focus reporting (reverse of :func:`enable_focus_events`)."""
    return f"{ESC}[?1004l"


def copy_clipboard(text: str) -> str:
    """Set the clipboard (OSC 52) with the base64 of the UTF-8 bytes;
    best-effort by design, since terminals may refuse it."""
    payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"{ESC}]52;c;{payload}\a"


# Windows console VT processing.
_STD_OUTPUT_HANDLE = 0xFFFFFFF5  # (DWORD)-11
_ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004


def enable_vt() -> bool:
    """Best-effort Windows VT enablement; ``True`` on non-Windows or once the
    mode is set, and any failure is ``False`` so the screen stays non-live."""
    if os.name != "nt":
        return True
    try:
        return _windows_vt_enabled()
    except Exception:
        return False


def _windows_vt_enabled() -> bool:
    """Set or observe ``ENABLE_VIRTUAL_TERMINAL_PROCESSING`` on the stdout
    console; unexpected failures propagate to :func:`enable_vt`."""
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

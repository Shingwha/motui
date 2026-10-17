"""The recorder and the replay source: a real session's events on disk.

Two :class:`~motui.core.events.KeySource` wrappers, the developer tools
the tui-depth wave adds (D11):

* :class:`RecordingKeys` wraps any source and appends every event it hands
  out to a JSONL file, one line per event, so a real session becomes a file
  in the repository::

      {"ms": 125, "event": {"kind": "key", "name": "c-f", "char": ""}}

* :class:`ReplayKeys` reads such a file back and hands the events out again
  in order, waiting the recorded milliseconds between them scaled by
  ``speed`` -- ``speed=0`` yields them with no wait at all, the contract the
  library and its tests hold (nothing in the toolkit ever sleeps).

Recording is **event-level**, not byte-level: the Windows console path has
no single byte seam a live session's input passes through, while every
source hands events to one ``read()``.  The decorator only *wraps*: it reads
its source, copies the event out and answers exactly what the source
answered.  An EOF (``None``) is not recorded -- the file ends there -- and
the one-shot ``None`` a :class:`~motui.core.events.ScriptedKeys` carries
mid-sequence passes through as the source's own semantics.

The payloads are the model's own fields: a key's ``name``/``char``, a paste's
``text``, a mouse report's ``name``/``button``/``x``/``y`` and its report
class -- carried as ``report`` (``press``/``release``/``motion``), because
``kind`` names the payload's *type* (``key``/``paste``/``mouse``).
:func:`encode_event` and :func:`decode_event` are the pure pair the two
classes run on, and the file IO lives in the classes alone.

The recipe -- record a real session, run it as a regression::

    source = RawTerminalKeys(hover=True)        # the live terminal
    source.start()
    keys = RecordingKeys(source, "session.jsonl")
    asyncio.run(TUI(keys=keys).run(host_loop))
    source.close()

    # later, headless, in a pytest: no terminal and no wait
    TUI(screen=HeadlessScreen(), keys=ReplayKeys("session.jsonl", speed=0))
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

from ..core.events import Key, KeySource, MouseEvent, Paste

__all__ = ["RecordingKeys", "ReplayKeys"]

#: The three payload types a recording line can carry.
_KEY, _PASTE, _MOUSE = "key", "paste", "mouse"

#: The three report classes a serialized mouse event can carry.
_REPORTS = ("press", "release", "motion")


# -- the pure pair -----------------------------------------------------------


def _payload_of(event: Key | Paste) -> dict:
    """One event as the JSON object its line carries (the model's fields)."""
    if isinstance(event, MouseEvent):
        # ``report`` -- not ``kind``: the payload's ``kind`` is the event
        # *type* ("mouse"), and the report's own class is the ``kind`` the
        # event model carries.  The name keeps both readable in one object.
        return {
            "kind": _MOUSE,
            "name": event.name,
            "button": event.button,
            "x": event.x,
            "y": event.y,
            "report": event.kind,
        }
    if isinstance(event, Paste):
        return {"kind": _PASTE, "text": event.text}
    if isinstance(event, Key):
        return {"kind": _KEY, "name": event.name, "char": event.char}
    raise TypeError(f"cannot record {type(event).__name__}: not a key event")


def encode_event(ms: int, event: Key | Paste) -> str:
    """One recording line: ``{"ms": ..., "event": {...}}``, no newline.

    ``ms`` is the event's stamp relative to the recording's start, in
    whole milliseconds; ``event`` is the model's own fields (see the module
    docstring).  Pure -- the class appends the line to the file.
    """
    return json.dumps({"ms": ms, "event": _payload_of(event)}, ensure_ascii=False)


def _bad(lineno: int, message: str) -> ValueError:
    """The one error shape a bad recording line raises: the line number in it."""
    return ValueError(f"recording line {lineno}: {message}")


def _event_from(payload: dict, lineno: int) -> Key | Paste:
    """Rebuild one event from its payload; ``ValueError`` names the line."""
    kind = payload.get("kind")
    if kind == _KEY:
        name = payload.get("name")
        char = payload.get("char", "")
        if not isinstance(name, str) or not isinstance(char, str):
            raise _bad(lineno, "a key needs string name/char")
        return Key(name, char)
    if kind == _PASTE:
        text = payload.get("text")
        if not isinstance(text, str):
            raise _bad(lineno, "a paste needs a string text")
        return Paste(text)
    if kind == _MOUSE:
        name = payload.get("name")
        report = payload.get("report")
        if not isinstance(name, str) or report not in _REPORTS:
            raise _bad(lineno, f"a mouse report needs a name and one of {_REPORTS}")
        coords = []
        for field in ("button", "x", "y"):
            value = payload.get(field)
            if not isinstance(value, int) or isinstance(value, bool):
                raise _bad(lineno, f"a mouse report needs an integer {field}")
            coords.append(value)
        return MouseEvent(name, button=coords[0], x=coords[1], y=coords[2], kind=report)
    raise _bad(lineno, f"unknown event kind {kind!r}")


def decode_event(line: str, lineno: int) -> tuple[int, Key | Paste]:
    """Parse one recording line into ``(ms, event)``; pure.

    Every malformed line raises :class:`ValueError` with ``lineno`` in the
    message -- bad JSON, a non-object record, a missing or non-integer
    ``ms``, a payload :func:`encode_event` would never write.
    """
    try:
        record = json.loads(line)
    except json.JSONDecodeError as error:
        raise _bad(lineno, f"not JSON: {error.msg}") from error
    if not isinstance(record, dict):
        raise _bad(lineno, "the record is not a JSON object")
    ms = record.get("ms")
    if not isinstance(ms, int) or isinstance(ms, bool):
        raise _bad(lineno, "ms is not an integer")
    payload = record.get("event")
    if not isinstance(payload, dict):
        raise _bad(lineno, "event is not a JSON object")
    return ms, _event_from(payload, lineno)


# -- the two sources ---------------------------------------------------------


class RecordingKeys:
    """A :class:`~motui.core.events.KeySource` that records what it serves.

    ``RecordingKeys(source, path)`` decorates ``source``: every ``read()``
    pulls the next event from the source, appends its JSON line (with its
    stamp relative to the recording's start) to ``path`` and answers the
    event untouched.  The constructor starts the recording -- the file is
    created fresh (truncated), so one path holds one recording and its
    timing base is honest -- and every line is written and flushed on its
    own, so a session that dies mid-way leaves every event it delivered on
    disk.

    An EOF the source reports (``None``) is **not** recorded and is returned
    as it came: the file ends where the session's events end, and a source
    that resumes after a one-shot EOF (a scripted replay) keeps recording
    into the same file.

    Only ``read()`` is decorated -- the source's own lifecycle stays the
    host's: ``start()`` / ``close()`` on a :class:`RawTerminalKeys` are
    called by whoever built it, exactly as without the wrapper.  ``clock``
    is the time seam (default :func:`time.monotonic`), the same replaceable
    reading :meth:`~motui.app.TUI.clock` follows, so a test can drive
    exact stamps.
    """

    __slots__ = ("_clock", "_path", "_source", "_start")

    def __init__(
        self,
        source: KeySource,
        path: str | Path,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._source = source
        self._path = Path(path)
        self._clock = time.monotonic if clock is None else clock
        self._start = self._clock()
        # The recording starts here: a fresh file, so the stamps below are
        # relative to the first read of this session and never to a stale
        # one.  Append-per-event keeps the working set empty between events.
        with self._path.open("w", encoding="utf-8", newline="\n"):
            pass

    def __repr__(self) -> str:
        return f"RecordingKeys(source={self._source!r}, path={self._path!r})"

    async def read(self) -> Key | Paste | None:
        """The source's next event, recorded; ``None`` (EOF) is not recorded."""
        event = await self._source.read()
        if event is None:
            return None
        ms = round((self._clock() - self._start) * 1000)
        with self._path.open("a", encoding="utf-8", newline="\n") as sink:
            sink.write(encode_event(ms, event) + "\n")
        return event


class ReplayKeys:
    """A key source that replays a :class:`RecordingKeys` file.

    ``ReplayKeys(path, speed=1.0)`` reads the recording lazily -- the file
    opens on the first ``read()`` and is read line by line -- and hands each
    event out after waiting the milliseconds since the previous one, scaled
    by ``speed``: ``speed=1.0`` is real time, ``2.0`` twice as fast, and
    ``speed=0`` skips the wait entirely (:func:`asyncio.sleep` is never
    called), which is what a test or the piped demo runs on.  The opening
    event waits its own stamp -- the silence before the session's first
    input is part of the recording -- and a stamp that goes backwards (two
    recordings concatenated by hand) waits nothing.

    The event sequence ends with the file: ``read()`` answers ``None`` at
    EOF and every read after it, like every source at end of stream.  A
    malformed line raises :class:`ValueError` naming its line number (and
    closes the file; the earlier events stay read).  A negative ``speed``
    raises :class:`ValueError` at construction -- there is no meaningful
    "backwards in time" replay.
    """

    __slots__ = ("_done", "_lineno", "_path", "_previous", "_sink", "_speed")

    def __init__(self, path: str | Path, *, speed: float = 1.0) -> None:
        if speed < 0:
            raise ValueError(f"replay speed must be >= 0, got {speed!r}")
        self._path = Path(path)
        self._speed = speed
        self._sink: TextIO | None = None
        self._lineno = 0
        self._previous = 0  # the stamp of the last event served (ms)
        self._done = False

    def __repr__(self) -> str:
        return f"ReplayKeys(path={self._path!r}, speed={self._speed})"

    async def read(self) -> Key | Paste | None:
        """The next recorded event (after its wait), or ``None`` at EOF."""
        if self._done:
            return None
        if self._sink is None:
            self._sink = self._path.open("r", encoding="utf-8")
        for line in self._sink:
            self._lineno += 1
            try:
                ms, event = decode_event(line.rstrip("\n"), self._lineno)
            except ValueError:
                self._close()  # a bad line ends the replay: no handle lingers
                raise
            delay = (ms - self._previous) * self._speed / 1000
            self._previous = ms
            if delay > 0:
                await asyncio.sleep(delay)
            return event
        self._close()
        return None

    def _close(self) -> None:
        """Close the file and mark the sequence exhausted (EOF forever)."""
        if self._sink is not None:
            self._sink.close()
            self._sink = None
        self._done = True

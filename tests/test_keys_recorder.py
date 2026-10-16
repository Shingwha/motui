"""Tests for mocode_tui.keys.recorder (RecordingKeys / ReplayKeys).

The pure pair is pinned first -- the JSONL shape ``encode_event`` writes,
the round trip of every event shape through ``decode_event``, and the
``ValueError`` a bad line raises with its line number.  Then the two
sources: a scripted recording read back verbatim, the EOF semantics (a
one-shot ``None`` passes through and is never recorded), the pacing
arithmetic under a patched sleep, and ``speed=0``'s zero-wait contract
(measured, never slept).
"""

import json
import time

import pytest

from mocode_tui.core.events import Key, KeySource, MouseEvent, Paste, ScriptedKeys
from mocode_tui.keys import RecordingKeys, ReplayKeys
from mocode_tui.keys.recorder import decode_event, encode_event

#: One event of each shape the recorder must carry, report classes included.
EVENTS = [
    Key("c-f"),
    Key("中", "中"),
    Paste("a paste with\nthree lines"),
    MouseEvent("left", button=0, x=3, y=4, kind="press"),
    MouseEvent("left", button=0, x=3, y=4, kind="release"),
    MouseEvent("none", button=0, x=9, y=2, kind="motion"),
]


def _clock_from(stamps: list[float]):
    """A fake clock reading ``stamps`` in order (constructor start included)."""
    readings = iter(stamps)
    return lambda: next(readings)


async def _drain(source) -> list:
    """Every event a source serves until its first EOF."""
    out = []
    while True:
        event = await source.read()
        if event is None:
            return out
        out.append(event)


def _record(tmp_path, events, stamps):
    """A recorded file: ``events`` at ``stamps`` (the start stamp first)."""
    path = tmp_path / "session.jsonl"
    recorder = RecordingKeys(ScriptedKeys(events), path, clock=_clock_from(stamps))
    return path, recorder


async def _recorded(tmp_path, events, stamps):
    """Record ``events`` and return the file path (the whole first step)."""
    path, recorder = _record(tmp_path, events, stamps)
    assert await _drain(recorder) == events
    return path


# --- the pure pair -------------------------------------------------------------


def test_the_wire_shape_is_the_one_the_recipe_documents():
    """The JSONL line verbatim: ms plus the model's own fields."""
    assert json.loads(encode_event(125, Key("c-f"))) == {
        "ms": 125,
        "event": {"kind": "key", "name": "c-f", "char": ""},
    }
    assert json.loads(encode_event(0, Key("中", "中"))) == {
        "ms": 0,
        "event": {"kind": "key", "name": "中", "char": "中"},
    }
    assert json.loads(encode_event(7, Paste("hi"))) == {
        "ms": 7,
        "event": {"kind": "paste", "text": "hi"},
    }
    # A mouse report's own kind rides as ``report``: ``kind`` is the type.
    assert json.loads(encode_event(9, MouseEvent("left", button=0, x=3, y=4, kind="press"))) == {
        "ms": 9,
        "event": {
            "kind": "mouse",
            "name": "left",
            "button": 0,
            "x": 3,
            "y": 4,
            "report": "press",
        },
    }


def test_the_pure_pair_round_trips_every_event_shape():
    """encode -> decode is the identity, stamps and all (the three types)."""
    for ms, event in enumerate(EVENTS):
        assert decode_event(encode_event(ms * 13, event), 1) == (ms * 13, event)


@pytest.mark.parametrize(
    "line",
    [
        "",
        "{",
        "[]",
        '"text"',
        '{"event": {"kind": "key", "name": "a"}}',  # no ms
        '{"ms": "1", "event": {"kind": "key", "name": "a"}}',  # ms not an integer
        '{"ms": true, "event": {"kind": "key", "name": "a"}}',  # bool is not an ms
        '{"ms": 0}',  # no event
        '{"ms": 0, "event": []}',
        '{"ms": 0, "event": {}}',  # no kind
        '{"ms": 0, "event": {"kind": "wolf"}}',
        '{"ms": 0, "event": {"kind": "key", "name": 3}}',  # name not a string
        '{"ms": 0, "event": {"kind": "paste", "text": null}}',
        '{"ms": 0, "event": {"kind": "mouse", "name": "left", "button": 0, "x": 1, "y": 1}}',  # no report
        '{"ms": 0, "event": {"kind": "mouse", "name": "left", "button": 0, "x": 1, "y": 1, "report": "tap"}}',
        '{"ms": 0, "event": {"kind": "mouse", "name": "left", "button": "0", "x": 1, "y": 1, "report": "press"}}',
        '{"ms": 0, "event": {"kind": "mouse", "name": "left", "button": 0, "x": 1.5, "y": 1, "report": "motion"}}',
    ],
)
def test_a_bad_line_raises_value_error_naming_its_number(line):
    """Every malformed line is one ValueError whose message carries the line."""
    with pytest.raises(ValueError, match="recording line 7"):
        decode_event(line, 7)


# --- recording and replay ------------------------------------------------------


def test_both_sources_are_key_sources(tmp_path):
    """The pair satisfies the structural protocol (async ``read``)."""
    assert isinstance(ReplayKeys(tmp_path / "none.jsonl"), KeySource)
    assert isinstance(RecordingKeys(ScriptedKeys([]), tmp_path / "out.jsonl"), KeySource)


async def test_a_recording_round_trips_through_the_file(tmp_path):
    """The three-step recipe: scripted source -> JSONL -> ReplayKeys(speed=0)."""
    path = await _recorded(tmp_path, EVENTS, [10.0, 10.25, 10.375, 10.4, 11.0, 11.5, 12.0])
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines == [
        encode_event(250, EVENTS[0]),
        encode_event(375, EVENTS[1]),
        encode_event(400, EVENTS[2]),
        encode_event(1000, EVENTS[3]),
        encode_event(1500, EVENTS[4]),
        encode_event(2000, EVENTS[5]),
    ]
    source = ReplayKeys(path, speed=0)
    assert await _drain(source) == EVENTS
    assert await source.read() is None  # exhausted: EOF forever


async def test_eof_is_not_recorded_and_a_one_shot_eof_passes_through(tmp_path):
    """``None`` from the source is returned as it came -- no line for it."""
    path, recorder = _record(tmp_path, [EVENTS[0], None, EVENTS[1]], [0.0, 1.0, 1.0, 2.0])
    assert await recorder.read() == EVENTS[0]
    assert await recorder.read() is None  # the one-shot EOF, untouched
    assert await recorder.read() == EVENTS[1]
    assert await recorder.read() is None  # and the source's final EOF
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["event"]["name"] for line in lines] == ["c-f", "中"]


async def test_an_empty_recording_eofs_at_once(tmp_path):
    """A recording with no events is an exhausted source, not an error."""
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    assert await ReplayKeys(path, speed=0).read() is None


async def test_the_recording_is_fresh_at_each_construction(tmp_path):
    """The constructor starts the recording: one path holds one session."""
    path = tmp_path / "session.jsonl"
    path.write_text("stale\n", encoding="utf-8")
    recorder = RecordingKeys(
        ScriptedKeys([EVENTS[0]]), path, clock=_clock_from([0.0, 0.5])
    )
    assert await recorder.read() == EVENTS[0]
    assert path.read_text(encoding="utf-8") == encode_event(500, EVENTS[0]) + "\n"


async def test_replay_paces_by_the_stamps_times_speed(tmp_path, monkeypatch):
    """The waits are the stamp deltas scaled by ``speed`` -- pinned, not slept.

    ``asyncio.sleep`` is replaced with a collector for the duration of the
    test, so the arithmetic is asserted exactly with zero wall time.
    """
    import mocode_tui.keys.recorder as recorder_module

    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(recorder_module.asyncio, "sleep", fake_sleep)
    path = await _recorded(tmp_path, EVENTS[:3], [0.0, 0.0, 0.1, 0.25])
    assert await _drain(ReplayKeys(path, speed=2.0)) == EVENTS[:3]
    # Event 1 is stamped 0: no wait.  Then 100ms and 150ms of stamps, doubled.
    assert sleeps == [pytest.approx(0.2), pytest.approx(0.3)]
    # Speed zero skips every wait, including the ones above: no sleep call.
    sleeps.clear()
    assert await _drain(ReplayKeys(path, speed=0)) == EVENTS[:3]
    assert sleeps == []


async def test_replay_speed_zero_never_waits_even_for_a_minute_of_stamps(tmp_path):
    """``speed=0`` is the zero-delay contract: 60s of stamps, no wall time.

    The assertion is the measured elapsed time -- the recording holds two
    events a minute apart, and the whole replay must finish in well under a
    second (it would take 60s at ``speed=1``).
    """
    path = await _recorded(tmp_path, EVENTS[:2], [0.0, 0.0, 60.0])
    source = ReplayKeys(path, speed=0)
    started = time.monotonic()
    assert await _drain(source) == EVENTS[:2]
    elapsed = time.monotonic() - started
    assert elapsed < 0.5, f"speed=0 waited {elapsed:.3f}s"


async def test_a_bad_line_mid_file_raises_with_its_number(tmp_path):
    """The file's own line number is in the error; earlier events stay read."""
    path = tmp_path / "session.jsonl"
    path.write_text(
        encode_event(0, EVENTS[0]) + "\n" + "{ not a record\n", encoding="utf-8"
    )
    source = ReplayKeys(path, speed=0)
    assert await source.read() == EVENTS[0]
    with pytest.raises(ValueError, match="recording line 2"):
        await source.read()


async def test_a_backwards_stamp_waits_nothing(tmp_path, monkeypatch):
    """A hand-concatenated recording degrades to no wait, never to a crash."""
    import mocode_tui.keys.recorder as recorder_module

    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(recorder_module.asyncio, "sleep", fake_sleep)
    path = tmp_path / "joined.jsonl"
    path.write_text(
        encode_event(5000, EVENTS[0]) + "\n" + encode_event(0, EVENTS[1]) + "\n",
        encoding="utf-8",
    )
    assert await _drain(ReplayKeys(path, speed=1.0)) == EVENTS[:2]
    assert sleeps == [pytest.approx(5.0)]  # the second stamp goes backwards: no wait


def test_a_negative_speed_is_refused_at_construction(tmp_path):
    """Backwards in time is not a replay: the constructor refuses it."""
    with pytest.raises(ValueError, match="speed"):
        ReplayKeys(tmp_path / "x.jsonl", speed=-1.0)

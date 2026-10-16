"""Fuzz the decoder: random bytes under fixed seeds, invariants not examples.

No hypothesis, no new dependency: ``random.Random(seed)`` walks a fixed
matrix of byte streams -- escape bytes, CSI fragments, UTF-8 lead and
continuation bytes, a fragment cut at the stream's exact length -- and
pins what the decoder must never do: raise, leave ``pending()`` anything
but a bool, or settle into a state ``finish()`` cannot clear.  One more
test holds the equivalence the incremental design promises: feeding the
same stream one byte at a time delivers exactly the events the whole
stream does -- for every case in the matrix but the ones that split a
bracketed paste's end marker, the one divergence the wave found and pinned
with a strict xfail instead of silently accepting (see that test).
"""

import random

import pytest

from mocode_tui.core.events import Key, MouseEvent, Paste
from mocode_tui.keys import KeyDecoder

#: The fixed seed matrix: one stream per seed, ``(seed, length)``.  The
#: lengths walk from the empty stream to 512 bytes; the seeds are fixed so
#: a failure is a recipe, not a coin toss.
CASES = tuple(
    zip(
        (1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597,
         2584, 4181, 6765, 10946, 17711, 28657, 46368, 75025),  # 24 seeds
        (0, 1, 2, 3, 7, 15, 31, 63, 100, 127, 200, 255, 300, 333, 377, 400,
         420, 440, 460, 480, 496, 504, 508, 512),  # 0 .. 512
    )
)

#: The alphabet the streams are built from, whole fragments at a time so
#: escape sequences, CSI bodies, SGR mouse reports, bracketed paste and
#: multi-byte UTF-8 actually appear -- and get cut mid-sequence when the
#: stream's length lands inside a fragment.
FRAGMENTS = (
    b"\x1b",
    b"\x1b[",
    b"\x1b[<",
    b"\x1b[200~",
    b"\x1b[201~",
    b"\x1b[1;2A",
    b"\x1b[<0;5;5M",
    b"\x1b[<35;9;9M",
    b"\x1b[<64;1;1M",
    b"\x1b[<0;3;xM",
    b"\x1b[5~",
    b"\x1b[3;5-~",
    b"~",
    b";",
    b"<",
    b"m",
    b"\r\n",
    b"\t",
    b"\x7f",
    b"\x00\x03",
    b"ab ",
    "中".encode(),
    b"\xc3",  # a lead byte with no continuation: broken UTF-8 on purpose
    b"\xe4\xb8",
    b"\xf0\x9f\x8f",
    b"\x80\xbf",  # continuation bytes with no lead
    b"\xff\xfe",
)


def stream(rng: random.Random, length: int) -> bytes:
    """One deterministic stream of exactly ``length`` bytes from the alphabet."""
    out = bytearray()
    while len(out) < length:
        out += rng.choice(FRAGMENTS)
    del out[length:]  # a fragment may overshoot: cut the stream at its length
    return bytes(out)


def decode_in_chunks(data: bytes, rng: random.Random) -> tuple[list, KeyDecoder]:
    """Feed ``data`` in random-sized chunks; answer the events and the decoder."""
    decoder = KeyDecoder()
    events: list = []
    index = 0
    while index < len(data):
        size = rng.randrange(1, 18)
        events.extend(decoder.feed(data[index : index + size]))
        index += size
    return events, decoder


def assert_events(items) -> None:
    """Whatever came out is one of the three event shapes -- nothing else."""
    for item in items:
        assert isinstance(item, (Key, MouseEvent, Paste)), repr(item)


def carries_a_paste_round_trip(data: bytes) -> bool:
    """Whether ``data`` opens a bracketed paste and carries its end marker.

    The predicate behind the one known divergence between the two feeding
    paths (``test_a_split_paste_end_marker...`` below): a stream that opens
    a paste and closes it later splits the ``ESC [ 201 ~`` marker across
    byte-wise feed boundaries, and today's decoder swallows a split marker
    into the payload instead of closing the paste.
    """
    start = data.find(b"\x1b[200~")
    return start >= 0 and b"\x1b[201~" in data[start + len(b"\x1b[200~") :]


def test_the_matrix_covers_the_promised_seeds_and_lengths():
    """The fixed table: >= 20 cases, the empty stream and 512 bytes present."""
    assert len(CASES) >= 20
    assert len({seed for seed, _ in CASES}) == len(CASES)  # distinct seeds
    lengths = [length for _, length in CASES]
    assert lengths[0] == 0 and lengths[-1] == 512
    assert all(0 <= length <= 512 for length in lengths)


def test_random_bytes_never_raise_and_never_leave_a_state_finish_cannot_clear():
    """The total machine: bytes in, well-typed events out, clean end state.

    Chunked randomly (1..17 bytes per feed), because the boundaries are
    where incremental state lives.  ``pending()`` must stay a bool through
    the whole walk, and after ``finish()`` the decoder must be empty: not
    pending any more, and a second ``finish()`` has nothing left to hand
    over.
    """
    for seed, length in CASES:
        rng = random.Random(seed)
        data = stream(rng, length)
        events, decoder = decode_in_chunks(data, rng)
        assert_events(events)
        assert isinstance(decoder.pending(), bool)
        tail = decoder.finish()
        assert_events(tail)
        assert decoder.pending() is False  # the stream is settled
        assert decoder.finish() == []  # and comes back empty, state cleared


def test_byte_by_byte_feeding_matches_whole_block_feeding():
    """The incremental promise, over every case it can hold on.

    One byte per feed (and one whole-block feed) must deliver exactly the
    same event sequence -- settle at the end included -- because the state
    machine carries escape and UTF-8 state across feeds rather than
    resolving at boundaries.  The paste-round-trip cases cannot hold the
    promise today (the split-marker bug pinned by the strict xfail below);
    every other case in the matrix is compared here, and the comparison
    count is asserted so the filter can never empty the test.
    """
    compared = 0
    for seed, length in CASES:
        data = stream(random.Random(seed), length)
        if carries_a_paste_round_trip(data):
            continue  # pinned by the strict xfail below -- reported, not hidden
        whole = KeyDecoder()
        whole_events = whole.feed(data) + whole.finish()
        bytewise = KeyDecoder()
        one_byte_events: list = []
        for index in range(len(data)):
            one_byte_events.extend(bytewise.feed(data[index : index + 1]))
        one_byte_events.extend(bytewise.finish())
        assert one_byte_events == whole_events, f"seed {seed}, length {length}"
        compared += 1
    assert compared >= 10  # the matrix really is exercising the promise


@pytest.mark.xfail(
    strict=True,
    reason=(
        "known decoder bug, out of this wave's scope (decode's behavior is "
        "on the do-not-touch list): a bracketed paste's end marker split "
        "across feeds is swallowed into the payload instead of closing the "
        "paste.  Fix the decoder and this strict xfail turns into an XPASS "
        "-- then fold these cases back into the equivalence test above."
    ),
)
def test_a_split_paste_end_marker_still_closes_the_paste():
    """The pinned divergence: a split ``ESC [ 201 ~`` must close the paste.

    The minimal repro first -- three feeds that split the marker, expected
    ``[Paste("ab"), Key("x"), Key("y")]`` -- then the matrix cases that
    carry a paste round trip, which differ today by exactly this bug (the
    payload keeps the marker bytes and everything after it, and the events
    past the paste vanish from the stream until ``finish()``).
    """
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[200~ab\x1b[2") == []
    assert decoder.feed(b"01~xy") == []
    assert decoder.finish() == [Paste("ab"), Key("x", "x"), Key("y", "y")]
    for seed, length in CASES:
        data = stream(random.Random(seed), length)
        if not carries_a_paste_round_trip(data):
            continue
        whole = KeyDecoder()
        whole_events = whole.feed(data) + whole.finish()
        bytewise = KeyDecoder()
        one_byte_events: list = []
        for index in range(len(data)):
            one_byte_events.extend(bytewise.feed(data[index : index + 1]))
        one_byte_events.extend(bytewise.finish())
        assert one_byte_events == whole_events, f"seed {seed}, length {length}"


def test_a_knife_edge_stream_of_csi_parameters_stays_total_and_settles():
    """A degenerate CSI body is dropped, degraded and settled -- never fatal.

    ``ESC [`` followed by thousands of innocent parameter bytes is the one
    shape whose *pending state* grows linearly; the public contract is what
    the decoder asserts here: it stays total, ``settle()`` resolves the
    pending sequence to escape plus its re-read parameters, and the state
    clears.
    """
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[" + b"1;" * 4000) == []
    assert decoder.pending() is True
    settled = decoder.settle()
    assert settled[0] == Key("escape")  # the introducer degrades, never hangs
    assert all(isinstance(event, Key) for event in settled)
    assert decoder.pending() is False
    assert decoder.finish() == []

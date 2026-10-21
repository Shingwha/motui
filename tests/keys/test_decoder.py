"""The key decoder: printable and control keys, CSI/SS3, modifiers, mouse
reports, paste and incremental assembly.

The decoder is a pure, total bytes-to-events state machine: it assembles
UTF-8 and escape sequences across feeds, degrades unknown input, and never
raises.  Two invariants close the file: arbitrary bytes stay total, and
byte-at-a-time feeding equals whole-block feeding.
"""

from __future__ import annotations

import random

import pytest

from motui.core.events import (
    Event,
    FocusEvent,
    KeyEvent,
    MouseEvent,
    PasteEvent,
    ResizeEvent,
)
from motui.core import KeyDecoder

SHIFT = frozenset({"shift"})
ALT = frozenset({"alt"})
CTRL = frozenset({"ctrl"})


def feed(*chunks: bytes) -> list:
    decoder = KeyDecoder()
    events: list = []
    for chunk in chunks:
        events.extend(decoder.feed(chunk))
    return events


def test_printable_and_wide_characters_are_their_own_key():
    assert feed(b"ab") == [KeyEvent("a", "a"), KeyEvent("b", "b")]
    assert feed("\u4e2d\u6587".encode()) == [
        KeyEvent("\u4e2d", "\u4e2d"),
        KeyEvent("\u6587", "\u6587"),
    ]
    assert feed(b" ") == [KeyEvent("space", " ")]


def test_cr_is_enter_and_lf_is_c_j():
    assert feed(b"\r") == [KeyEvent("enter")]
    assert feed(b"\n") == [KeyEvent("c-j")]
    assert feed(b"\t") == [KeyEvent("tab")]
    assert feed(b"\x7f") == [KeyEvent("backspace")]


def test_control_bytes_map_to_c_a_through_c_z():
    assert feed(b"\x01") == [KeyEvent("c-a")]
    assert feed(b"\x03") == [KeyEvent("c-c")]
    assert feed(b"\x1a") == [KeyEvent("c-z")]
    assert feed(b"\x00") == []
    assert feed(b"\x1c\x1d\x1e\x1f") == []
    assert feed(b"a\x00b") == [KeyEvent("a", "a"), KeyEvent("b", "b")]


def test_csi_letter_finals_name_navigation_and_f1_through_f4():
    assert feed(b"\x1b[A") == [KeyEvent("up")]
    assert feed(b"\x1b[B") == [KeyEvent("down")]
    assert feed(b"\x1b[C") == [KeyEvent("right")]
    assert feed(b"\x1b[D") == [KeyEvent("left")]
    assert feed(b"\x1b[H") == [KeyEvent("home")]
    assert feed(b"\x1b[F") == [KeyEvent("end")]
    assert feed(b"\x1b[P") == [KeyEvent("f1")]
    assert feed(b"\x1b[S") == [KeyEvent("f4")]


def test_focus_reports_decode_as_focus_events():
    assert feed(b"\x1b[I") == [FocusEvent(True)]
    assert feed(b"\x1b[O") == [FocusEvent(False)]


def test_csi_tilde_family_navigation_and_function_keys():
    assert feed(b"\x1b[1~") == [KeyEvent("home")]
    assert feed(b"\x1b[2~") == [KeyEvent("insert")]
    assert feed(b"\x1b[3~") == [KeyEvent("delete")]
    assert feed(b"\x1b[5~") == [KeyEvent("page_up")]
    assert feed(b"\x1b[6~") == [KeyEvent("page_down")]
    expected = {
        11: "f1",
        12: "f2",
        13: "f3",
        14: "f4",
        15: "f5",
        17: "f6",
        18: "f7",
        19: "f8",
        20: "f9",
        21: "f10",
        23: "f11",
        24: "f12",
    }
    for code, name in expected.items():
        assert feed(f"\x1b[{code}~".encode()) == [KeyEvent(name)]


def test_ss3_keys_and_an_unknown_ss3_degrades():
    expected = {
        b"\x1bOA": "up",
        b"\x1bOB": "down",
        b"\x1bOC": "right",
        b"\x1bOD": "left",
        b"\x1bOH": "home",
        b"\x1bOF": "end",
        b"\x1bOP": "f1",
        b"\x1bOS": "f4",
    }
    for sequence, name in expected.items():
        assert feed(sequence) == [KeyEvent(name)]
    assert feed(b"\x1bOZ") == [
        KeyEvent("escape"),
        KeyEvent("O", "O"),
        KeyEvent("Z", "Z"),
    ]


def test_shift_tab_is_a_chord():
    assert feed(b"\x1b[Z") == [KeyEvent("s-tab", "", SHIFT)]
    assert feed(b"\x1b[1;6Z") == [
        KeyEvent("c-s-tab", "", frozenset({"ctrl", "shift"}))
    ]


def test_modifier_parameters_fill_the_key_and_the_set():
    cases = [
        (b"\x1b[1;2A", "s-up", SHIFT),
        (b"\x1b[1;3A", "a-up", ALT),
        (b"\x1b[1;4A", "a-s-up", frozenset({"alt", "shift"})),
        (b"\x1b[1;5A", "c-up", CTRL),
        (b"\x1b[1;6A", "c-s-up", frozenset({"ctrl", "shift"})),
        (b"\x1b[1;7A", "c-a-up", frozenset({"ctrl", "alt"})),
        (b"\x1b[1;8A", "c-a-s-up", frozenset({"ctrl", "alt", "shift"})),
        (b"\x1b[1;9A", "super-up", frozenset({"super"})),
        (b"\x1b[3;5~", "c-delete", CTRL),
        (b"\x1b[1;2H", "s-home", SHIFT),
    ]
    for sequence, key, modifiers in cases:
        assert feed(sequence) == [KeyEvent(key, "", modifiers)]


def test_kitty_codepoint_forms():
    assert feed(b"\x1b[97u") == [KeyEvent("a", "a")]
    assert feed(b"\x1b[97;5u") == [KeyEvent("c-a", "", CTRL)]
    assert feed(b"\x1b[13u") == [KeyEvent("enter")]
    assert feed(b"\x1b[32u") == [KeyEvent("space", " ")]
    assert feed(b"\x1b[97;1:2u") == [KeyEvent("a", "a", frozenset(), "repeat")]
    assert feed(b"\x1b[97;1:3u") == [KeyEvent("a", "a", frozenset(), "release")]
    assert feed(b"\x1b[97;2u") == [KeyEvent("a", "a", SHIFT)]
    assert feed(b"\x1b[1092u") == [KeyEvent("\u0444", "\u0444")]


def test_modify_other_keys_form():
    assert feed(b"\x1b[27;5;13~") == [KeyEvent("c-enter", "", CTRL)]
    assert feed(b"\x1b[27;3;97~") == [KeyEvent("a-a", "", ALT)]
    assert feed(b"\x1b[27;1;97~") == [KeyEvent("a", "a")]
    assert feed(b"\x1b[27;5;27~") == [KeyEvent("c-escape", "", CTRL)]


def test_resize_reports_decode_and_malformed_ones_drop():
    assert feed(b"\x1b[8;24;80t") == [ResizeEvent(80, 24)]
    assert feed(b"\x1b[8;40;120t") == [ResizeEvent(120, 40)]
    assert feed(b"\x1b[8;24t") == []


def test_unknown_sequences_are_dropped():
    assert feed(b"\x1b[?25h") == []
    assert feed(b"\x1b[999~") == []
    assert feed(b"\x1b[1114112u") == []


def test_sgr_wheel_reports_decode():
    assert feed(b"\x1b[<64;10;5M") == [MouseEvent("wheel_up", 9, 4, "wheel")]
    assert feed(b"\x1b[<65;10;5m") == [MouseEvent("wheel_down", 9, 4, "wheel")]
    assert feed(b"\x1b[<81;3;9m") == [
        MouseEvent("wheel_down", 2, 8, "wheel", frozenset({"ctrl"}))
    ]
    assert feed(b"\x1b[<66;3;9M") == [MouseEvent("wheel_left", 2, 8, "wheel")]
    assert feed(b"\x1b[<67;3;9M") == [MouseEvent("wheel_right", 2, 8, "wheel")]
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[<64;1") == []
    assert decoder.feed(b"0;5M") == [MouseEvent("wheel_up", 9, 4, "wheel")]


def test_sgr_button_presses_and_modifiers():
    assert feed(b"\x1b[<0;5;5M") == [MouseEvent("left", 4, 4, "press")]
    assert feed(b"\x1b[<1;3;7M") == [MouseEvent("middle", 2, 6, "press")]
    assert feed(b"\x1b[<2;3;7M") == [MouseEvent("right", 2, 6, "press")]
    assert feed(b"\x1b[<6;3;7M") == [
        MouseEvent("right", 2, 6, "press", frozenset({"shift"}))
    ]
    assert feed(b"\x1b[<18;3;7M") == [
        MouseEvent("right", 2, 6, "press", frozenset({"ctrl"}))
    ]


def test_sgr_release_motion_and_button_free_motion():
    assert feed(b"\x1b[<0;5;5m") == [MouseEvent("left", 4, 4, "release")]
    assert feed(b"\x1b[<32;2;5M") == [MouseEvent("left", 1, 4, "motion")]
    assert feed(b"\x1b[<38;3;7M") == [
        MouseEvent("right", 2, 6, "motion", frozenset({"shift"}))
    ]
    assert feed(b"\x1b[<35;2;5M") == [MouseEvent("none", 1, 4, "motion")]
    assert feed(b"\x1b[<3;5;5M") == [MouseEvent("none", 4, 4, "press")]


def test_x10_reports_decode_across_feeds():
    assert feed(b"\x1b[M %%") == [MouseEvent("left", 4, 4, "press")]
    assert feed(b"\x1b[M#%%") == [MouseEvent("none", 4, 4, "release")]
    assert feed(b"\x1b[M@%%") == [MouseEvent("left", 4, 4, "motion")]
    assert feed(b"\x1b[M`%%") == [MouseEvent("wheel_up", 4, 4, "wheel")]
    decoder = KeyDecoder()
    for byte in b"\x1b[M %%":
        events = decoder.feed(bytes([byte]))
    assert events == [MouseEvent("left", 4, 4, "press")]


def test_urxvt_1015_reports_decode():
    assert feed(b"\x1b[0;5;5M") == [MouseEvent("left", 4, 4, "press")]
    assert feed(b"\x1b[0;5;5m") == [MouseEvent("left", 4, 4, "release")]
    assert feed(b"\x1b[64;2;3M") == [MouseEvent("wheel_up", 1, 2, "wheel")]
    assert feed(b"\x1b[35;2;3M") == [MouseEvent("none", 1, 2, "motion")]


def test_malformed_mouse_reports_drop():
    assert feed(b"\x1b[<64;10M") == []
    assert feed(b"\x1b[<M") == []
    assert feed(b"\x1b[<;1;1M") == []
    assert feed(b"\x1b[<1;2;3;4M") == []


def test_bracketed_paste_is_one_event_never_reinterpreted():
    assert feed(b"\x1b[200~hello\r\nworld\x1b[201~") == [PasteEvent("hello\r\nworld")]
    payload = b"a\x1bb\x1b[201"
    assert feed(b"\x1b[200~" + payload + b"\x1b[201~") == [PasteEvent("a\x1bb\x1b[201")]
    assert feed(b"\x1b[200~\x1b[201~") == [PasteEvent("")]


def test_paste_spans_feeds_and_finish_closes_an_unclosed_one():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[200~ab") == []
    assert decoder.feed(b"cd") == []
    assert decoder.pending() is False
    assert decoder.feed(b"\x1b[201~") == [PasteEvent("abcd")]
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[200~raw\r\ntext") == []
    assert decoder.finish() == [PasteEvent("raw\r\ntext")]


def test_a_paste_end_marker_split_across_feeds_still_closes_the_paste():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[200~ab\x1b[2") == []
    assert decoder.feed(b"01~xy") == [
        PasteEvent("ab"),
        KeyEvent("x", "x"),
        KeyEvent("y", "y"),
    ]
    assert decoder.finish() == []
    streamed = b"\x1b[200~ab\x1b[201~xy"
    whole = KeyDecoder()
    whole_events = whole.feed(streamed) + whole.finish()
    for cut in range(1, len(streamed)):
        split = KeyDecoder()
        events = split.feed(streamed[:cut]) + split.feed(streamed[cut:]) + split.finish()
        assert events == whole_events
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[200~a\x1b[20") == []
    assert decoder.feed(b"Q\x1b[201~") == [PasteEvent("a\x1b[20Q")]
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[200~raw\x1b[20") == []
    assert decoder.finish() == [PasteEvent("raw\x1b[20")]


def test_a_stray_paste_end_marker_is_dropped():
    assert feed(b"\x1b[201~") == []
    assert feed(b"a\x1b[201~b") == [KeyEvent("a", "a"), KeyEvent("b", "b")]


def test_lone_escape_stays_pending_until_settled():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b") == []
    assert decoder.pending() is True
    assert decoder.settle() == [KeyEvent("escape")]
    assert decoder.pending() is False
    assert decoder.settle() == []
    assert feed(b"a\x1bb") == [
        KeyEvent("a", "a"),
        KeyEvent("escape"),
        KeyEvent("b", "b"),
    ]


def test_escape_escape_resolves_the_first_and_restarts():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b\x1b") == [KeyEvent("escape")]
    assert decoder.settle() == [KeyEvent("escape")]
    assert feed(b"\x1b\x1b[A") == [KeyEvent("escape"), KeyEvent("up")]


def test_incomplete_csi_degrades_to_escape_plus_literal_parameters():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[") == []
    assert decoder.pending() is True
    assert decoder.settle() == [KeyEvent("escape")]
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[1;5") == []
    assert decoder.settle() == [
        KeyEvent("escape"),
        KeyEvent("1", "1"),
        KeyEvent(";", ";"),
        KeyEvent("5", "5"),
    ]
    assert decoder.feed(b"q") == [KeyEvent("q", "q")]


def test_incomplete_ss3_and_x10_release_their_introducers():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1bO") == []
    assert decoder.settle() == [KeyEvent("escape"), KeyEvent("O", "O")]
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[M ") == []
    assert decoder.settle() == [
        KeyEvent("escape"),
        KeyEvent("[", "["),
        KeyEvent("M", "M"),
        KeyEvent("space", " "),
    ]


def test_a_csi_aborted_by_an_invalid_byte_degrades_and_resumes():
    assert feed(b"\x1b[1\r") == [
        KeyEvent("escape"),
        KeyEvent("1", "1"),
        KeyEvent("enter"),
    ]
    assert feed(b"\x1bOX") == [
        KeyEvent("escape"),
        KeyEvent("O", "O"),
        KeyEvent("X", "X"),
    ]


def test_sequences_assemble_across_feeds_byte_by_byte():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b") == []
    assert decoder.feed(b"[") == []
    assert decoder.feed(b"A") == [KeyEvent("up")]
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b") == []
    assert decoder.feed(b"[5~") == [KeyEvent("page_up")]
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b") == []
    assert decoder.feed(b"O") == []
    assert decoder.feed(b"P") == [KeyEvent("f1")]
    decoder.feed(b"\x1b[200~x")
    assert decoder.pending() is False


def test_utf8_assembles_across_feeds_and_invalid_bytes_degrade():
    decoder = KeyDecoder()
    assert decoder.feed(b"\xe4\xb8") == []
    assert decoder.feed(b"\xad") == [KeyEvent("\u4e2d", "\u4e2d")]
    assert feed(b"\xff") == [KeyEvent("\ufffd", "\ufffd")]
    decoder = KeyDecoder()
    assert decoder.feed(b"\xe4\xb8") == []
    assert decoder.finish() == [KeyEvent("\ufffd", "\ufffd")]


def test_feed_rejects_non_bytes_input():
    with pytest.raises(TypeError):
        KeyDecoder().feed("abc")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        KeyDecoder().feed(bytearray(b"abc"))  # type: ignore[arg-type]


CASES = tuple(
    zip(
        (1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597,
         2584, 4181, 6765, 10946, 17711, 28657, 46368, 75025),
        (0, 1, 2, 3, 7, 15, 31, 63, 100, 127, 200, 255, 300, 333, 377, 400,
         420, 440, 460, 480, 496, 504, 508, 512),
    )
)

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
    "\u4e2d".encode(),
    b"\xc3",
    b"\xe4\xb8",
    b"\xf0\x9f\x8f",
    b"\x80\xbf",
    b"\xff\xfe",
)


def stream(rng: random.Random, length: int) -> bytes:
    out = bytearray()
    while len(out) < length:
        out += rng.choice(FRAGMENTS)
    del out[length:]
    return bytes(out)


def assert_events(items) -> None:
    for item in items:
        assert isinstance(
            item, (KeyEvent, MouseEvent, PasteEvent, ResizeEvent, FocusEvent)
        ), repr(item)
        assert isinstance(item, Event), repr(item)


def test_random_bytes_never_raise_and_finish_clears_the_state():
    for seed, length in CASES:
        rng = random.Random(seed)
        data = stream(rng, length)
        decoder = KeyDecoder()
        events: list = []
        index = 0
        while index < len(data):
            size = rng.randrange(1, 18)
            events.extend(decoder.feed(data[index : index + size]))
            index += size
        assert_events(events)
        assert isinstance(decoder.pending(), bool)
        assert_events(decoder.finish())
        assert decoder.pending() is False
        assert decoder.finish() == []


def test_byte_by_byte_feeding_matches_whole_block_feeding():
    compared = 0
    for seed, length in CASES:
        data = stream(random.Random(seed), length)
        whole = KeyDecoder()
        whole_events = whole.feed(data) + whole.finish()
        bytewise = KeyDecoder()
        one_byte_events: list = []
        for index in range(len(data)):
            one_byte_events.extend(bytewise.feed(data[index : index + 1]))
        one_byte_events.extend(bytewise.finish())
        assert one_byte_events == whole_events, (seed, length)
        compared += 1
    assert compared >= 20

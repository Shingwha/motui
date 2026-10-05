"""Tests for mocode_tui.keys.decoder (KeyDecoder) and the event model.

A pure, total ``bytes -> events`` machine -- incremental UTF-8, control names,
CSI navigation, bracketed paste, SGR mouse; nothing ever raises.
"""

import pytest

from mocode_tui.core.events import Key, KeySource, MouseEvent, Paste
from mocode_tui.keys import KeyDecoder


def feed(*chunks: bytes) -> list:
    """Decode every chunk through one decoder, in order."""
    decoder = KeyDecoder()
    out: list = []
    for chunk in chunks:
        out.extend(decoder.feed(chunk))
    return out


# --- event model --------------------------------------------------------------


def test_events_are_frozen_and_the_source_protocol_is_structural():
    assert Key("a", "a") == Key("a", "a") and Key("a", "a") != Key("a")
    assert Paste("x") == Paste("x")
    with pytest.raises(Exception):
        Key("a").name = "b"  # type: ignore[misc]

    class Source:
        async def read(self):
            return None

    assert isinstance(Source(), KeySource)


# --- printable characters and control names ------------------------------------


def test_printable_and_wide_characters_are_their_own_name():
    assert feed(b"ab") == [Key("a", "a"), Key("b", "b")]
    assert feed("中文".encode()) == [Key("中", "中"), Key("文", "文")]
    assert feed(b" ") == [Key("space", " ")]


def test_enter_tab_and_backspace():
    assert feed(b"\r") == [Key("enter")] and feed(b"\n") == [Key("enter")]
    assert feed(b"\t") == [Key("tab")]
    assert feed(b"\x7f") == [Key("backspace")]


def test_control_bytes_map_to_c_a_through_c_z():
    assert feed(b"\x01") == [Key("c-a")]
    assert feed(b"\x03") == [Key("c-c")]
    assert feed(b"\x1a") == [Key("c-z")]


def test_unlisted_control_bytes_are_dropped_not_fatal():
    assert feed(b"\x00") == []
    assert feed(b"\x1c\x1d\x1e\x1f") == []
    assert feed(b"a\x00b") == [Key("a", "a"), Key("b", "b")]


# --- CSI navigation keys -------------------------------------------------------


def test_csi_letter_finals():
    assert feed(b"\x1b[A") == [Key("up")]
    assert feed(b"\x1b[B") == [Key("down")]
    assert feed(b"\x1b[C") == [Key("right")] and feed(b"\x1b[D") == [Key("left")]
    assert feed(b"\x1b[H") == [Key("home")] and feed(b"\x1b[F") == [Key("end")]


def test_csi_tilde_family_by_first_parameter():
    assert feed(b"\x1b[3~") == [Key("delete")]
    assert feed(b"\x1b[1~") == [Key("home")] and feed(b"\x1b[4~") == [Key("end")]
    assert feed(b"\x1b[5~") == [Key("page_up")] and feed(b"\x1b[6~") == [Key("page_down")]


def test_parameters_and_modifiers_are_ignored():
    assert feed(b"\x1b[1;5A") == [Key("up")]  # modifier fields carry no meaning
    assert feed(b"\x1b[3;5~") == [Key("delete")]  # only the first parameter counts
    assert feed(b"\x1b[A\x1b[B") == [Key("up"), Key("down")]  # two per feed


def test_unknown_sequences_are_dropped():
    assert feed(b"\x1b[?25h") == []  # unknown final byte
    assert feed(b"\x1b[Z") == []  # shift+tab: outside the contract
    assert feed(b"\x1b[2~") == []  # insert: outside the contract
    assert feed(b"\x1b[24;80R") == []  # cursor position report: dropped


# --- SGR mouse reports -------------------------------------------------------


def test_sgr_wheel_reports_decode():
    # The report's fields are 1-based; the decoder normalizes to 0-based.
    assert feed(b"\x1b[<64;10;5M") == [MouseEvent("wheel_up", button=0, x=9, y=4)]
    assert feed(b"\x1b[<65;10;5m") == [MouseEvent("wheel_down", button=1, x=9, y=4)]
    # The low two bits select the direction; modifier bits are covered by them.
    assert feed(b"\x1b[<81;3;9m") == [MouseEvent("wheel_down", button=1, x=2, y=8)]
    # A report may be split across feeds.
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[<64;1") == []
    assert decoder.feed(b"0;5M") == [MouseEvent("wheel_up", button=0, x=9, y=4)]


def test_sgr_button_presses_decode():
    assert feed(b"\x1b[<0;5;5M") == [MouseEvent("left", button=0, x=4, y=4, kind="press")]
    assert feed(b"\x1b[<1;3;7M") == [MouseEvent("middle", button=1, x=2, y=6)]
    assert feed(b"\x1b[<2;3;7M") == [MouseEvent("right", button=2, x=2, y=6)]
    # Modifier bits (shift 4, ctrl 16) never change which button was pressed.
    assert feed(b"\x1b[<6;3;7M") == [MouseEvent("right", button=2, x=2, y=6)]
    assert feed(b"\x1b[<18;3;7M") == [MouseEvent("right", button=2, x=2, y=6)]


def test_sgr_release_and_motion_reports_decode():
    # Lowercase m is a release; the motion bit (32) with M is a motion
    # report -- a drag while the button is held, or hover with bits 0.
    assert feed(b"\x1b[<0;5;5m") == [MouseEvent("left", button=0, x=4, y=4, kind="release")]
    assert feed(b"\x1b[<2;3;7m") == [MouseEvent("right", button=2, x=2, y=6, kind="release")]
    assert feed(b"\x1b[<32;2;5M") == [MouseEvent("left", button=0, x=1, y=4, kind="motion")]
    assert feed(b"\x1b[<34;5;5M") == [MouseEvent("right", button=2, x=4, y=4, kind="motion")]
    # A modifier never changes which button the motion report names.
    assert feed(b"\x1b[<38;3;7M") == [MouseEvent("right", button=2, x=2, y=6, kind="motion")]


@pytest.mark.parametrize(
    "report, name, kind",
    [
        (b"\x1b[<0;5;3M", "left", "press"),  # a button going down
        (b"\x1b[<32;5;4M", "left", "motion"),  # the pointer moved at 4;3
        (b"\x1b[<0;5;5m", "left", "release"),  # the button came back up
        (b"\x1b[<64;10;5M", "wheel_up", "press"),  # the wheel stays discrete
        (b"\x1b[<65;10;5m", "wheel_down", "press"),  # ...final byte aside
    ],
)
def test_mouse_events_carry_a_kind(report, name, kind):
    event = feed(report)[0]
    assert (event.name, event.kind) == (name, kind)


def test_unknown_button_codes_and_malformed_reports_stay_dropped():
    assert feed(b"\x1b[<3;1;1M") == []  # an unknown button code
    assert feed(b"\x1b[<3;1;1m") == []  # unknown on a release too
    assert feed(b"\x1b[<66;1;1M") == []  # horizontal wheel: not routed today
    assert feed(b"\x1b[<64;10M") == []  # malformed (missing field)
    assert feed(b"\x1b[<M") == []  # malformed (no fields)


# --- bracketed paste -----------------------------------------------------------


def test_bracketed_paste_is_one_event_never_reinterpreted():
    assert feed(b"\x1b[200~hello\r\nworld\x1b[201~") == [Paste("hello\r\nworld")]
    payload = b"a\x1bb\x1b[201"  # escapes and a fake end-marker fragment
    assert feed(b"\x1b[200~" + payload + b"\x1b[201~") == [Paste("a\x1bb\x1b[201")]
    assert feed(b"\x1b[200~\x1b[201~") == [Paste("")]  # an empty paste is a paste


def test_paste_spans_feeds_and_flush_closes_an_unclosed_one():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[200~ab") == []
    assert decoder.feed(b"cd") == []
    assert decoder.pending() is False  # a paste is payload text, not a pending sequence
    assert decoder.feed(b"\x1b[201~") == [Paste("abcd")]
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[200~raw\r\ntext") == []
    assert decoder.finish() == [Paste("raw\r\ntext")]  # delivered verbatim


def test_stray_paste_end_marker_is_dropped():
    assert feed(b"\x1b[201~") == []
    assert feed(b"a\x1b[201~b") == [Key("a", "a"), Key("b", "b")]


# --- escape resolution ---------------------------------------------------------


def test_lone_escape_stays_pending_until_settled():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b") == [] and decoder.pending() is True
    assert decoder.settle() == [Key("escape")] and decoder.pending() is False
    assert decoder.settle() == []  # settling twice changes nothing
    assert feed(b"a\x1bb") == [Key("a", "a"), Key("escape"), Key("b", "b")]


def test_escape_escape_resolves_the_first_and_restarts():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b\x1b") == [Key("escape")]
    assert decoder.settle() == [Key("escape")]
    assert feed(b"\x1b\x1b[A") == [Key("escape"), Key("up")]


def test_incomplete_csi_degrades_to_escape_plus_literal_parameters():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[") == [] and decoder.pending() is True
    assert decoder.settle() == [Key("escape")]  # the "[" introducer is consumed
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[1;5") == []
    assert decoder.settle() == [Key("escape"), Key("1", "1"), Key(";", ";"), Key("5", "5")]
    assert decoder.feed(b"q") == [Key("q", "q")]  # decoding resumes


def test_csi_aborted_by_an_invalid_byte_degrades_and_resumes():
    # ESC [ 1 CR: the CR cannot be part of a CSI, so it degrades and the CR is
    # re-read as ground -- as soon as the CR arrives, feed boundary irrelevant.
    assert feed(b"\x1b[1\r") == [Key("escape"), Key("1", "1"), Key("enter")]
    # ESC O P (an unknown two-byte escape) degrades the same way.
    assert feed(b"\x1bOP") == [Key("escape"), Key("O", "O"), Key("P", "P")]


def test_sequences_assemble_across_feeds_byte_by_byte():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b") == []
    assert decoder.feed(b"[") == []
    assert decoder.feed(b"A") == [Key("up")]
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b") == []
    assert decoder.feed(b"[5~") == [Key("page_up")]
    # A paste never shows up as pending.
    decoder.feed(b"\x1b[200~x")
    assert decoder.pending() is False


# --- incremental UTF-8 ---------------------------------------------------------


def test_utf8_assembles_across_feeds_and_invalid_bytes_degrade():
    decoder = KeyDecoder()
    assert decoder.feed(b"\xe4\xb8") == []
    assert decoder.feed(b"\xad") == [Key("中", "中")]
    assert feed(b"\xff") == [Key("\ufffd", "\ufffd")]
    decoder = KeyDecoder()
    assert decoder.feed(b"\xe4\xb8") == []
    assert decoder.finish() == [Key("\ufffd", "\ufffd")]  # truncated tail


def test_feed_rejects_text_input():
    with pytest.raises(TypeError):
        KeyDecoder().feed("abc")  # type: ignore[arg-type]

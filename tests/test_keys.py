"""Tests for motui.keys.decoder (KeyDecoder): the 1.2 decode matrix.

A pure, total ``bytes -> events`` machine -- incremental UTF-8, control names,
CSI/SS3 navigation, F1-F12, modifier chords, kitty and modifyOtherKeys,
bracketed paste, focus/resize reports, SGR/X10/urxvt mouse; nothing raises.
"""

import pytest

from motui.kernel.events import (
    FocusEvent,
    KeyEvent,
    MouseEvent,
    PasteEvent,
    ResizeEvent,
)
from motui.keys import KeyDecoder

SHIFT = frozenset({"shift"})
ALT = frozenset({"alt"})
CTRL = frozenset({"ctrl"})


def feed(*chunks: bytes) -> list:
    """Decode every chunk through one decoder, in order."""
    decoder = KeyDecoder()
    out: list = []
    for chunk in chunks:
        out.extend(decoder.feed(chunk))
    return out


# --- printable characters and control names ------------------------------------


def test_printable_and_wide_characters_are_their_own_key():
    assert feed(b"ab") == [KeyEvent("a", "a"), KeyEvent("b", "b")]
    assert feed("中文".encode()) == [KeyEvent("中", "中"), KeyEvent("文", "文")]
    assert feed(b" ") == [KeyEvent("space", " ")]


def test_cr_is_enter_and_lf_is_c_j():
    assert feed(b"\r") == [KeyEvent("enter")]
    # The one name that makes EDITOR_SUBMIT_KEYMAP reachable: a line feed is
    # Ctrl-J, a carriage return is the submit gesture.
    assert feed(b"\n") == [KeyEvent("c-j")]
    assert feed(b"\t") == [KeyEvent("tab")]
    assert feed(b"\x7f") == [KeyEvent("backspace")]


def test_control_bytes_map_to_c_a_through_c_z():
    assert feed(b"\x01") == [KeyEvent("c-a")]
    assert feed(b"\x03") == [KeyEvent("c-c")]
    assert feed(b"\x1a") == [KeyEvent("c-z")]


def test_unlisted_control_bytes_are_dropped_not_fatal():
    assert feed(b"\x00") == []
    assert feed(b"\x1c\x1d\x1e\x1f") == []
    assert feed(b"a\x00b") == [KeyEvent("a", "a"), KeyEvent("b", "b")]


# --- CSI navigation keys -------------------------------------------------------


def test_csi_letter_finals():
    assert feed(b"\x1b[A") == [KeyEvent("up")]
    assert feed(b"\x1b[B") == [KeyEvent("down")]
    assert feed(b"\x1b[C") == [KeyEvent("right")] and feed(b"\x1b[D") == [KeyEvent("left")]
    assert feed(b"\x1b[H") == [KeyEvent("home")] and feed(b"\x1b[F") == [KeyEvent("end")]


def test_csi_f1_through_f4_letters():
    assert feed(b"\x1b[P") == [KeyEvent("f1")]
    assert feed(b"\x1b[Q") == [KeyEvent("f2")]
    assert feed(b"\x1b[R") == [KeyEvent("f3")]
    assert feed(b"\x1b[S") == [KeyEvent("f4")]


def test_focus_reports_decode_as_focus_events():
    # DECSET 1004: the terminal reports its window gaining / losing focus.
    assert feed(b"\x1b[I") == [FocusEvent(True)]
    assert feed(b"\x1b[O") == [FocusEvent(False)]


def test_csi_tilde_family_by_first_parameter():
    assert feed(b"\x1b[1~") == [KeyEvent("home")] and feed(b"\x1b[7~") == [KeyEvent("home")]
    assert feed(b"\x1b[2~") == [KeyEvent("insert")]
    assert feed(b"\x1b[3~") == [KeyEvent("delete")]
    assert feed(b"\x1b[4~") == [KeyEvent("end")] and feed(b"\x1b[8~") == [KeyEvent("end")]
    assert feed(b"\x1b[5~") == [KeyEvent("page_up")] and feed(b"\x1b[6~") == [KeyEvent("page_down")]


def test_csi_tilde_f1_through_f12():
    expected = {
        11: "f1", 12: "f2", 13: "f3", 14: "f4", 15: "f5", 17: "f6",
        18: "f7", 19: "f8", 20: "f9", 21: "f10", 23: "f11", 24: "f12",
    }
    for code, name in expected.items():
        assert feed(f"\x1b[{code}~".encode()) == [KeyEvent(name)]


def test_ss3_navigation_f1_through_f4_and_tab_back():
    assert feed(b"\x1bOA") == [KeyEvent("up")]
    assert feed(b"\x1bOB") == [KeyEvent("down")]
    assert feed(b"\x1bOC") == [KeyEvent("right")]
    assert feed(b"\x1bOD") == [KeyEvent("left")]
    assert feed(b"\x1bOH") == [KeyEvent("home")]
    assert feed(b"\x1bOF") == [KeyEvent("end")]
    assert feed(b"\x1bOP") == [KeyEvent("f1")]
    assert feed(b"\x1bOQ") == [KeyEvent("f2")]
    assert feed(b"\x1bOR") == [KeyEvent("f3")]
    assert feed(b"\x1bOS") == [KeyEvent("f4")]
    assert feed(b"\x1bOZ") == [KeyEvent("escape"), KeyEvent("O", "O"), KeyEvent("Z", "Z")]


def test_shift_tab_names_s_tab():
    assert feed(b"\x1b[Z") == [KeyEvent("s-tab", "", SHIFT)]
    assert feed(b"\x1b[1;2Z") == [KeyEvent("s-tab", "", SHIFT)]
    assert feed(b"\x1b[1;6Z") == [KeyEvent("c-s-tab", "", frozenset({"ctrl", "shift"}))]


def test_modifier_parameters_fill_the_key_and_the_set():
    # m = 1 + shift(1) | alt(2) | ctrl(4).
    assert feed(b"\x1b[1;2A") == [KeyEvent("s-up", "", SHIFT)]
    assert feed(b"\x1b[1;3A") == [KeyEvent("a-up", "", ALT)]
    assert feed(b"\x1b[1;4A") == [KeyEvent("a-s-up", "", frozenset({"alt", "shift"}))]
    assert feed(b"\x1b[1;5A") == [KeyEvent("c-up", "", CTRL)]
    assert feed(b"\x1b[1;6A") == [KeyEvent("c-s-up", "", frozenset({"ctrl", "shift"}))]
    assert feed(b"\x1b[1;7A") == [KeyEvent("c-a-up", "", frozenset({"ctrl", "alt"}))]
    assert feed(b"\x1b[1;8A") == [
        KeyEvent("c-a-s-up", "", frozenset({"ctrl", "alt", "shift"}))
    ]
    assert feed(b"\x1b[1;9A") == [KeyEvent("super-up", "", frozenset({"super"}))]
    # The same modifier field works on the tilde family.
    assert feed(b"\x1b[3;5~") == [KeyEvent("c-delete", "", CTRL)]
    assert feed(b"\x1b[1;2H") == [KeyEvent("s-home", "", SHIFT)]
    assert feed(b"\x1b[A\x1b[B") == [KeyEvent("up"), KeyEvent("down")]


def test_kitty_codepoint_forms():
    assert feed(b"\x1b[97u") == [KeyEvent("a", "a")]
    assert feed(b"\x1b[97;5u") == [KeyEvent("c-a", "", CTRL)]
    assert feed(b"\x1b[13u") == [KeyEvent("enter")]
    assert feed(b"\x1b[32u") == [KeyEvent("space", " ")]
    assert feed(b"\x1b[97;1:2u") == [KeyEvent("a", "a", frozenset(), "repeat")]
    assert feed(b"\x1b[97;1:3u") == [KeyEvent("a", "a", frozenset(), "release")]
    assert feed(b"\x1b[97;2u") == [KeyEvent("a", "a", SHIFT)]
    assert feed(b"\x1b[1092u") == [KeyEvent("ф", "ф")]  # U+0444


def test_modify_other_keys_form():
    assert feed(b"\x1b[27;5;13~") == [KeyEvent("c-enter", "", CTRL)]
    assert feed(b"\x1b[27;3;97~") == [KeyEvent("a-a", "", ALT)]
    assert feed(b"\x1b[27;1;97~") == [KeyEvent("a", "a")]
    assert feed(b"\x1b[27;5;27~") == [KeyEvent("c-escape", "", CTRL)]


def test_resize_reports_decode():
    assert feed(b"\x1b[8;24;80t") == [ResizeEvent(80, 24)]
    assert feed(b"\x1b[8;40;120t") == [ResizeEvent(120, 40)]
    assert feed(b"\x1b[8;24t") == []  # malformed (two fields): dropped


def test_unknown_sequences_are_dropped():
    assert feed(b"\x1b[?25h") == []  # unknown final byte
    assert feed(b"\x1b[999~") == []  # unknown tilde code
    assert feed(b"\x1b[1114112u") == []  # beyond Unicode: dropped


# --- SGR mouse reports -------------------------------------------------------


def test_sgr_wheel_reports_decode():
    # The report's fields are 1-based; the decoder normalizes to 0-based.
    assert feed(b"\x1b[<64;10;5M") == [MouseEvent("wheel_up", 9, 4, "wheel")]
    assert feed(b"\x1b[<65;10;5m") == [MouseEvent("wheel_down", 9, 4, "wheel")]
    # The low two bits select the direction; modifier bits ride alongside.
    assert feed(b"\x1b[<81;3;9m") == [
        MouseEvent("wheel_down", 2, 8, "wheel", frozenset({"ctrl"}))
    ]
    # A horizontal wheel is parsed, not dropped.
    assert feed(b"\x1b[<66;3;9M") == [MouseEvent("wheel_left", 2, 8, "wheel")]
    assert feed(b"\x1b[<67;3;9M") == [MouseEvent("wheel_right", 2, 8, "wheel")]
    # A report may be split across feeds.
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[<64;1") == []
    assert decoder.feed(b"0;5M") == [MouseEvent("wheel_up", 9, 4, "wheel")]


def test_sgr_button_presses_decode():
    assert feed(b"\x1b[<0;5;5M") == [MouseEvent("left", 4, 4, "press")]
    assert feed(b"\x1b[<1;3;7M") == [MouseEvent("middle", 2, 6, "press")]
    assert feed(b"\x1b[<2;3;7M") == [MouseEvent("right", 2, 6, "press")]
    # Modifier bits (shift 4, alt 8, ctrl 16) never change which button it is.
    assert feed(b"\x1b[<6;3;7M") == [
        MouseEvent("right", 2, 6, "press", frozenset({"shift"}))
    ]
    assert feed(b"\x1b[<18;3;7M") == [
        MouseEvent("right", 2, 6, "press", frozenset({"ctrl"}))
    ]


def test_sgr_release_and_motion_reports_decode():
    assert feed(b"\x1b[<0;5;5m") == [MouseEvent("left", 4, 4, "release")]
    assert feed(b"\x1b[<2;3;7m") == [MouseEvent("right", 2, 6, "release")]
    assert feed(b"\x1b[<32;2;5M") == [MouseEvent("left", 1, 4, "motion")]
    assert feed(b"\x1b[<34;5;5M") == [MouseEvent("right", 4, 4, "motion")]
    # A modifier never changes which button the motion report names.
    assert feed(b"\x1b[<38;3;7M") == [
        MouseEvent("right", 2, 6, "motion", frozenset({"shift"}))
    ]


def test_sgr_button_free_motion_normalizes_to_none():
    assert feed(b"\x1b[<35;2;5M") == [MouseEvent("none", 1, 4, "motion")]
    assert feed(b"\x1b[<39;2;5M") == [
        MouseEvent("none", 1, 4, "motion", frozenset({"shift"}))
    ]
    # A press or release carrying low 3 names no button.
    assert feed(b"\x1b[<3;5;5M") == [MouseEvent("none", 4, 4, "press")]
    assert feed(b"\x1b[<3;5;5m") == [MouseEvent("none", 4, 4, "release")]


def test_x10_reports_decode():
    # ESC [ M plus three raw bytes: button+32, x+33, y+33.
    assert feed(b"\x1b[M %%") == [MouseEvent("left", 4, 4, "press")]
    assert feed(b"\x1b[M#%%") == [MouseEvent("none", 4, 4, "release")]
    assert feed(b"\x1b[M@%%") == [MouseEvent("left", 4, 4, "motion")]
    assert feed(b"\x1b[M`%%") == [MouseEvent("wheel_up", 4, 4, "wheel")]
    # Byte by byte across feeds.
    decoder = KeyDecoder()
    for byte in b"\x1b[M %%":
        out = decoder.feed(bytes([byte]))
    assert out == [MouseEvent("left", 4, 4, "press")]


def test_urxvt_1015_reports_decode():
    assert feed(b"\x1b[0;5;5M") == [MouseEvent("left", 4, 4, "press")]
    assert feed(b"\x1b[0;5;5m") == [MouseEvent("left", 4, 4, "release")]
    assert feed(b"\x1b[2;5;5M") == [MouseEvent("right", 4, 4, "press")]
    assert feed(b"\x1b[64;2;3M") == [MouseEvent("wheel_up", 1, 2, "wheel")]
    assert feed(b"\x1b[35;2;3M") == [MouseEvent("none", 1, 2, "motion")]


def test_mouse_events_carry_a_kind_and_button():
    cases = [
        (b"\x1b[<0;5;3M", "left", "press"),  # a button going down
        (b"\x1b[<32;5;4M", "left", "motion"),  # the pointer moved at 4;3
        (b"\x1b[<0;5;5m", "left", "release"),  # the button came back up
        (b"\x1b[<64;10;5M", "wheel_up", "wheel"),  # wheel reports are discrete
        (b"\x1b[<65;10;5m", "wheel_down", "wheel"),  # ...final byte aside
    ]
    for report, button, kind in cases:
        event = feed(report)[0]
        assert (event.button, event.kind) == (button, kind)


def test_malformed_reports_stay_dropped():
    assert feed(b"\x1b[<64;10M") == []  # malformed (missing field)
    assert feed(b"\x1b[<M") == []  # malformed (no fields)
    assert feed(b"\x1b[<;1;1M") == []  # non-numeric button
    assert feed(b"\x1b[<1;2;3;4M") == []  # too many fields


# --- bracketed paste -----------------------------------------------------------


def test_bracketed_paste_is_one_event_never_reinterpreted():
    assert feed(b"\x1b[200~hello\r\nworld\x1b[201~") == [PasteEvent("hello\r\nworld")]
    payload = b"a\x1bb\x1b[201"  # escapes and a fake end-marker fragment
    assert feed(b"\x1b[200~" + payload + b"\x1b[201~") == [PasteEvent("a\x1bb\x1b[201")]
    assert feed(b"\x1b[200~\x1b[201~") == [PasteEvent("")]  # an empty paste is a paste


def test_paste_spans_feeds_and_finish_closes_an_unclosed_one():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[200~ab") == []
    assert decoder.feed(b"cd") == []
    assert decoder.pending() is False  # a paste is payload text, not a pending sequence
    assert decoder.feed(b"\x1b[201~") == [PasteEvent("abcd")]
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[200~raw\r\ntext") == []
    assert decoder.finish() == [PasteEvent("raw\r\ntext")]  # delivered verbatim


def test_a_paste_end_marker_split_across_feeds_still_closes_the_paste():
    """The marker's bytes belong to the protocol, wherever a feed boundary falls."""
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[200~ab\x1b[2") == []
    assert decoder.feed(b"01~xy") == [PasteEvent("ab"), KeyEvent("x", "x"), KeyEvent("y", "y")]
    assert decoder.finish() == []

    streamed = b"\x1b[200~ab\x1b[201~xy"
    whole = KeyDecoder()
    whole_events = whole.feed(streamed) + whole.finish()
    assert whole_events == [PasteEvent("ab"), KeyEvent("x", "x"), KeyEvent("y", "y")]
    for cut in range(1, len(streamed)):
        split = KeyDecoder()
        events = split.feed(streamed[:cut]) + split.feed(streamed[cut:]) + split.finish()
        assert events == whole_events, f"cut at {cut}"

    # A partial marker that turns out to be payload content stays payload.
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[200~a\x1b[20") == []
    assert decoder.feed(b"Q\x1b[201~") == [PasteEvent("a\x1b[20Q")]
    # And an unclosed paste still delivers its held-back tail with the rest.
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[200~raw\x1b[20") == []
    assert decoder.finish() == [PasteEvent("raw\x1b[20")]


def test_stray_paste_end_marker_is_dropped():
    assert feed(b"\x1b[201~") == []
    assert feed(b"a\x1b[201~b") == [KeyEvent("a", "a"), KeyEvent("b", "b")]


# --- escape resolution ---------------------------------------------------------


def test_lone_escape_stays_pending_until_settled():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b") == [] and decoder.pending() is True
    assert decoder.settle() == [KeyEvent("escape")] and decoder.pending() is False
    assert decoder.settle() == []  # settling twice changes nothing
    assert feed(b"a\x1bb") == [KeyEvent("a", "a"), KeyEvent("escape"), KeyEvent("b", "b")]


def test_escape_escape_resolves_the_first_and_restarts():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b\x1b") == [KeyEvent("escape")]
    assert decoder.settle() == [KeyEvent("escape")]
    assert feed(b"\x1b\x1b[A") == [KeyEvent("escape"), KeyEvent("up")]


def test_incomplete_csi_degrades_to_escape_plus_literal_parameters():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[") == [] and decoder.pending() is True
    assert decoder.settle() == [KeyEvent("escape")]  # the "[" introducer is consumed
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[1;5") == []
    assert decoder.settle() == [
        KeyEvent("escape"), KeyEvent("1", "1"), KeyEvent(";", ";"), KeyEvent("5", "5")
    ]
    assert decoder.feed(b"q") == [KeyEvent("q", "q")]  # decoding resumes


def test_incomplete_ss3_and_x10_release_their_introducers():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1bO") == [] and decoder.pending() is True
    assert decoder.settle() == [KeyEvent("escape"), KeyEvent("O", "O")]
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[M ") == [] and decoder.pending() is True
    assert decoder.settle() == [
        KeyEvent("escape"), KeyEvent("[", "["), KeyEvent("M", "M"), KeyEvent("space", " ")
    ]


def test_csi_aborted_by_an_invalid_byte_degrades_and_resumes():
    # ESC [ 1 CR: the CR cannot be part of a CSI, so it degrades and the CR is
    # re-read as ground -- as soon as the CR arrives, feed boundary irrelevant.
    assert feed(b"\x1b[1\r") == [KeyEvent("escape"), KeyEvent("1", "1"), KeyEvent("enter")]
    # ESC O P is f1 now, so an unknown SS3 (ESC O X) degrades.
    assert feed(b"\x1bOX") == [KeyEvent("escape"), KeyEvent("O", "O"), KeyEvent("X", "X")]


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
    # A paste never shows up as pending.
    decoder.feed(b"\x1b[200~x")
    assert decoder.pending() is False


# --- incremental UTF-8 ---------------------------------------------------------


def test_utf8_assembles_across_feeds_and_invalid_bytes_degrade():
    decoder = KeyDecoder()
    assert decoder.feed(b"\xe4\xb8") == []
    assert decoder.feed(b"\xad") == [KeyEvent("中", "中")]
    assert feed(b"\xff") == [KeyEvent("\ufffd", "\ufffd")]
    decoder = KeyDecoder()
    assert decoder.feed(b"\xe4\xb8") == []
    assert decoder.finish() == [KeyEvent("\ufffd", "\ufffd")]  # truncated tail


def test_feed_rejects_non_bytes_input():
    with pytest.raises(TypeError):
        KeyDecoder().feed("abc")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        KeyDecoder().feed(bytearray(b"abc"))  # type: ignore[arg-type]

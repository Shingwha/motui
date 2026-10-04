"""Tests for mocode_tui.keys: the event model and the KeyDecoder."""

import pytest

from mocode_tui.keys import Key, KeyDecoder, KeySource, MouseEvent, Paste


def feed(*chunks: bytes) -> list:
    """Decode every chunk through one decoder, in order."""
    decoder = KeyDecoder()
    out: list = []
    for chunk in chunks:
        out.extend(decoder.feed(chunk))
    return out


# --- event model -------------------------------------------------------------


def test_key_and_paste_are_frozen_dataclasses():
    assert Key("a") == Key("a", "")
    assert Key("a", "a") != Key("a")
    assert Paste("x") == Paste("x")
    with pytest.raises(Exception):
        Key("a").name = "b"  # frozen


def test_key_source_protocol_is_runtime_checkable():
    class Source:
        async def read(self):
            return None

    assert isinstance(Source(), KeySource)


# --- printable characters ----------------------------------------------------


def test_printable_characters_are_their_own_name():
    assert feed(b"ab") == [Key("a", "a"), Key("b", "b")]


def test_wide_characters_survive_utf8():
    assert feed("中文".encode()) == [Key("中", "中"), Key("文", "文")]


def test_space_is_named_space():
    assert feed(b" ") == [Key("space", " ")]


# --- control names -----------------------------------------------------------


def test_carriage_return_and_new_feed_are_enter():
    assert feed(b"\r") == [Key("enter")]
    assert feed(b"\n") == [Key("enter")]
    assert feed(b"hi\r") == [Key("h", "h"), Key("i", "i"), Key("enter")]


def test_tab_and_backspace():
    assert feed(b"\t") == [Key("tab")]
    assert feed(b"\x7f") == [Key("backspace")]


@pytest.mark.parametrize(
    ("byte", "name"),
    [(0x01, "c-a"), (0x03, "c-c"), (0x08, "c-h"), (0x0C, "c-l"), (0x1A, "c-z")],
)
def test_control_bytes_map_to_c_a_through_c_z(byte, name):
    assert feed(bytes([byte])) == [Key(name)]


def test_unlisted_control_bytes_are_dropped_not_fatal():
    assert feed(b"\x00") == []
    assert feed(b"\x1c\x1d\x1e\x1f") == []
    assert feed(b"a\x00b") == [Key("a", "a"), Key("b", "b")]


# --- CSI navigation keys -----------------------------------------------------


@pytest.mark.parametrize(
    ("seq", "name"),
    [
        (b"\x1b[A", "up"),
        (b"\x1b[B", "down"),
        (b"\x1b[C", "right"),
        (b"\x1b[D", "left"),
        (b"\x1b[H", "home"),
        (b"\x1b[F", "end"),
    ],
)
def test_csi_letter_finals(seq, name):
    assert feed(seq) == [Key(name)]


@pytest.mark.parametrize(
    ("seq", "name"),
    [
        (b"\x1b[1~", "home"),
        (b"\x1b[7~", "home"),
        (b"\x1b[3~", "delete"),
        (b"\x1b[4~", "end"),
        (b"\x1b[8~", "end"),
        (b"\x1b[5~", "page_up"),
        (b"\x1b[6~", "page_down"),
    ],
)
def test_csi_tilde_family_by_first_parameter(seq, name):
    assert feed(seq) == [Key(name)]


def test_tilde_family_reads_only_the_first_parameter():
    assert feed(b"\x1b[3;5~") == [Key("delete")]


def test_csi_with_private_markers_and_modifiers_is_dispatched_or_dropped():
    assert feed(b"\x1b[1;5A") == [Key("up")]  # modifier params ignored
    assert feed(b"\x1b[?25h") == []  # unknown final byte: dropped
    assert feed(b"\x1b[<0;5;5M") == []  # SGR mouse report: dropped
    assert feed(b"\x1b[<66;1;1M") == []  # horizontal wheel: dropped
    assert feed(b"\x1b[<64;10M") == []  # malformed report (missing field): dropped
    assert feed(b"\x1b[<M") == []  # malformed report (no fields): dropped
    assert feed(b"\x1b[24;80R") == []  # cursor position report: dropped


# --- SGR mouse wheel reports -------------------------------------------------


@pytest.mark.parametrize(
    ("report", "name", "button", "x", "y"),
    [
        (b"\x1b[<64;10;5M", "wheel_up", 0, 10, 5),
        (b"\x1b[<65;10;5m", "wheel_down", 1, 10, 5),
        (b"\x1b[<68;3;9M", "wheel_up", 0, 3, 9),      # shift bit (4) masked
        (b"\x1b[<81;3;9m", "wheel_down", 1, 3, 9),    # ctrl bit (16) masked
    ],
)
def test_sgr_wheel_reports_decode_to_wheel_keys(report, name, button, x, y):
    assert feed(report) == [MouseEvent(name, button=button, x=x, y=y)]


def test_sgr_wheel_report_assembles_across_feeds():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[<64;1") == []  # still pending mid-report
    assert decoder.feed(b"0;5M") == [MouseEvent("wheel_up", button=0, x=10, y=5)]


def test_unknown_tilde_parameter_is_dropped():
    assert feed(b"\x1b[2~") == []  # insert: outside the contract
    assert feed(b"\x1b[Z") == []  # shift+tab: outside the contract


def test_a_complete_sequence_in_one_feed_is_parsed_as_a_unit():
    assert feed(b"\x1b[A\x1b[B") == [Key("up"), Key("down")]


# --- bracketed paste ---------------------------------------------------------


def test_bracketed_paste_is_one_event():
    assert feed(b"\x1b[200~hello\r\nworld\x1b[201~") == [Paste("hello\r\nworld")]


def test_paste_across_feeds_aggregates_until_the_end_marker():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[200~ab") == []
    assert decoder.feed(b"cd") == []
    assert decoder.feed(b"\x1b[201~") == [Paste("abcd")]


def test_paste_content_is_never_reinterpreted():
    # The payload contains escape bytes and a fake end-marker fragment.
    payload = b"a\x1bb\x1b[201"
    assert feed(b"\x1b[200~" + payload + b"\x1b[201~") == [Paste("a\x1bb\x1b[201")]


def test_empty_paste_delivers_an_empty_paste():
    assert feed(b"\x1b[200~\x1b[201~") == [Paste("")]


def test_stray_paste_end_marker_is_dropped():
    assert feed(b"\x1b[201~") == []
    assert feed(b"a\x1b[201~b") == [Key("a", "a"), Key("b", "b")]


def test_flush_delivers_an_unclosed_paste_verbatim():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[200~raw\r\ntext") == []
    assert decoder.flush() == [Paste("raw\r\ntext")]


# --- escape resolution -------------------------------------------------------


def test_lone_escape_at_feed_end_stays_pending_until_settled():
    # W7 semantics: a feed ending inside a sequence leaves it pending; the
    # escape key surfaces at the caller's settle deadline, not at the feed
    # boundary -- the next feed may still continue the sequence.
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b") == []
    assert decoder.pending() is True
    assert decoder.settle() == [Key("escape")]
    assert decoder.pending() is False

    decoder = KeyDecoder()
    assert decoder.feed(b"a\x1b") == [Key("a", "a")]
    assert decoder.settle() == [Key("escape")]


def test_escape_between_keys_is_delivered():
    assert feed(b"a\x1bb") == [Key("a", "a"), Key("escape"), Key("b", "b")]


def test_escape_escape_is_two_escape_keys():
    # ESC ESC resolves the first escape immediately and restarts on the
    # second, which stays pending across the feed boundary (settle delivers
    # it).  A following CSI still assembles normally.
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b\x1b") == [Key("escape")]
    assert decoder.settle() == [Key("escape")]
    assert feed(b"\x1b\x1b[A") == [Key("escape"), Key("up")]


def test_incomplete_csi_degrades_to_escape_plus_literal_parameters():
    # The "[" introducer is consumed as part of the broken sequence; only the
    # parameter characters are re-read literally.  W7 semantics: the
    # incomplete CSI is pending first (more bytes may still assemble it) and
    # the degrade happens at the caller's settle deadline.
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[") == []
    assert decoder.pending() is True
    assert decoder.settle() == [Key("escape")]

    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[1") == []
    assert decoder.settle() == [Key("escape"), Key("1", "1")]

    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b[1;5") == []
    assert decoder.settle() == [
        Key("escape"),
        Key("1", "1"),
        Key(";", ";"),
        Key("5", "5"),
    ]


def test_csi_aborted_by_an_invalid_byte_degrades_and_resumes():
    # ESC [ 1 CR: the CR cannot be part of a CSI, so the sequence degrades and
    # the CR is processed normally as enter.  This resolves as soon as the
    # CR arrives -- feed boundaries play no role.
    assert feed(b"\x1b[1\r") == [Key("escape"), Key("1", "1"), Key("enter")]


def test_sequence_assembles_across_feeds():
    # The W7 fix: a VT sequence split byte by byte across feeds -- exactly
    # how the Windows console record path delivers it -- still decodes.
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b") == []
    assert decoder.feed(b"[") == []
    assert decoder.feed(b"A") == [Key("up")]


def test_tilde_family_assembles_across_two_feeds():
    decoder = KeyDecoder()
    assert decoder.feed(b"\x1b") == []
    assert decoder.feed(b"[5~") == [Key("page_up")]


def test_pending_tracks_escape_and_csi_but_never_paste():
    decoder = KeyDecoder()
    assert decoder.pending() is False
    decoder.feed(b"a")
    assert decoder.pending() is False
    decoder.feed(b"\x1b")
    assert decoder.pending() is True
    decoder.feed(b"[")
    assert decoder.pending() is True
    decoder.feed(b"A")
    assert decoder.pending() is False
    decoder.feed(b"\x1b[200~x")
    assert decoder.pending() is False  # a paste is payload text, not a pending sequence


def test_settle_clears_csi_state_and_decoding_resumes():
    decoder = KeyDecoder()
    decoder.feed(b"\x1b[1;5")
    assert decoder.settle() == [Key("escape"), Key("1", "1"), Key(";", ";"), Key("5", "5")]
    assert decoder.pending() is False
    assert decoder.feed(b"q") == [Key("q", "q")]


def test_settle_is_idempotent_and_paste_is_untouched():
    decoder = KeyDecoder()
    assert decoder.settle() == []
    decoder.feed(b"\x1b")
    assert decoder.settle() == [Key("escape")]
    assert decoder.settle() == []
    decoder.feed(b"\x1b[200~x")
    assert decoder.settle() == []  # pastes wait for their end marker, never settle


def test_flush_settles_a_pending_sequence():
    decoder = KeyDecoder()
    assert decoder.feed(b"a\x1b[1") == [Key("a", "a")]
    assert decoder.flush() == [Key("escape"), Key("1", "1")]


def test_unknown_two_byte_escape_degrades_to_escape_plus_literal():
    assert feed(b"\x1bOP") == [Key("escape"), Key("O", "O"), Key("P", "P")]


# --- incremental UTF-8 -------------------------------------------------------


def test_split_utf8_sequence_completes_on_a_later_feed():
    decoder = KeyDecoder()
    assert decoder.feed(b"\xe4\xb8") == []
    assert decoder.feed(b"\xad") == [Key("中", "中")]


def test_invalid_utf8_becomes_replacement_characters():
    assert feed(b"\xff") == [Key("\ufffd", "\ufffd")]


def test_flush_reports_a_truncated_utf8_tail():
    decoder = KeyDecoder()
    assert decoder.feed(b"\xe4\xb8") == []
    assert decoder.flush() == [Key("\ufffd", "\ufffd")]


# --- misc --------------------------------------------------------------------


def test_empty_feed_is_empty_and_flush_is_idempotent():
    decoder = KeyDecoder()
    assert decoder.feed(b"") == []
    assert decoder.flush() == []
    assert decoder.flush() == []


def test_feed_rejects_text_input():
    with pytest.raises(TypeError):
        KeyDecoder().feed("abc")  # type: ignore[arg-type]


def test_keys_after_a_flushed_paste_still_decode():
    decoder = KeyDecoder()
    decoder.feed(b"\x1b[200~tail")
    assert decoder.flush() == [Paste("tail")]
    assert decoder.feed(b"a") == [Key("a", "a")]

"""Tests for mocode_tui.keys: the event model and the KeyDecoder."""

import pytest

from mocode_tui.keys import Key, KeyDecoder, KeySource, Paste


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
    assert feed(b"\x1b[24;80R") == []  # cursor position report: dropped


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


def test_lone_escape_at_feed_end_is_an_escape_key():
    assert feed(b"\x1b") == [Key("escape")]
    assert feed(b"a\x1b") == [Key("a", "a"), Key("escape")]


def test_escape_between_keys_is_delivered():
    assert feed(b"a\x1bb") == [Key("a", "a"), Key("escape"), Key("b", "b")]


def test_escape_escape_is_two_escape_keys():
    assert feed(b"\x1b\x1b") == [Key("escape"), Key("escape")]
    assert feed(b"\x1b\x1b[A") == [Key("escape"), Key("up")]


def test_incomplete_csi_degrades_to_escape_plus_literal_parameters():
    # The "[" introducer is consumed as part of the broken sequence; only the
    # parameter characters are re-read literally.
    assert feed(b"\x1b[") == [Key("escape")]
    assert feed(b"\x1b[1") == [Key("escape"), Key("1", "1")]
    assert feed(b"\x1b[1;5") == [
        Key("escape"),
        Key("1", "1"),
        Key(";", ";"),
        Key("5", "5"),
    ]


def test_csi_aborted_by_an_invalid_byte_degrades_and_resumes():
    # ESC [ 1 CR: the CR cannot be part of a CSI, so the sequence degrades and
    # the CR is processed normally as enter.
    assert feed(b"\x1b[1\r") == [Key("escape"), Key("1", "1"), Key("enter")]


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

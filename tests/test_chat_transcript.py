"""Tests for mocode_tui.chat.transcript (Transcript / StreamHandle).

Contract: every appended block is followed by exactly one blank row (the
demo's uniform rhythm) unless ``spacer=False``; ``stream`` grows a
Message chunk by chunk and invalidates each step; ``seal`` freezes the
block so the viewport caches its rows; ``clear`` removes the body blocks
and leaves pinned ones (an input box, a header) alone.
"""

import pytest

from mocode_tui.chat.message import Message
from mocode_tui.chat.transcript import StreamHandle, Transcript
from mocode_tui.core.block import BlockState
from mocode_tui.core.style import Style
from mocode_tui.testing import headless_tui
from mocode_tui.core.theme import MUTED, Theme
from mocode_tui.widgets.layout import Spacer
from mocode_tui.core.text import Text


def _transcript(**kwargs):
    tui = headless_tui(80, 24)
    return tui, Transcript(tui, **kwargs)


def _components(tui):
    return [block.component for block in tui.document.blocks()]


def test_append_follows_every_block_with_one_blank_row():
    tui, transcript = _transcript()
    first = transcript.append(Message("user", "hi"))
    assert first.is_open is True  # the appended block stays writable
    transcript.append(Message("assistant", "hello"))
    components = _components(tui)
    assert len(components) == 4  # block, spacer, block, spacer
    assert isinstance(components[0], Message)
    assert isinstance(components[1], Spacer) and components[1].rows == 1
    assert isinstance(components[2], Message)
    assert isinstance(components[3], Spacer)


def test_append_returns_the_block_and_honours_an_id():
    tui, transcript = _transcript()
    block = transcript.append(Message("user", "hi"), id="q1")
    assert block.id == "q1"
    assert tui.get("q1").component.text == "hi"


def test_spacer_false_packs_the_blocks_tight():
    tui, transcript = _transcript(spacer=False)
    transcript.append(Message("user", "hi"))
    transcript.append(Message("assistant", "hello"))
    assert len(tui.document.blocks()) == 2
    assert not any(isinstance(c, Spacer) for c in _components(tui))


def test_stream_grows_the_message_chunk_by_chunk():
    tui, transcript = _transcript()
    handle = transcript.stream("thinking")
    assert isinstance(handle, StreamHandle)
    assert isinstance(handle.message, Message)
    assert handle.message.role == "thinking"
    assert handle.message.text == ""
    handle.append("Reading ")
    assert handle.message.text == "Reading "
    assert tui._dirty is True  # each chunk invalidates the frame
    handle.append("the repo.")
    assert handle.message.text == "Reading the repo."


def test_stream_rows_grow_with_the_text():
    tui, transcript = _transcript()
    handle = transcript.stream("assistant")
    rows_before = len(handle.block.render(80))
    assert rows_before == 1  # an empty message is one blank row
    handle.append("word " * 40)  # 200 columns of text at width 80
    assert len(handle.block.render(80)) > rows_before


def test_stream_uses_the_transcript_theme():
    tui, transcript = _transcript(theme=Theme(muted=MUTED))
    handle = transcript.stream("thinking")
    assert handle.message.theme is transcript.theme
    (row,) = handle.block.render(80)
    assert all(seg.style == MUTED.merge(Style(italic=True)) for seg in row.segments)


def test_seal_freezes_the_block_and_caches_its_rows():
    tui, transcript = _transcript()
    handle = transcript.stream("assistant")
    handle.append("hello")
    handle.seal()
    assert handle.block.state is BlockState.SEALED
    tui.paint()  # the first layout after the seal caches the block's rows

    # Behind the seal the viewport serves the cached rows: a later edit of
    # the component cannot change what the frames show any more.
    handle.message.text = "goodbye"
    tui.paint()
    texts = [row.text for row in tui.rows]
    assert "hello" in texts
    assert "goodbye" not in texts

    # Sealing twice is the kernel's documented error, surfaced as-is.
    with pytest.raises(ValueError):
        handle.seal()


def test_clear_removes_the_body_and_keeps_the_pinned_regions():
    tui, transcript = _transcript()
    header = tui.add(Text("banner"), id="header", pin="top")
    footer = tui.add(Text("footer"), id="footer", pin="bottom")
    transcript.append(Message("user", "hi"))
    transcript.append(Message("assistant", "hello"))
    assert len(tui.document.blocks()) == 6  # 2 pinned + 2 blocks + 2 spacers

    transcript.clear()
    remaining = tui.document.blocks()
    assert [block.id for block in remaining] == ["header", "footer"]
    assert tui.get("header") is header and tui.get("footer") is footer


def test_clear_on_an_empty_transcript_is_a_noop():
    tui, transcript = _transcript()
    transcript.clear()
    assert tui.document.blocks() == ()


def test_the_streaming_block_sits_in_the_scrollable_body():
    tui, transcript = _transcript()
    handle = transcript.stream("user")
    assert handle.block.pin is None

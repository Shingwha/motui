"""Tests for :func:`fit_text` and the measurement contract built on it.

Contracts (the W1 ticket): ``fit_text(text, budget)`` returns a prefix of
``text`` measuring at most ``budget`` columns under the single measuring
truth, :func:`visible_width`.  The postcondition
``visible_width(fit_text(text, w)) <= w`` holds for *arbitrary* input,
including emoji whose whole-string width disagrees with the per-character
sum: a VS16 selector widens its base character ("\u26a0\ufe0f" measures 2
whole, 1 per character), while a ZWJ run collapses into one cluster (the
"\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466" family measures 2
whole, 8 per character).  :func:`ellipsize_tail` and :meth:`Line.fit
<mocode_tui.core.lines.Line.fit>` are rewritten on :func:`fit_text`, so they
inherit the same guarantee.
"""

from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import ACCENT, NONE, Style
from mocode_tui.core.text import ellipsize_tail, fit_text, visible_width

# Nasty inputs: VS16-widened emoji, a ZWJ family, a combining sequence,
# wide CJK, tabs, and a run that mixes everything above.
NASTY = [
    "\u26a0\ufe0f Blocked",  # VS16: whole 2, per-character sum 1
    "\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466",  # ZWJ family: whole 2, per-char 8
    "e\u0301e\u0301e\u0301",  # combining acute accents
    "\u65e5\u672c\u8a9e\u306e\u30c6\u30b9\u30c8",  # CJK wide
    "a\tb\tc",  # tabs count one column each
    "\u26a0\ufe0f\u26a0\ufe0f\u26a0\ufe0f end",  # stacked VS16 emoji
    "caf\u00e9 \U0001F600 \u4e2d\u6587",  # mixed narrow, emoji, CJK
    "x\U0001F468\u200D\U0001F469\u200Dy",  # a family inside plain text
]


def test_fit_text_returns_a_prefix_within_budget_for_every_budget():
    for text in NASTY:
        for budget in range(len(text) + 3):
            result = fit_text(text, budget)
            assert text.startswith(result)  # always a prefix
            assert visible_width(result) <= budget  # the hard postcondition


def test_fit_text_cannot_be_extended_by_one_more_character():
    for text in NASTY:
        for budget in range(len(text) + 3):
            result = fit_text(text, budget)
            if len(result) < len(text):
                # The cut is local-greedy: one more character overflows
                # (a later cluster collapse is the documented simplification).
                assert visible_width(text[: len(result) + 1]) > budget


def test_fit_text_returns_whole_text_when_it_fits_and_empty_on_no_budget():
    assert fit_text("abcdef", 6) == "abcdef"
    assert fit_text("abcdef", 99) == "abcdef"
    assert fit_text("\u26a0\ufe0f Blocked", 10) == "\u26a0\ufe0f Blocked"
    assert fit_text("abcdef", 0) == ""
    assert fit_text("abcdef", -3) == ""


def test_ellipsize_tail_postcondition_holds_for_every_budget():
    for text in NASTY:
        for budget in range(len(text) + 3):
            assert visible_width(ellipsize_tail(text, budget)) <= budget


def test_ellipsize_tail_vs16_emoji_stays_within_the_budget():
    # Regression (red before the fix): the old per-character walk measured
    # "\u26a0\ufe0f" as one column while whole-string measurement says two,
    # so the one-column marker pushed the result to five columns at width 4.
    assert visible_width(ellipsize_tail("\u26a0\ufe0f Blocked", 4)) <= 4
    assert ellipsize_tail("\u26a0\ufe0f Blocked", 4) == "\u26a0\ufe0f \u2026"


def test_ellipsize_tail_keeps_its_documented_shape():
    assert ellipsize_tail("abc", 3) == "abc"  # fits: unchanged
    assert ellipsize_tail("abcdef", 4) == "abc\u2026"
    assert ellipsize_tail("abcdef", 1) == "\u2026"
    assert ellipsize_tail("abcdef", 0) == ""
    assert ellipsize_tail("abcdef", -5) == ""
    assert ellipsize_tail("\u65e5\u672c\u8a9e", 4) == "\u65e5\u2026"


def test_line_fit_postcondition_holds_for_every_width():
    # The same nasty inputs as separate segments of one line: Line.fit's
    # inner truncation runs through fit_text now, so the row never
    # overflows -- the second measurement path is gone.
    segments = [Segment(text) for text in NASTY]
    joined = "".join(text for text in NASTY)
    for width in range(len(joined) + 3):
        row = Line(segments).fit(width)
        assert row.width <= width


def test_line_fit_multi_segment_examples():
    row = Line((Segment("ab", ACCENT), Segment("\u26a0\ufe0fx", NONE))).fit(4)
    # Three columns of text survive ("ab" + the bare warning sign, its
    # VS16 selector no longer fits) and the marker takes the fourth.
    assert row.text == "ab\u26a0\u2026" and row.width == 4
    assert row.segments == (Segment("ab", ACCENT), Segment("\u26a0\u2026", NONE))
    # A zero-width run never blocks the marker: the style still fuses.
    assert Line((Segment("\u200d", Style(italic=True)), Segment("abc"))).fit(2).width == 2

"""Tests for mocode_tui.components.markdown (the rule-registry engine)."""

import pytest

from mocode_tui.components.markdown import (
    INLINE_RULES,
    BlockRule,
    FenceRule,
    HeadingRule,
    InlineRule,
    ListRule,
    Markdown,
    ParagraphRule,
    QuoteRule,
    TableRule,
    ThematicBreakRule,
    default_block_rules,
    inline_segments,
)
from mocode_tui.lines import Line, Segment
from mocode_tui.style import ACCENT, CODE, MUTED, NONE, Style

# A document exercising every block type, long enough to sample 200 times at
# ten characters per step (the T4 streaming smoke).
STREAM_DOC = """# Streaming title

A paragraph with `code`, **bold**, *italic* and a [link](https://example.com)
that keeps going so the buffer grows past two thousand characters in total,
which is what the two-hundred-sample smoke needs to step through ten
characters at a time without ever producing a row wider than the width.

The parser must never blow up on a half-typed construct either: a fence that
has not been closed yet still renders its body, a table whose delimiter row
has not arrived yet is still just a paragraph, and an emphasis marker whose
partner has not been typed yet stays literal text.  That is the whole point
of the streaming contract, and this paragraph exists to give the sampler
enough characters to walk the document ten at a time, twice over, while every
intermediate state stays inside the requested width and raises nothing.

Each block rule owns both halves of its job: it decides where its construct
starts and how many lines it eats, and it renders exactly those lines.  The
registry is ordered, the first rule that claims a line wins, and the
paragraph catch-all sits last so nothing is ever dropped on the floor.  A
rule that declines simply returns None and the engine moves on to the next
candidate, which is what keeps classification a flat chain instead of a
nest of special cases, and it is also what makes the whole thing extensible
without patching: a new construct is a new class plus one list entry, and
both the inline and the block side work exactly the same way.  This third
paragraph is here purely to push the sample count past two hundred so the
smoke walks the entire document at ten characters per step, which is a much
harsher test than rendering the finished text in one shot, and the two
hundred samples it asks for are the number the ticket pins, ten characters
per assignment, from the empty buffer all the way to the final newline.

- first item
  - nested item
1. ordered item
2. second ordered item

> a quoted line
> and another

```python
def f(x):
    return x + 1
```

| Name | Score |
|:-----|------:|
| alice | 10 |
| bob | 2 |

---
"""


# --- headings ----------------------------------------------------------------


def test_markdown_empty_renders_no_rows():
    assert Markdown("").render(40) == []


def test_markdown_heading_strips_markers_and_styles():
    rows = Markdown("## Title").render(40)
    assert [row.text for row in rows] == ["Title"]
    assert rows[0].segments[0].style == ACCENT.merge(Style(underline=True))


def test_markdown_heading_levels_share_accent_family():
    styles = [
        Markdown(f"{'#' * level} H").render(40)[0].segments[0].style for level in (1, 2, 3, 4)
    ]
    # Palette-agnostic: the levels are pinned through the semantic constants
    # and attribute shapes, so a palette upgrade never reddens these.
    assert styles[0] == ACCENT  # h1: the accent constant
    assert styles[1] == ACCENT.merge(Style(underline=True))  # h2: accent + underline
    assert not styles[2].bold and not styles[2].dim  # h3: plain
    assert styles[3].dim  # h4: dim


@pytest.mark.parametrize(
    ("level", "style"),
    [
        (5, MUTED.merge(Style(dim=True))),
        (6, MUTED.merge(Style(dim=True, italic=True))),
    ],
)
def test_markdown_deep_headings_settle_on_muted_dim(level, style):
    rows = Markdown(f"{'#' * level} Deep").render(40)
    assert [row.text for row in rows] == ["Deep"]
    assert rows[0].segments[0].style == style


def test_markdown_heading_inline_markup_keeps_the_ladder_base():
    row = Markdown("# **Bold** title").render(40)[0]
    assert row.text == "Bold title"
    assert row.segments[0].style == ACCENT.merge(Style(bold=True))


def test_markdown_heading_can_wrap():
    rows = Markdown("# a very long heading indeed").render(12)
    assert all(row.width <= 12 for row in rows)
    assert "".join(row.text for row in rows).startswith("a very long")


# --- paragraphs --------------------------------------------------------------


def test_markdown_paragraph_joins_soft_breaks():
    rows = Markdown("line one\nline two").render(80)
    assert [row.text for row in rows] == ["line one line two"]


def test_markdown_paragraph_wraps():
    rows = Markdown("the quick brown fox").render(9)
    assert [row.text for row in rows] == ["the quick", "brown fox"]


def test_markdown_blank_rows_separate_blocks_without_gaps():
    rows = Markdown("one\n\ntwo").render(40)
    assert [row.text for row in rows] == ["one", "two"]


def test_markdown_unknown_syntax_degrades_to_paragraph():
    rows = Markdown("| a | b |\n> quoted").render(80)
    # A lone pipe row is not a table (no delimiter row yet) and a quote line
    # is its own block: both render, neither raises.
    assert [row.text for row in rows] == ["| a | b |", "\u2502 quoted"]


# --- lists -------------------------------------------------------------------


def test_markdown_unordered_list_keeps_the_marker():
    rows = Markdown("- one\n* two").render(40)
    assert [row.text for row in rows] == ["- one", "* two"]
    assert rows[0].segments[0] == Segment("- ", MUTED)
    assert rows[1].segments[0] == Segment("* ", MUTED)


def test_markdown_ordered_list_keeps_numbers():
    rows = Markdown("1. first\n2. second").render(40)
    assert [row.text for row in rows] == ["1. first", "2. second"]
    assert rows[0].segments[0] == Segment("1. ", MUTED)


def test_markdown_list_nests_by_indent_two_spaces_per_level():
    rows = Markdown("- top\n  - nested\n    - deep").render(40)
    # Two levels are distinct; a deeper indent caps at the nested level.
    assert [row.text for row in rows] == ["- top", "  - nested", "  - deep"]


def test_markdown_list_item_wraps_with_a_hanging_indent():
    rows = Markdown("- a long item that wraps").render(12)
    assert [row.text for row in rows] == ["- a long", "  item that", "  wraps"]
    assert all(row.width <= 12 for row in rows)


def test_markdown_list_marker_styles_are_muted():
    row = Markdown("1. ten").render(40)[0]
    assert row.segments[0] == Segment("1. ", MUTED)
    assert row.segments[1] == Segment("ten", NONE)


# --- quotes ------------------------------------------------------------------


def test_markdown_quote_prefixes_every_line_with_a_bar():
    rows = Markdown("> first\n> second").render(40)
    assert [row.text for row in rows] == ["\u2502 first", "\u2502 second"]
    assert rows[0].segments[0] == Segment("\u2502 ", MUTED)


def test_markdown_quote_drops_the_marker_and_one_space():
    rows = Markdown(">no space").render(40)
    assert [row.text for row in rows] == ["\u2502 no space"]


def test_markdown_quote_line_wraps():
    rows = Markdown("> a quoted line that wraps").render(12)
    assert all(row.width <= 12 for row in rows)
    assert "".join(row.text for row in rows).startswith("\u2502 a quoted")


# --- fenced code -------------------------------------------------------------


def test_markdown_fenced_code_block():
    rows = Markdown("```\nx = 1\n```").render(40)
    assert [row.text for row in rows] == ["x = 1"]
    assert rows[0].segments == (Segment("x = 1", CODE),)


def test_markdown_fence_drops_the_language_tag():
    rows = Markdown("```python\nx = 1\n```").render(40)
    assert [row.text for row in rows] == ["x = 1"]


def test_markdown_fenced_code_without_close_runs_to_end():
    rows = Markdown("```\nunclosed").render(40)
    assert [row.text for row in rows] == ["unclosed"]
    assert rows[0].segments == (Segment("unclosed", CODE),)


def test_markdown_fence_content_is_verbatim_and_fit():
    rows = Markdown("```\n    indented = 1\n```").render(40)
    assert [row.text for row in rows] == ["    indented = 1"]


def test_markdown_fence_row_is_fit_not_wrapped():
    rows = Markdown("```\na very long code line indeed\n```").render(12)
    assert [row.text for row in rows] == ["a very long\u2026"]
    assert all(row.width <= 12 for row in rows)


# --- tables ------------------------------------------------------------------


def test_markdown_table_shape_and_bold_header():
    rows = Markdown("| Name | Score |\n|---|---|\n| alice | 10 |").render(20)
    assert [row.text for row in rows] == [
        "\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510",
        "\u2502 Name  \u2502 Score \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524",
        "\u2502 alice \u2502 10    \u2502",
        "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518",
    ]
    assert rows[1].segments[1] == Segment(" Name  ", Style(bold=True))


def test_markdown_table_alignment_markers():
    rows = Markdown(
        "| l | c | r |\n|:--|:-:|--:|\n| a | bb | c |\n| longer | x | ccc |"
    ).render(30)
    texts = [row.text for row in rows]
    assert texts[0] == "\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2510"
    assert texts[1] == "\u2502 l      \u2502 c  \u2502   r \u2502"
    assert texts[2] == "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2500\u2524"
    assert texts[3] == "\u2502 a      \u2502 bb \u2502   c \u2502"
    assert texts[4] == "\u2502 longer \u2502 x  \u2502 ccc \u2502"
    assert texts[5] == "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2500\u2518"


def test_markdown_table_without_a_delimiter_row_is_a_paragraph():
    rows = Markdown("| a | b |\n| c | d |").render(40)
    assert [row.text for row in rows] == ["| a | b | | c | d |"]


def test_markdown_table_delimiter_must_match_the_header_cell_count():
    rows = Markdown("| a | b |\n|---|").render(40)
    assert [row.text for row in rows] == ["| a | b | |---|"]


def test_markdown_table_halves_stay_safe():
    # The header alone is a paragraph; the delimiter alone is a paragraph.
    assert [row.text for row in Markdown("| a | b |").render(40)] == ["| a | b |"]
    assert [row.text for row in Markdown("|---|---|").render(40)] == ["|---|---|"]


def test_markdown_table_reuses_the_table_component():
    from mocode_tui.components.table import Table

    source = "| a | b |\n|---|---|\n| 1 | 2 |"
    assert Markdown(source).render(20) == Table(["a", "b"], [["1", "2"]]).render(20)


def test_markdown_table_uses_the_bright_border():
    from mocode_tui.components.table import TABLE_BORDER

    rows = Markdown("| a | b |\n|---|---|\n| 1 | 2 |").render(20)
    assert [row.text for row in rows] == [
        "\u250c\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2510",
        "\u2502 a \u2502 b \u2502",
        "\u251c\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2524",
        "\u2502 1 \u2502 2 \u2502",
        "\u2514\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2518",
    ]
    for row in rows:
        for seg in row.segments:
            if set(seg.text) <= set("\u2502\u251c\u253c\u2524\u2500\u250c\u252c\u2510\u2514\u2534\u2518"):
                assert seg.style == TABLE_BORDER


# --- thematic breaks ---------------------------------------------------------


@pytest.mark.parametrize("source", ["---", "***", "- - -", "* * *"])
def test_markdown_thematic_break_renders_a_divider(source):
    rows = Markdown(source).render(10)
    assert [row.text for row in rows] == ["\u2500" * 10]


def test_markdown_two_dashes_are_not_a_break():
    assert [row.text for row in Markdown("--").render(10)] == ["--"]


# --- inline ------------------------------------------------------------------


def test_markdown_inline_code_bold_italic():
    row = Markdown("a `code` **bold** *em*").render(80)[0]
    assert row.text == "a code bold em"
    styles = {seg.text: seg.style for seg in row.segments}
    assert styles["code"] == CODE
    assert styles["bold"] == Style(bold=True)
    assert styles["em"] == Style(italic=True)


def test_markdown_inline_link_renders_label_and_muted_url():
    row = Markdown("see [docs](https://x.dev) now").render(80)[0]
    assert row.text == "see docs (https://x.dev) now"
    styles = {seg.text: seg.style for seg in row.segments}
    assert styles["docs"] == ACCENT.merge(Style(underline=True))
    assert styles[" (https://x.dev)"] == MUTED


def test_markdown_inline_markers_inside_words_stay_literal():
    row = Markdown("a*b and 2*3 and `oops").render(80)[0]
    assert row.text == "a*b and 2*3 and `oops"
    assert row.segments[0].style == NONE


def test_markdown_inline_unclosed_markers_stay_literal():
    row = Markdown("**half and *half and [t](u").render(80)[0]
    assert row.text == "**half and *half and [t](u"
    assert row.segments[0].style == NONE


def test_markdown_inline_stars_inside_bold_stay_put():
    row = Markdown("**a*b**").render(80)[0]
    assert row.text == "a*b"
    assert row.segments[0].style == Style(bold=True)


def test_inline_segments_merges_attribute_styles_onto_the_base():
    segs = inline_segments("**x**", ACCENT)
    assert segs == [Segment("x", ACCENT.merge(Style(bold=True)))]


# --- streaming safety --------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "```python\nx = 1\n```",
        "| a | b |\n|---|---|\n| 1 | 2 |",
        "a `code` **bold** *em* [t](u)",
        "# title\n\n- item\n\n> quote\n\n---\n",
    ],
)
def test_markdown_every_prefix_is_safe_and_fits(source):
    for size in range(len(source) + 1):
        rows = Markdown(source[:size]).render(24)
        assert all(row.width <= 24 for row in rows)


def test_markdown_streaming_two_hundred_samples():
    width = 46
    samples = list(range(0, len(STREAM_DOC) + 1, 10))
    assert len(samples) >= 200  # ten characters per step, two hundred samples
    for size in samples:
        rows = Markdown(STREAM_DOC[:size]).render(width)
        assert rows or size == 0
        assert all(row.width <= width for row in rows)


# --- registry extensibility --------------------------------------------------


class _StrikeInlineRule:
    """A custom inline rule: ``~~text~~`` in dim."""

    name = "strike"

    def match(self, text: str, pos: int) -> tuple[int, list[Segment]] | None:
        if not text.startswith("~~", pos):
            return None
        end = text.find("~~", pos + 2)
        if end < 0:
            return None
        return end + 2, [Segment(text[pos + 2 : end], Style(dim=True))]


class _ShoutBlockRule:
    """A custom block rule: lines starting with ``!`` render upper-cased."""

    name = "shout"

    def match(self, lines: list[str], i: int) -> int | None:
        return 1 if lines[i].startswith("!") else None

    def render(self, lines: list[str], width: int) -> list[Line]:
        return [Line.from_text(lines[0][1:].strip().upper()).fit(width)]


def test_custom_inline_rule_joins_the_registry():
    md = Markdown("a ~~b~~ c", inline_rules=[_StrikeInlineRule(), *INLINE_RULES])
    row = md.render(40)[0]
    assert row.text == "a b c"
    assert {seg.text: seg.style for seg in row.segments}["b"] == Style(dim=True)


def test_custom_block_rule_interrupts_paragraphs_and_renders():
    md = Markdown(
        "para one\n!shout\npara two",
        block_rules=[_ShoutBlockRule(), *default_block_rules()],
    )
    assert [row.text for row in md.render(40)] == ["para one", "SHOUT", "para two"]


def test_custom_inline_rules_reach_the_builtin_blocks():
    md = Markdown(
        "# ~~title~~\n\n- ~~item~~",
        inline_rules=[_StrikeInlineRule(), *INLINE_RULES],
    )
    rows = md.render(40)
    assert rows[0].text == "title"
    assert rows[0].segments[0].style == ACCENT.merge(Style(dim=True))
    assert rows[1].text == "- item"


def test_registries_are_ordered_lists_of_rules():
    assert [type(rule).__name__ for rule in default_block_rules()] == [
        "HeadingRule",
        "FenceRule",
        "TableRule",
        "ThematicBreakRule",
        "QuoteRule",
        "ListRule",
        "ParagraphRule",
    ]
    assert [rule.name for rule in INLINE_RULES] == ["code", "bold", "italic", "link"]


def test_rule_protocols_are_structural():
    for rule in default_block_rules():
        assert isinstance(rule.name, str)
        assert callable(rule.match) and callable(rule.render)
    for rule in INLINE_RULES:
        assert isinstance(rule.name, str)
        assert callable(rule.match)


# --- degenerate --------------------------------------------------------------


def test_markdown_degenerate_widths_do_not_crash():
    rows = Markdown("# heading\n\n- item\n\n> q\n\n| a |\n|---|\n\n---").render(1)
    assert all(row.width <= 1 for row in rows)
    rows0 = Markdown("para").render(0)
    assert all(row.width == 0 for row in rows0)


def test_markdown_repr_shows_the_text():
    assert repr(Markdown("hi")) == "Markdown('hi')"

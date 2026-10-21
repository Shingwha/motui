"""Markdown: block rules, inline rules, links, tasks, streaming and the cap."""

from dataclasses import replace

from motui.kernel.lines import Line
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import Markdown
from motui.widgets.markdown import default_block_rules

from tests.testing import texts


def test_headings_strip_their_markers_and_keep_the_rules():
    assert texts(Markdown("## Title"), 80) == ["Title"]
    assert texts(Markdown("### Deep"), 80) == ["### Deep"]
    assert Markdown("# H").render(80)[0].segments[0].style == DEFAULT_THEME.headings[0].merge(
        Style(underline=True)
    )


def test_paragraphs_join_soft_breaks_and_blocks_are_separated_by_one_gap():
    assert texts(Markdown("line one\nline two"), 80) == ["line one line two"]
    assert texts(Markdown("one\n\n\n\ntwo"), 80) == ["one", "", "two"]
    assert texts(Markdown("one\n\ntwo", gap=0), 80) == ["one", "two"]
    assert texts(Markdown(""), 80) == []


def test_lists_keep_the_marker_and_nest_by_indent():
    assert texts(Markdown("- one\n* two\n1. first"), 80) == ["- one", "* two", "1. first"]
    assert texts(Markdown("- top\n  - nested\n    - deep"), 80) == [
        "- top",
        "  - nested",
        "  - deep",
    ]


def test_quotes_render_behind_a_muted_bar_and_stack_per_level():
    rows = Markdown("> first\n> second").render(80)
    assert rows[0].text == "\u2502 first second"
    assert rows[0].segments[0].text == "\u2502 "
    assert rows[0].segments[1].style == Style(italic=True)
    assert texts(Markdown("> a\n>\n> > b"), 80) == ["\u2502 a", "\u2502 \u2502 b"]


def test_fenced_code_parses_the_tag_and_runs_to_the_end():
    closed = Markdown("```python\nx = 1\n```").render(80)
    assert [row.text for row in closed] == ["```python", "x = 1", "```"]
    assert closed[1].segments[1].text == "1"
    assert closed[1].segments[1].style == DEFAULT_THEME.warning
    unclosed = Markdown("```\nunclosed").render(80)
    assert [row.text for row in unclosed] == ["```", "unclosed"]


def test_a_table_needs_both_its_header_and_delimiter_rows():
    rows = Markdown("| Name | Score |\n|---|---|\n| alice | 10 |").render(20)
    assert [row.text for row in rows] == [
        "\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510",
        "\u2502 Name  \u2502 Score \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524",
        "\u2502 alice \u2502 10    \u2502",
        "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518",
    ]
    assert texts(Markdown("| a | b |"), 40) == ["| a | b |"]
    assert texts(Markdown("|---|---|"), 40) == ["|---|---|"]


def test_thematic_breaks_are_capped_by_divider_max_width():
    assert texts(Markdown("---"), 10) == ["\u2500" * 10]
    assert texts(Markdown("--"), 10) == ["--"]
    assert texts(Markdown("---"), 120) == ["\u2500" * 80]
    assert texts(Markdown("---", divider_max_width=None), 120) == ["\u2500" * 120]
    assert texts(Markdown("---", divider_max_width=5), 120) == ["\u2500" * 5]


def test_inline_code_bold_italic_strike_and_links_render_their_text():
    row = Markdown("a `code` **bold** *em* ~~out~~ [t](u)").render(80)[0]
    assert row.text == "a code bold em out t"
    styles = {seg.text: seg.style for seg in row.segments}
    assert styles["code"] == DEFAULT_THEME.inline_code
    assert styles["bold"] == Style(bold=True)
    assert styles["em"] == Style(italic=True)
    assert styles["out"] == Style(strike=True)


def test_a_link_click_leaves_its_url_pending_once():
    md = Markdown("see [docs](https://example.test)")
    md.render(40)
    assert md.click(0, 5) is True
    assert md.take_result() == "https://example.test"
    assert md.take_result() is None
    assert md.click(0, 0) is False


def test_a_link_hover_marks_the_span_and_clears_back():
    theme = replace(DEFAULT_THEME, surfaces=replace(DEFAULT_THEME.surfaces, hover=Style(reverse=True)))
    md = Markdown("[docs](u)", theme=theme)
    plain = md.render(20)
    assert md.hover_at(0, 0) is True
    assert md.render(20)[0].segments[0].style.reverse is True
    assert md.hover_at(0, 0) is False
    assert md.hover_at(-1, -1) is True
    assert md.render(20) == plain


def test_every_streaming_prefix_renders_safely_within_the_width():
    source = "# H\n\npara **bold**\n\n- item\n\n```py\nx = 1\n```\n\n> quote"
    md = Markdown("")
    for end in range(len(source) + 1):
        md.text = source[:end]
        assert all(row.width <= 20 for row in md.render(20))


def test_max_width_caps_the_wrap_and_never_pads():
    md = Markdown("the quick brown fox", max_width=9)
    assert texts(md, 80) == ["the quick", "brown fox"]
    assert all(row.width <= 9 for row in md.render(80))


def test_task_items_render_a_box_and_click_with_their_flat_ordinal():
    md = Markdown("- [ ] first\n- [x] second")
    assert texts(md, 40) == ["\u2610 first", "\u2611 second"]
    md.render(40)
    assert md.click(1, 0) is True and md.take_result() == "todo:1"
    assert md.click(1, 5) is False


def test_fences_reports_the_top_level_code_blocks():
    md = Markdown("```python\nx = 1\n```\n\ntext\n\n```\nplain\n```")
    assert md.fences() == [("python", "x = 1"), ("", "plain")]
    assert md.fences() == [("python", "x = 1"), ("", "plain")]


def test_a_custom_block_rule_interrupts_a_paragraph():
    class Shout:
        name = "shout"

        def match(self, lines, index):
            return 1 if lines[index].startswith("!") else None

        def render(self, lines, width, ctx):
            return [Line.from_text(lines[0][1:].strip().upper()).fit(width)]

    md = Markdown("para\n!loud", block_rules=[Shout(), *default_block_rules()])
    assert texts(md, 20) == ["para", "", "LOUD"]

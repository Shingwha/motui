"""Tests for mocode_tui.widgets.syntax (the built-in highlighter).

A per-language table of ordered regex rules colors five theme-derived token
classes; unknown languages fall back to monochrome; custom tables override.
"""

from dataclasses import replace

import pytest

from mocode_tui.core.lines import Line
from mocode_tui.core.style import Style
from mocode_tui.core.text import visible_width
from mocode_tui.core.theme import DEFAULT_THEME
from mocode_tui.widgets.markdown import Markdown
from mocode_tui.widgets.syntax import (
    Highlighter,
    RegexHighlighter,
    default_highlighter,
    highlight,
)

# The token classes the table asserts, derived from DEFAULT_THEME -- the same
# derivation the engine performs, so retuning a hex never turns this red.
COMMENT = DEFAULT_THEME.muted.merge(Style(italic=True))
STRING = DEFAULT_THEME.success
NUMBER = DEFAULT_THEME.warning
KEYWORD = Style(fg=DEFAULT_THEME.accent.fg)
PLAIN = DEFAULT_THEME.code  # plain code and the builtin token share this color
MUTED = DEFAULT_THEME.muted  # a fenced block's marker rows
NAMES = {
    COMMENT: "COMMENT",
    STRING: "STRING",
    NUMBER: "NUMBER",
    KEYWORD: "KEYWORD",
    PLAIN: "PLAIN",
    MUTED: "MUTED",
}


def _tokens(row: Line) -> list[tuple[str, str]]:
    """One ``(text, token-class name)`` run per segment of ``row``."""
    return [(seg.text, NAMES[seg.style]) for seg in row.segments]


def _rows(
    code: str, lang: str, engine: Highlighter | None = None
) -> list[list[tuple[str, str]]]:
    built = engine if engine is not None else RegexHighlighter()
    return [_tokens(row) for row in built.highlight(code, lang)]


# One table for every built-in language: the tag, a sample that shows its
# characteristic tokens across as many rows as it needs, and the exact runs it
# colors.  Builtins share the plain color and fuse with it, which is why
# several rows read as a single run.
@pytest.mark.parametrize(
    ("lang", "code", "expected"),
    [
        (
            "python",
            '# note\ndef f():\n    return 1\n    y = "s"',
            [
                [("# note", "COMMENT")],
                [("def", "KEYWORD"), (" f():", "PLAIN")],
                [("    ", "PLAIN"), ("return", "KEYWORD"), (" ", "PLAIN"), ("1", "NUMBER")],
                [("    y = ", "PLAIN"), ('"s"', "STRING")],
            ],
        ),
        # A string swallows the comment marker and the keywords inside it.
        (
            "python",
            'x = "# not a comment"',
            [[("x = ", "PLAIN"), ('"# not a comment"', "STRING")]],
        ),
        (
            "javascript",
            'const x = "hi"; // tail\nconst x = 1;',
            [
                [
                    ("const", "KEYWORD"),
                    (" x = ", "PLAIN"),
                    ('"hi"', "STRING"),
                    ("; ", "PLAIN"),
                    ("// tail", "COMMENT"),
                ],
                [("const", "KEYWORD"), (" x = ", "PLAIN"), ("1", "NUMBER"), (";", "PLAIN")],
            ],
        ),
        # TypeScript is JavaScript plus the type-level keywords and primitives.
        (
            "typescript",
            "let x: number = 1;",
            [
                [
                    ("let", "KEYWORD"),
                    (" x: ", "PLAIN"),
                    ("number", "KEYWORD"),
                    (" = ", "PLAIN"),
                    ("1", "NUMBER"),
                    (";", "PLAIN"),
                ]
            ],
        ),
        (
            "bash",
            'echo "hi" # tail',
            [[("echo ", "PLAIN"), ('"hi"', "STRING"), (" ", "PLAIN"), ("# tail", "COMMENT")]],
        ),
        (
            "json",
            '{"a": 1, "b": true}',
            [
                [
                    ("{", "PLAIN"),
                    ('"a"', "KEYWORD"),  # object key
                    (": ", "PLAIN"),
                    ("1", "NUMBER"),
                    (", ", "PLAIN"),
                    ('"b"', "KEYWORD"),
                    (": ", "PLAIN"),
                    ("true", "KEYWORD"),
                    ("}", "PLAIN"),
                ]
            ],
        ),
        (
            "yaml",
            "key: value # tail\nkey: value",
            [
                [("key", "KEYWORD"), (": value ", "PLAIN"), ("# tail", "COMMENT")],
                [("key", "KEYWORD"), (": value", "PLAIN")],
            ],
        ),
        (
            "toml",
            '[tool]\nname = "x"',
            [
                [("[tool]", "KEYWORD")],
                [("name", "KEYWORD"), (" = ", "PLAIN"), ('"x"', "STRING")],
            ],
        ),
        (
            "markdown",
            "# title\n`code` **b** y",
            [
                [("# title", "KEYWORD")],
                [("`code`", "STRING"), (" **b** y", "PLAIN")],
            ],
        ),
        (
            "diff",
            " ctx\n-old\n+new",
            [
                [(" ctx", "COMMENT")],  # context line
                [("-old", "COMMENT")],  # removed: the comment style, by design
                [("+new", "STRING")],  # added
            ],
        ),
        (
            "rust",
            "fn main() -> i32 { 1 }",
            [
                [
                    ("fn", "KEYWORD"),
                    (" main() -> i32 { ", "PLAIN"),
                    ("1", "NUMBER"),
                    (" }", "PLAIN"),
                ]
            ],
        ),
        (
            "go",
            "func main() { println(1) }",
            [
                [
                    ("func", "KEYWORD"),
                    (" main() { println(", "PLAIN"),
                    ("1", "NUMBER"),
                    (") }", "PLAIN"),
                ]
            ],
        ),
        (
            "c",
            "#include <stdio.h>\nint x = 1;",
            [
                [("#include", "KEYWORD"), (" <stdio.h>", "PLAIN")],
                [("int", "KEYWORD"), (" x = ", "PLAIN"), ("1", "NUMBER"), (";", "PLAIN")],
            ],
        ),
        (
            "cpp",
            "auto x = 1;",
            [[("auto", "KEYWORD"), (" x = ", "PLAIN"), ("1", "NUMBER"), (";", "PLAIN")]],
        ),
        (
            "c++",
            "template <class T> struct S;",
            [
                [
                    ("template", "KEYWORD"),
                    (" <", "PLAIN"),
                    ("class", "KEYWORD"),
                    (" T> ", "PLAIN"),
                    ("struct", "KEYWORD"),
                    (" S;", "PLAIN"),
                ]
            ],
        ),
        (
            "html",
            '<a href="u">x</a>',
            [
                [
                    ("<a", "KEYWORD"),
                    (" href=", "PLAIN"),
                    ('"u"', "STRING"),
                    (">x", "PLAIN"),
                    ("</a", "KEYWORD"),
                    (">", "PLAIN"),
                ]
            ],
        ),
        (
            "css",
            ".a { color: #fff; }",
            [[(".a", "KEYWORD"), (" { color: ", "PLAIN"), ("#fff", "NUMBER"), ("; }", "PLAIN")]],
        ),
        (
            "sql",
            "SELECT 1 FROM t WHERE a = 'x' -- tail",
            [
                [
                    ("SELECT", "KEYWORD"),
                    (" ", "PLAIN"),
                    ("1", "NUMBER"),
                    (" ", "PLAIN"),
                    ("FROM", "KEYWORD"),
                    (" t ", "PLAIN"),
                    ("WHERE", "KEYWORD"),
                    (" a = ", "PLAIN"),
                    ("'x'", "STRING"),
                    (" ", "PLAIN"),
                    ("-- tail", "COMMENT"),
                ]
            ],
        ),
    ],
)
def test_per_language_token_runs(lang, code, expected):
    assert _rows(code, lang) == expected


def test_a_fence_highlights_the_tagged_body_row_by_row():
    """The fence hands the tag-parsed body to the engine, one row per code
    line, and keeps its markers in the muted container style."""
    rows = Markdown("```python\n# note\ndef f():\n    return 1\n```").render(80)
    assert [row.text for row in rows] == [
        "```python",
        "# note",
        "def f():",
        "    return 1",
        "```",
    ]
    assert _tokens(rows[0]) == [("```python", "MUTED")]
    assert _tokens(rows[1]) == [("# note", "COMMENT")]
    assert _tokens(rows[2]) == [("def", "KEYWORD"), (" f():", "PLAIN")]
    assert _tokens(rows[3]) == [
        ("    ", "PLAIN"),
        ("return", "KEYWORD"),
        (" ", "PLAIN"),
        ("1", "NUMBER"),
    ]


def test_an_untagged_or_unknown_tag_renders_the_body_monochrome():
    for text, opening in (
        ("```\nplain body\n```", "```"),
        ("```brainfuck\nplain body\n```", "```brainfuck"),
    ):
        rows = Markdown(text).render(80)
        assert [row.text for row in rows] == [opening, "plain body", "```"]
        assert _tokens(rows[0]) == [(opening, "MUTED")]  # the markers render muted
        assert _tokens(rows[1]) == [("plain body", "PLAIN")]  # the body stays monochrome


def test_aliases_resolve_to_the_same_rules():
    built = RegexHighlighter()
    assert built.highlight("const x = 1;", "js") == built.highlight("const x = 1;", "javascript")
    assert built.highlight("key: value", "yml") == built.highlight("key: value", "yaml")


def test_unknown_and_empty_languages_fall_back_to_monochrome():
    for lang in ("", "brainfuck", "py3"):
        assert _rows("whatever 42", lang) == [[("whatever 42", "PLAIN")]]


def test_language_tags_are_normalized_and_may_carry_attributes():
    built = RegexHighlighter()
    assert built.highlight("x = 1", "PY") == built.highlight("x = 1", "python")
    assert built.highlight("x = 1", " Python ") == built.highlight("x = 1", "python")
    assert built.highlight("x = 1", "python title=foo") == built.highlight("x = 1", "python")


def test_empty_code_is_one_empty_line_per_row():
    assert RegexHighlighter().highlight("", "python") == [Line()]
    assert RegexHighlighter().highlight("\n\n", "python") == [Line(), Line(), Line()]


def test_a_wide_character_line_never_shifts():
    code = 's = "\u4f60\u597d"  # \u4e2d\u6587'
    row = RegexHighlighter().highlight(code, "python")[0]
    assert row.text == code  # nothing dropped, nothing duplicated
    assert row.width == visible_width(code)


def test_block_constructs_are_approximated_per_line():
    # No cross-line state: a triple-quoted opener keeps the rest of its line
    # and every later line uncolored (documented in the module docstring).
    rows = RegexHighlighter().highlight('"""doc\nstill doc\nend"""', "python")
    assert "".join(seg.text for seg in rows[1].segments) == "still doc"
    assert all(seg.style == PLAIN for seg in rows[1].segments)


def test_token_colors_follow_the_theme():
    # Round-trip: an injected style comes back out; no default is pinned.
    theme = replace(DEFAULT_THEME, warning=Style(fg="#abcdef"))
    row = RegexHighlighter(theme=theme).highlight("n = 1", "python")[0]
    assert [(seg.text, seg.style) for seg in row.segments] == [
        ("n = ", theme.code),
        ("1", theme.warning),
    ]


def test_custom_languages_extend_and_override_the_table():
    built = RegexHighlighter(
        languages={
            "toy": [(r"#.*", "comment"), (r"\bwow\b", "keyword"), (r"!!", Style(fg="#ff0000"))],
            "python": [(r".*", "string")],
        }
    )
    # An explicit Style passes through instead of resolving against the theme.
    toy = built.highlight("wow !! # hi", "toy")[0]
    assert [(seg.text, seg.style) for seg in toy.segments] == [
        ("wow", KEYWORD),
        (" ", PLAIN),
        ("!!", Style(fg="#ff0000")),
        (" ", PLAIN),
        ("# hi", COMMENT),
    ]
    assert _rows("def f(): pass", "python", built) == [[("def f(): pass", "STRING")]]
    # Unmentioned built-ins survive; the override is per normalized key, so
    # the 'py' alias still points at the stock Python rules.
    assert built.highlight("const x = 1;", "js") == RegexHighlighter().highlight(
        "const x = 1;", "javascript"
    )
    assert built.highlight("def f(): pass", "py") == RegexHighlighter().highlight(
        "def f(): pass", "python"
    )


def test_an_unknown_token_name_fails_at_construction():
    with pytest.raises(ValueError):
        RegexHighlighter(languages={"toy": [("a", "bogus")]})


def test_default_highlighter_is_built_once_and_is_a_highlighter():
    assert default_highlighter() is default_highlighter()
    assert isinstance(default_highlighter(), Highlighter)


def test_highlight_entry_matches_the_highlighter_and_honors_an_injected_engine():
    assert highlight("x = 1", "python") == RegexHighlighter().highlight("x = 1", "python")

    class Stub:
        def highlight(self, code, lang):
            return [Line.from_text(f"{lang}:{code}", Style(bold=True))]

    # An explicit highlighter wins and `theme` is ignored.
    stub = Stub()
    assert highlight("body", "python", highlighter=stub, theme=DEFAULT_THEME) == [
        Line.from_text("python:body", Style(bold=True))
    ]

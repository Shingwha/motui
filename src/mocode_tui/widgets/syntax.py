"""Built-in lightweight syntax highlighting for fenced code blocks.

Zero dependencies by contract: this module is pure :mod:`re` over the kernel
(:class:`mocode_tui.core.lines.Line`/:class:`mocode_tui.core.lines.Segment`,
:class:`mocode_tui.core.style.Style`, :class:`mocode_tui.core.theme.Theme`).
A :class:`Highlighter` turns ``(code, lang)`` into one
:class:`~mocode_tui.core.lines.Line` per logical line; :class:`RegexHighlighter`
is the built-in implementation -- an ordered table of per-language regex rules
resolved against a theme's semantic colors.

Five token classes, colored from :class:`~mocode_tui.core.theme.Theme`
(``Theme()`` defaults in parentheses)::

    comment   muted + italic
    string    success (green)
    number    warning (amber)
    keyword   accent's hue (blue), weight-neutral
    builtin   code (ice blue)

No token carries weight: code blocks stay weight-neutral, so the only bold
in a default render remains the ``**...**`` syntax itself.

Rules match first-come, first-served at each scan position, and every line is
matched on its own -- there is no cross-line state.  Block comments and
multi-line strings are therefore an in-line approximation: a ``/*`` or a
triple-quoted string whose partner sits on a later line is left uncolored
(kept as plain code text) instead of guessed.  Text no rule claims stays in
the theme's ``code`` style, which is also the whole-line style for an unknown
or missing language tag.

All patterns compile at construction time and ``highlight`` does no IO, so a
highlighter instance is safe to build once and share.  Inject your own
highlighter (any object with ``highlight(code, lang) -> list[Line]``) to
replace the engine entirely, and your own language table via
``RegexHighlighter(languages=...)`` to extend or override the built-ins.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from ..core.lines import Line, Segment, fuse
from ..core.style import Style
from ..core.theme import DEFAULT_THEME, Theme

__all__ = [
    "Highlighter",
    "RegexHighlighter",
    "default_highlighter",
    "highlight",
]


# --- protocol -----------------------------------------------------------------


@runtime_checkable
class Highlighter(Protocol):
    """Turns ``(code, lang)`` into one :class:`Line` per logical line.

    ``lang`` is the raw language tag from the caller (``RegexHighlighter``
    normalizes it); an implementation may ignore it.  Returning an empty list
    for a non-empty code is allowed but renders nothing.
    """

    def highlight(self, code: str, lang: str) -> list[Line]: ...


# --- shared pattern atoms ------------------------------------------------------


# A decimal / 0x..0o..0b.. number that is not part of an identifier (so the
# ``1`` in ``x1`` and the ``2`` in ``3.14.15`` stay plain).
_NUMBER = r"(?<![\w.])(?:0[xXoObB][0-9a-fA-F]+|\d+(?:\.\d+)?)(?![\w.])"

# A one-line block comment (the pairing delimiter on a later line is *not*
# colored: matching is per-line, by design).
_C_COMMENT = r"/\*.*?\*/"

# A C-family single line comment.
_CPP_COMMENT = r"//.*"

# A single- or double-quoted string with backslash escapes (single line).
_QUOTED = r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\''

# A ``#`` that opens a comment: at line start or after whitespace (so a ``#``
# inside a word or a URL stays literal).
_HASH_COMMENT = r"(?:(?<=\s)|(?<=^))#.*"

# A Python string literal, ``r``/``b``/``f``/``u`` prefixes allowed.
_PY_STRING = (
    r'(?:[rbfuRBFU]{0,2})"(?:[^"\\\n]|\\.)*"'
    r"|(?:[rbfuRBFU]{0,2})'(?:[^'\\\n]|\\.)*'"
)


def _py_rules() -> list[tuple[str, str]]:
    keywords = (
        r"\b(?:False|None|True|and|as|assert|async|await|break|class|continue"
        r"|def|del|elif|else|except|finally|for|from|global|if|import|in|is"
        r"|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b"
    )
    builtins = (
        r"\b(?:abs|all|any|bool|bytes|dict|dir|enumerate|filter|float|format"
        r"|frozenset|getattr|hasattr|hash|id|input|int|isinstance|issubclass"
        r"|iter|len|list|map|max|min|next|object|open|ord|print|range|repr"
        r"|reversed|round|set|setattr|sorted|str|sum|super|tuple|type|vars"
        r"|zip)\b"
    )
    return [
        (r"#.*", "comment"),
        (r'""".*?"""', "string"),
        (r"'''.*?'''", "string"),
        (_PY_STRING, "string"),
        (_NUMBER, "number"),
        (keywords, "keyword"),
        (builtins, "builtin"),
    ]


def _js_rules() -> list[tuple[str, str]]:
    keywords = (
        r"\b(?:async|await|break|case|catch|class|const|continue|debugger"
        r"|default|delete|do|else|enum|export|extends|false|finally|for|from"
        r"|function|get|if|import|in|instanceof|let|new|null|of|return|set"
        r"|static|super|switch|this|throw|true|try|typeof|undefined|var|void"
        r"|while|with|yield)\b"
    )
    builtins = (
        r"\b(?:Array|Boolean|console|Date|document|Error|fetch|globalThis"
        r"|JSON|Map|Math|module|Number|Object|parseFloat|parseInt|process"
        r"|Promise|Proxy|Reflect|RegExp|require|Set|setInterval|setTimeout"
        r"|String|Symbol|WeakMap|window)\b"
    )
    return [
        (_CPP_COMMENT, "comment"),
        (_C_COMMENT, "comment"),
        (_QUOTED, "string"),
        (r"`(?:[^`\\]|\\.)*`", "string"),
        (_NUMBER, "number"),
        (keywords, "keyword"),
        (builtins, "builtin"),
    ]


def _ts_rules() -> list[tuple[str, str]]:
    # TypeScript is JavaScript plus the type-level keywords and primitives.
    extra_keywords = (
        r"\b(?:abstract|declare|implements|infer|interface|is|keyof"
        r"|namespace|private|protected|public|readonly|type)\b"
    )
    primitives = r"\b(?:any|bigint|boolean|never|number|object|string|symbol|unknown)\b"
    return [*_js_rules(), (extra_keywords, "keyword"), (primitives, "keyword")]


def _bash_rules() -> list[tuple[str, str]]:
    keywords = (
        r"\b(?:case|do|done|elif|else|esac|fi|for|function|if|in|select|then"
        r"|time|until|while)\b"
    )
    builtins = (
        r"\b(?:alias|bg|bind|break|builtin|caller|cd|command|compgen|complete"
        r"|continue|declare|dirs|disown|echo|enable|eval|exec|exit|export"
        r"|false|fc|fg|getopts|hash|help|history|jobs|kill|let|local|logout"
        r"|popd|printf|pushd|pwd|read|readonly|return|set|shift|shopt|source"
        r"|suspend|test|times|trap|true|type|typeset|ulimit|umask|unalias"
        r"|unset|wait)\b"
    )
    return [
        (_HASH_COMMENT, "comment"),
        (_QUOTED, "string"),
        (_NUMBER, "number"),
        (keywords, "keyword"),
        (builtins, "builtin"),
    ]


def _json_rules() -> list[tuple[str, str]]:
    return [
        (r'"(?:[^"\\\n]|\\.)*"(?=\s*:)', "keyword"),  # object key
        (r'"(?:[^"\\\n]|\\.)*"', "string"),
        (_NUMBER, "number"),
        (r"\b(?:true|false|null)\b", "keyword"),
    ]


def _yaml_rules() -> list[tuple[str, str]]:
    return [
        (_HASH_COMMENT, "comment"),
        (_QUOTED, "string"),
        (r"^\s*-?\s*[\w.-]+(?=\s*:)", "keyword"),  # mapping key
        (_NUMBER, "number"),
        (r"(?i)\b(?:true|false|null|yes|no)\b", "keyword"),
    ]


def _toml_rules() -> list[tuple[str, str]]:
    return [
        (r"#.*", "comment"),
        (r"^\s*\[.*\]\s*$", "keyword"),  # table header
        (_QUOTED, "string"),
        (r"^\s*[\w.-]+(?=\s*=)", "keyword"),  # bare key
        (_NUMBER, "number"),
        (r"\b(?:true|false)\b", "keyword"),
    ]


def _md_rules() -> list[tuple[str, str]]:
    return [
        (r"^#{1,6} .*", "keyword"),  # ATX heading
        (r"`[^`\n]*`", "string"),  # inline code
        (r"\*\*[^*\n]+\*\*", "builtin"),  # strong
        (r"\*[^*\n]+\*", "builtin"),  # emphasis
        (r"^\s*>.*", "comment"),  # block quote
    ]


def _diff_rules() -> list[tuple[str, str]]:
    # Removed lines reuse the comment style: the token vocabulary stays the
    # five semantic classes (no red token, by design).
    return [
        (r"^@@.*@@", "keyword"),
        (r"^\+\+\+.*$", "builtin"),
        (r"^---.*$", "builtin"),
        (r"^[+].*$", "string"),  # added line
        (r"^-.+$", "comment"),  # removed line
        (r"^ .*", "comment"),  # context line (leading space)
        (r"^[^+\-@ ].*", "comment"),  # any other non-marker line
    ]


def _rust_rules() -> list[tuple[str, str]]:
    keywords = (
        r"\b(?:as|async|await|break|const|continue|crate|dyn|else|enum"
        r"|extern|false|fn|for|if|impl|in|let|loop|match|mod|move|mut|pub"
        r"|ref|return|self|Self|static|struct|super|trait|true|type|unsafe"
        r"|use|where|while)\b"
    )
    builtins = (
        r"\b(?:Arc|Box|HashMap|HashSet|Option|Rc|RefCell|Result|String|Vec"
        r"|bool|char|f32|f64|i128|i16|i32|i64|i8|isize|str|u128|u16|u32"
        r"|u64|u8|usize)\b"
    )
    return [
        (_CPP_COMMENT, "comment"),
        (_C_COMMENT, "comment"),
        (r'r#"[^"]*"#', "string"),  # raw string
        (_QUOTED, "string"),
        (r"'(?:[^'\\\n]|\\.)'", "string"),  # char literal / lifetime-ish
        (_NUMBER, "number"),
        (keywords, "keyword"),
        (builtins, "builtin"),
    ]


def _go_rules() -> list[tuple[str, str]]:
    keywords = (
        r"\b(?:break|case|chan|const|continue|default|defer|else|fallthrough"
        r"|for|func|go|goto|if|import|interface|map|package|range|return"
        r"|select|struct|switch|type|var)\b"
    )
    builtins = (
        r"\b(?:any|append|bool|byte|cap|clear|close|complex|complex128"
        r"|complex64|copy|delete|error|false|float32|float64|int|int16|int32"
        r"|int64|int8|iota|len|make|max|min|new|nil|panic|print|println"
        r"|real|recover|rune|string|true|uint|uint16|uint32|uint64|uint8"
        r"|uintptr)\b"
    )
    return [
        (_CPP_COMMENT, "comment"),
        (_C_COMMENT, "comment"),
        (r"`[^`\n]*`", "string"),  # raw string
        (_QUOTED, "string"),
        (_NUMBER, "number"),
        (keywords, "keyword"),
        (builtins, "builtin"),
    ]


def _c_rules() -> list[tuple[str, str]]:
    keywords = (
        r"\b(?:auto|break|case|char|const|continue|default|do|double|else"
        r"|enum|extern|float|for|goto|if|inline|int|long|register|restrict"
        r"|return|short|signed|sizeof|static|struct|switch|typedef|union"
        r"|unsigned|void|volatile|while)\b"
    )
    builtins = (
        r"\b(?:bool|calloc|fclose|fopen|fprintf|free|int16_t|int32_t|int64_t"
        r"|int8_t|intptr_t|malloc|memcpy|memset|ptrdiff_t|realloc|size_t"
        r"|ssize_t|strcat|strcmp|strcpy|strlen|uint16_t|uint32_t|uint64_t"
        r"|uint8_t)\b"
    )
    return [
        (_CPP_COMMENT, "comment"),
        (_C_COMMENT, "comment"),
        (r"^\s*#\s*\w+", "keyword"),  # preprocessor directive
        (_QUOTED, "string"),
        (_NUMBER, "number"),
        (keywords, "keyword"),
        (builtins, "builtin"),
    ]


def _cpp_rules() -> list[tuple[str, str]]:
    extra_keywords = (
        r"\b(?:catch|class|consteval|constexpr|constinit|decltype|delete"
        r"|explicit|final|friend|mutable|namespace|new|noexcept|nullptr"
        r"|operator|override|private|protected|public|static_assert|template"
        r"|this|throw|try|typename|using|virtual)\b"
    )
    return [*_c_rules(), (extra_keywords, "keyword")]


def _html_rules() -> list[tuple[str, str]]:
    return [
        (r"<!--.*?-->", "comment"),
        (r"(?i)<!DOCTYPE[^>]*>", "comment"),
        (r"</?[A-Za-z][\w:.-]*", "keyword"),  # tag name
        (r"[A-Za-z_:][\w:.-]*(?=\s*=)", "builtin"),  # attribute name
        (r'"[^"\n]*"', "string"),
        (r"'[^'\n]*'", "string"),
    ]


def _css_rules() -> list[tuple[str, str]]:
    return [
        (r"/\*.*?\*/", "comment"),
        (r"@[\w-]+", "keyword"),  # at-rule
        (r"[-a-zA-Z]+(?=\s*:)", "builtin"),  # property
        (r"[.\w-]+(?=[^;{}]*\{)", "keyword"),  # selector before a block
        (r'"[^"\n]*"', "string"),
        (r"'[^'\n]*'", "string"),
        (r"#[0-9a-fA-F]{3,8}\b", "number"),  # hex color
        (_NUMBER, "number"),
    ]


def _sql_rules() -> list[tuple[str, str]]:
    keywords = (
        r"(?i)\b(?:add|all|alter|and|as|asc|between|by|cascade|case|check"
        r"|column|constraint|create|cross|default|delete|desc|distinct"
        r"|drop|else|end|exists|foreign|from|full|group|having|in|index"
        r"|inner|insert|intersect|into|is|join|key|left|like|limit|match"
        r"|natural|not|null|offset|on|or|order|outer|primary|references"
        r"|right|select|set|table|then|union|unique|update|using|values"
        r"|view|when|where|with)\b"
    )
    builtins = (
        r"(?i)\b(?:avg|bigint|blob|boolean|char|count|date|datetime|decimal"
        r"|double|float|int|integer|json|max|min|numeric|serial|smallint"
        r"|sum|text|time|timestamp|tinyint|uuid|varchar)\b"
    )
    return [
        (r"--[^\n]*", "comment"),
        (r"/\*.*?\*/", "comment"),
        (r"'(?:[^'\n]|'')*'", "string"),
        (r'"[^"\n]*"', "string"),
        (_NUMBER, "number"),
        (keywords, "keyword"),
        (builtins, "builtin"),
    ]


#: The built-in language table: normalized tag -> ordered
#: ``(pattern, token-name)`` rules.  Aliases are ordinary keys; a rule's
#: second element is a token name (see the module docstring) or an explicit
#: :class:`Style` when the caller passes their own table to
#: :class:`RegexHighlighter`.
_BUILTIN_LANGUAGES: dict[str, list[tuple[str, str]]] = {
    "python": _py_rules(),
    "py": _py_rules(),
    "javascript": _js_rules(),
    "js": _js_rules(),
    "typescript": _ts_rules(),
    "ts": _ts_rules(),
    "bash": _bash_rules(),
    "shell": _bash_rules(),
    "sh": _bash_rules(),
    "json": _json_rules(),
    "yaml": _yaml_rules(),
    "yml": _yaml_rules(),
    "toml": _toml_rules(),
    "markdown": _md_rules(),
    "md": _md_rules(),
    "diff": _diff_rules(),
    "rust": _rust_rules(),
    "rs": _rust_rules(),
    "go": _go_rules(),
    "golang": _go_rules(),
    "c": _c_rules(),
    "h": _c_rules(),
    "cpp": _cpp_rules(),
    "c++": _cpp_rules(),
    "cc": _cpp_rules(),
    "cxx": _cpp_rules(),
    "hpp": _cpp_rules(),
    "html": _html_rules(),
    "htm": _html_rules(),
    "xml": _html_rules(),
    "css": _css_rules(),
    "sql": _sql_rules(),
}


def _normalize_lang(lang: str) -> str:
    """Normalize a language tag: ``"  Py "`` -> ``"py"``.

    Info strings sometimes carry attributes (`` ```python title=x ``), so
    only the first whitespace-delimited word is used.
    """
    tag = lang.strip().lower()
    if not tag:
        return ""
    return tag.split()[0]


def _token_styles(theme: Theme) -> dict[str, Style]:
    """Token name -> style, every value derived from ``theme`` colors."""
    return {
        "comment": theme.muted.merge(Style(italic=True)),
        "string": theme.success,
        "number": theme.warning,
        "keyword": Style(fg=theme.accent.fg),  # accent's hue, weight-neutral
        "builtin": theme.code,
    }


def _resolve_style(key: str | Style, styles: dict[str, Style]) -> Style:
    """A rule's token name -> style; an explicit ``Style`` passes through."""
    if isinstance(key, Style):
        return key
    try:
        return styles[key]
    except KeyError:
        raise ValueError(
            f"unknown syntax token {key!r}: expected one of "
            f"{sorted(styles)} or a Style"
        ) from None


def _highlight_line(
    text: str, rules: Sequence[tuple[re.Pattern[str], Style]], plain: Style
) -> Line:
    """Highlight one line: scan left to right, first matching rule wins.

    Rules are tried in order at each position; a match advances the cursor to
    its end, text between matches accumulates in ``plain``.  A zero-width
    match is declined so the scan always advances (same guard the inline
    markdown engine uses).  Adjacent runs sharing a style -- a builtin that
    colors exactly like the plain code text, say -- are coalesced by
    :func:`~mocode_tui.core.lines.fuse` before the row is built.
    """
    runs: list[Segment] = []
    plain_from = 0
    pos = 0
    n = len(text)
    while pos < n:
        for pattern, style in rules:
            matched = pattern.match(text, pos)
            if matched is None:
                continue
            end = matched.end()
            if end <= pos:
                continue
            if pos > plain_from:
                runs.append(Segment(text[plain_from:pos], plain))
            runs.append(Segment(matched.group(0), style))
            pos = end
            plain_from = pos
            break
        else:
            pos += 1
    if plain_from < n:
        runs.append(Segment(text[plain_from:], plain))
    return Line(fuse(runs))


# --- highlighter ---------------------------------------------------------------


class RegexHighlighter:
    """The built-in highlighter: ordered regex rules per language.

    ``theme`` supplies every token color (see the module docstring);
    ``languages`` extends or overrides the built-in table
    (``languages={"python": my_rules}`` replaces Python's rules,
    ``languages={"ruby": ...}`` adds a language).  Each rule is a
    ``(pattern, key)`` pair where ``key`` is a token name or an explicit
    :class:`~mocode_tui.core.style.Style` (which overrides theme colors).

    Patterns are compiled once, here; :meth:`highlight` is pure computation
    with no IO, so build one instance and share it across components.
    """

    def __init__(
        self,
        *,
        theme: Theme | None = None,
        languages: dict[str, list[tuple[str, str | Style]]] | None = None,
    ) -> None:
        self._theme = theme if theme is not None else DEFAULT_THEME
        self._plain = self._theme.code
        styles = _token_styles(self._theme)
        table = dict(_BUILTIN_LANGUAGES)
        if languages:
            table.update(
                {_normalize_lang(name): rules for name, rules in languages.items()}
            )
        self._languages: dict[str, list[tuple[re.Pattern[str], Style]]] = {
            name: [
                (re.compile(pattern), _resolve_style(key, styles)) for pattern, key in rules
            ]
            for name, rules in table.items()
        }

    def highlight(self, code: str, lang: str) -> list[Line]:
        """One :class:`Line` per logical line of ``code``.

        An unknown (or empty) ``lang`` renders every line in the theme's
        ``code`` style, monochrome.
        """
        rules = self._languages.get(_normalize_lang(lang))
        if rules is None:
            return [Line.from_text(raw, self._plain) for raw in code.split("\n")]
        return [
            _highlight_line(raw, rules, self._plain)
            for raw in code.split("\n")
        ]


_DEFAULT: RegexHighlighter | None = None


def default_highlighter() -> RegexHighlighter:
    """The shared default highlighter (``DEFAULT_THEME`` colors).

    Built once on first call and reused afterwards: constructing a
    highlighter compiles every built-in rule, so components that need the
    stock engine should share this instance instead of rebuilding it.
    """
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = RegexHighlighter()
    return _DEFAULT


def highlight(
    code: str,
    lang: str,
    *,
    highlighter: Highlighter | None = None,
    theme: Theme | None = None,
) -> list[Line]:
    """Highlight ``code`` as ``lang``; convenience entry point.

    ``highlighter`` wins when given (``theme`` is then ignored), otherwise a
    :class:`RegexHighlighter` runs -- the shared default for ``theme=None``,
    a fresh one for an explicit theme.
    """
    if highlighter is not None:
        return highlighter.highlight(code, lang)
    if theme is None:
        return default_highlighter().highlight(code, lang)
    return RegexHighlighter(theme=theme).highlight(code, lang)

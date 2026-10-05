# Spec W3 · 内置轻量语法高亮 + Markdown 接入(波次 W3)

> 分支 `lib-w3-syntax`;前置:W1 已合并;深读:总纲、`src/mocode_tui/widgets/markdown.py`(FenceRule 现状)、`src/mocode_tui/core/style.py`、`src/mocode_tui/core/lines.py`(Segment/Line)。

## 目标

为代码围栏块提供零新依赖的正则语法高亮,协议可注入替换。**只动 `widgets/syntax.py`(新)、`widgets/markdown.py` 及对应测试。**

## 工单(按序执行,每项一个 commit)

### T1 `widgets/syntax.py`

```python
class Highlighter(Protocol):
    def highlight(self, code: str, lang: str) -> list[Line]: ...   # 每逻辑行一条 Line

class RegexHighlighter:
    def __init__(self, *, theme=None, languages: dict[str, list[tuple[str, Style-or-token]]] | None = None): ...

def highlight(code: str, lang: str, *, highlighter=None, theme=None) -> list[Line]:  # 便捷入口
```

- 内置语言表(至少):`python`、`javascript`/`js`、`typescript`/`ts`、`bash`/`shell`/`sh`、`json`、`yaml`/`yml`、`toml`、`markdown`/`md`、`diff`、`rust`、`go`、`c`/`cpp`、`html`/`xml`、`css`、`sql`。语言名归一化(大小写、别名)。
- 每语言一组**有序**正则规则,五类 token:comment / string / number / keyword / builtin(常量、类型名)。正则按序匹配、先中先得;每行独立匹配(不跨行状态,块注释按行内近似处理即可——简洁优先,注释里写明限制)。
- token 颜色走 Theme:Theme 若无对应字段则在 syntax.py 定义私有默认(从 DEFAULT_THEME 派生:keyword=accent、string=success、comment=muted+italic、number=warning、builtin=code 色系;实现者可微调,但须全部出自 Theme 语义色的 merge/replace,不引入新魔法色)。
- 未知/空语言 → 整行 `theme.code` 单色(现状语义)。
- 性能:规则编译在构造期一次完成;`highlight` 无 IO。
- `tests/test_widgets_syntax.py`:每语言至少一条代表性断言行(关键字/字符串/注释着色)、未知语言回退、空代码、宽字符行不错位、自定义 languages 注入生效。

### T2 Markdown FenceRule 接入

- `FenceRule` 保留并解析语言标签(```python 的 `python`),渲染时调用高亮;未知名/无标签维持现状单色。
- `Markdown(*, ..., highlighter: Highlighter | None = None)`:None 用内置默认;注入的 highlighter 直达 FenceRule(经 `with_inline_rules` 同类机制或构造期绑定,按现有引擎结构选干净做法)。
- 围栏块视觉容器(色带、边距)保持现状;只改变代码行的着色来源。
- markdown 现有测试保持绿(语言标签此前被丢弃,若有断言丢弃行为的测试,更新为新语义并注明)。
- 新增 `tests/test_widgets_markdown_highlight.py`:围栏内 python/bash/json 着色断言、无标签回退、自定义 highlighter 注入生效、流式半开围栏不炸。

## 验收

1. `uv run pytest -q` 全绿(贴真实输出)。
2. `uv run python examples/pi_demo.py < /dev/null` exit 0(demo 未改;其围栏块带语言标签的输出行颜色会变——这是本波**有意行为变化**,在报告中贴 diff 摘要并说明)。
3. `uv run python -c "from mocode_tui.widgets.syntax import RegexHighlighter, highlight"` 正常。

## 禁触清单

`src/mocode_tui/__init__.py`、`core/`、`keys/`、`widgets/` 其他文件、`tests/test_api_root.py`、`examples/`、`docs/`、`README.md`、`pyproject.toml`(零新依赖是红线)。

## 最终报告格式

工单状态表 / commit 清单 / 门禁真实输出 / 内置语言与 token 类别表 / demo diff 的有意变化说明 / 偏差与取舍 / 未决问题。

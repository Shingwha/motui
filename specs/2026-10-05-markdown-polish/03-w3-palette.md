# Spec markdown-polish · 配色 + 文档 + 基线重采（波次 W3）

> 分支 `md-w3-palette`（从 W2 合并后的最新 main 创建）；前置：W2 已合并；
> 深读：`specs/2026-10-05-markdown-polish/00-overview.md`（决策 9/10 配色全表）、
> `src/mocode_tui/core/theme.py`、`src/mocode_tui/core/style.py:160-176`、
> `tests/test_theme.py:66-88`、`README.md:152-179`、`docs/COMPONENTS.md:26-69,133-149`。

## 目标

落实"正常用色、bold 只跟 `**…**` 语法、各元素配色互相隔开"的默认主题：标题金色阶梯、
链接蓝下划线不加粗且只显示 label、行内代码粉、列表标记紫、引用斜体、表头/首列去 bold；
同步文档并重采 demo 基线。**最高约束：Theme 解析顺序（explicit > theme > DEFAULT_THEME）与
`dataclasses.replace` 自定义路径不动；色值可一键替换。**

## 工单（按序执行，每项一个 commit，每个 commit 独立过门禁）

### T1 `core/style.py` + `core/theme.py`：新 token 与阶梯

- `style.py` 按现有常量模式（160-176 一带）新增并导出：
  `HEADING = Style(fg="#e3b341")`、`LINK = Style(fg="#58a6ff", underline=True)`、
  `INLINE_CODE = Style(fg="#f778ba")`、`LIST_MARKER = Style(fg="#bc8cff")`（`__all__` 同步）。
- `theme.py` 新字段（语义色区块）：`heading = HEADING`、`link = LINK`、`inline_code = INLINE_CODE`、
  `list_marker = LIST_MARKER`；`first_column` 默认改 `NONE`。
- `headings` 派生改由 `heading`/`muted`：`(heading, heading, heading+dim, muted+dim, muted+dim,
  muted+dim+italic)`——全部不加粗、无下划线；模块与类 docstring 中"derived from accent/muted"同步改。
- accent 语义收窄为链接/关键字用色（本波只改派生来源，不改 accent 常量本身）。

### T2 `widgets/table.py` + `widgets/markdown.py`：消费新 token

- `table.py`：`DEFAULT_HEADER_STYLE = NONE`（常量保留，注释与 docstring 去掉 "bold"/"soft-purple"）。
- `markdown.py`：
  - `CodeInlineRule`：`theme.code` → `theme.inline_code`（docstring "in ice blue" 同步）。
  - `LinkInlineRule`：label 用 `theme.link`；**只返回 label 段，删除 muted ` (url)` 段**（docstring 同步）。
  - `ListRule`：标记段 `theme.muted` → `theme.list_marker`（docstring 同步）。
  - `QuoteRule`：正文 base 改 `Style(italic=True)`（bar 仍 `theme.muted`）。
  - `HeadingRule`/阶梯无需改代码（读 theme）。
- fence 高亮与 `syntax.py` 不动（keyword=accent 属代码高亮，bold 政策豁免）。

### T3 测试更新（跑出红再逐个改绿，报告列出每一处）

- `tests/test_theme.py:66-88` 阶梯 pin、157-175 主题驱动 markdown 断言。
- `tests/test_widgets_markdown.py:33-42` 阶梯、`:54` 标记 MUTED→LIST_MARKER、
  `:89` 表头 bold→NONE、`:108-116` 链接（row.text 变 `"a code bold em t"`，无 `" (u)"`，
  label 样式 = `theme.link`）、`:62` 引用正文 italic 与 bar。
- `tests/test_widgets_table.py`：first_column 相关断言改 NONE 基线。
- 其余（highlight/readme_examples 等）跑出来再处理；`replace(DEFAULT_THEME, accent=...)` 路径必须仍绿。

### T4 文档 + 基线重采

- `README.md` 152-179 主题字段表：新增 4 字段、修订 `first_column` 默认、补一句 bold 政策；
  若 README/文档里有 Markdown 渲染示例输出，同步。
- `docs/COMPONENTS.md`：Markdown 引擎契约（133-149 一带）补——块间空行与 `gap`、单元格渲染内联、
  网格横线、`\|` 转义、`divider_max_width`、链接 label-only；主题字段表（26-69）同步新字段。
- `docs/DESIGN.md`：仿照既有 "### Theme: added 2026-10-05 (W1)" 小节补一条本次变更记录。
- 重采基线到本组 `ref/`（与 lead 的 before 同法）：`after-pi-demo.txt`、`after-markdown-demo.txt`、
  `after-toc-w60/100.txt`、`after-text-styles-w60/100.txt`、`after-tables-w60/100.txt`、
  `after-misc-w60/100.txt`。旧组 `ref/` 是历史记录，不动。
- 采集脚本（pipe 到文件即可）：

```python
from pathlib import Path
from mocode_tui.widgets.markdown import Markdown
text = Path("examples/Markdown-Rendering-Test.md").read_text(encoding="utf-8")
lines = text.splitlines()
def section(a, b):
    s = next(i for i, l in enumerate(lines) if l.startswith(a))
    e = next(i for i, l in enumerate(lines) if l.startswith(b))
    return "\n".join(lines[s:e])
blocks = {"toc": "\n".join(lines[:28]), "text-styles": section("## 2.", "## 3."),
          "tables": section("## 9.", "## 10."), "misc": "\n".join(lines[-30:])}
ref = Path("specs/2026-10-05-markdown-polish/ref")
for name, src in blocks.items():
    for w in (60, 100):
        with (ref / f"after-{name}-w{w}.txt").open("w", encoding="utf-8") as f:
            for ln in Markdown(src).render(w):
                f.write(f"[{ln.width:>3}] {ln.text}\n")
```

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` 全绿（用例数只增不减）。
2. 两个 piped demo exit 0。
3. `after-*` vs `before-*` 逐节对比结论写进报告：TOC 链接无 `(#…)` 后缀、标题金色（样式段断言），
   text-styles 表格网格横线 + 单元格内联、misc 分割线宽 ≤ 80。
4. bold 政策自查：`DEFAULT_THEME` 里除 syntax 派生外无 bold（列出 grep 证据）。

## 禁触清单

`chat/**`、`core/` 其余文件（text/lines/lines 之外的）、`examples/**`、`pyproject.toml`、
`specs/**`（`ref/after-*` 除外）、`src/mocode_tui/__init__.py` 及各 facade `__all__`。越界即停、上报 lead。

## 最终报告格式

工单状态表 / commit 清单（hash + message）/ `uv run pytest -q` 真实输出结论 / demo exit code /
after-vs-before 逐节结论 / 偏差与取舍 / 未决问题。阻塞即停，不越界自救。

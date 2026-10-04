# Spec W3 · 组件库（波次 W3）
> ✅ 2026-10-04 已交付合并；终验 585 passed（main）。分支见 git log --merges。
> 分支 `wfs3-components`；前置：**W2 已合并**（从合并时刻最新 main 切出）；深读：`00-overview.md` + `01` + `02`

## 目标

从零建设全部 MVP 组件与 Block 内布局容器，配测试。组件协议即 W1 定型的
`render(width) -> list[Line]`（本波不得改协议本身）。最高约束：组件**只算布局、不碰屏幕**
（不 import screen/painter）；每个 `render` 是给定宽度的纯函数；编辑态方法由驱动（W4）驱动调用。

## 工单（按序，每项一个 commit，每 commit 独立过 `uv run pytest`）

### T1 `components/text.py` — Text / Markdown
- `Text(text="", *, style=NONE)`：`text` 可变属性；`render(width)` = `wrap_text` 逐行成 `Line`，
  每行 `.fit(width)`。多空行保留（split("\n") 语义）。
- `Markdown(text, ...)`：轻量子集——段落、ATX 标题（`#`..`####`）、围栏代码块（```）、列表（`-`/`*`/`1.`）、
  行内 `code`（反引号）、`**bold**`、`*italic*`。未知语法按普通段落。流式期间建议 Text，定稿换 Markdown。
- 测试 `tests/test_components_text.py`：空文本、单行、长词换行宽度、CJK、多段；
  Markdown 各元素至少一例；render 宽度边界（width=1、width=0 不炸）。

### T2 `components/chrome.py` — Notice / Divider / Panel
- `Notice(text, *, level="info")`：info 裸行；warn/error 前缀 `WARNING: `/`ERROR: `（语义样式）；
  未知 level 降级 info（用户面不炸）。
- `Divider(*, char="─", style=BORDER)`：整宽规则行（char 重复 + fit）。
- `Panel(child, *, title="", style=BORDER)`：子组件渲染在 `width-4`（边框+每侧 1 padding），
  行 pad 回内宽；`width<4` 降级为裸子组件 fit；标题嵌顶边框。
- 测试 `tests/test_components_chrome.py`：Notice 各级样式段；Divider 宽度与 CJK char；
  Panel 边框对齐/标题/窄宽降级。

### T3 `components/choice.py` — Select / Confirm / Option
- `Option(label, value=None, hint="")` dataclass。
- `Select(options, *, title="", selected_style=SELECTION, hint_style=DIM, title_style=NONE)`：
  `index`；`selected`；`move(delta)`（夹取、不环绕）；render：可选标题行 + 每选项一行，
  选中行 `❯ ` 前缀 + selected_style（整行一段连续样式带），hint 追加 dim。
- `Confirm(message, *, danger=False)`：两个 Option("Yes",True)/("No",False) 的 Select 特化；
  danger 时标题用 ERROR 样式。
- 测试 `tests/test_components_choice.py`：move 夹取/不环绕；selected 边界；空 options 不炸；
  render 行数与宽度；Confirm 的 Yes/No 与 danger 样式。

### T4 `components/input.py` — Input
- `Input(*, prompt="❯ ", placeholder="", style=NONE, prompt_style=ACCENT, cursor_style=CURSOR, focused=True)`。
- 编辑态：`text`/`cursor`（char index）；`insert(s)`（容纳多行 `\n`）；`newline()`；`backspace()/delete()`
  （边界返 False）；`clear()`；`move_left/right()/home()/end()/move_up()/move_down()`
  （上下为**视觉行**移动，需自算 wrap 几何：wrap 断点规则与 text.py 一致；光标落在被丢弃断点空格上
  时归属前一视觉行末）。
- 渲染：prompt 前缀（仅首视觉行；续行以等宽空格占位）；placeholder（空文本且 focused 时 dim 显示）；
  光标：所在视觉行内该字符 re-style 为 `style.merge(cursor_style)`，或在行尾插一个反色空格
  （行已满则跳过插入，不溢出）。记录 `_last_width` 供视觉行几何；首渲前用 80 兜底。
- 测试 `tests/test_components_input.py`：插入/删除/清空边界；光标左右与 home/end；
  单行/多行 wrap 下的上下移动列保持；placeholder 与空态渲染；prompt 占位宽度；
  行尾满宽不溢出（render 行宽 ≤ width）；粘贴多行文本 render 形状。

### T5 `components/status.py` + `components/spinner.py`
- `StatusBar(*, segments: list[StatusSegment] = ())`：`segment(text, priority)` 添加；
  render(width)：按优先级从高到低保留，直到放不下就丢（低优先级先丢），最后 fit 截断。
- `StatusSegment(text, priority=0)` frozen dataclass。
- `Spinner(text="", *, frames=None, interval=0.1)`：frames 默认 `("⠋","⠙","⠹",...)`；
  `advance()`（帧循环）；`render(width)` = 当前帧 + 空格 + text，fit。
- 测试 `tests/test_components_status.py` / `tests/test_components_spinner.py`：
  优先级丢弃顺序、超宽截断、空栏；帧循环回绕、advance 无 invalidate 依赖、空文本形状。

### T6 `layout.py` — Row / Column + `components/__init__.py` 收口
- `Row(children, *, widths=None, gap=1)`：定宽列（widths[i] 非 None）+ 弹性列均分剩余
  （整除，余量弃用不拉伸）；每列 pad 到列宽保持网格对齐；行数=最高子组件；gap 列间空列。
- `Column(children, *, gap=0)`：纵向顺序拼接，gap 个空行分隔。
- 两者都是普通组件（可嵌套一层）：`from .block import Component` 仅供协议引用，不得 import 驱动/屏幕。
- `components/__init__.py`：导出 Text/Markdown/Notice/Divider/Panel/Option/Select/Confirm/
  Input/StatusBar/StatusSegment/Spinner（Row/Column 在 `layout.py`，由顶层 `__init__.py` 导出——W4 做）。
- 根 `src/mocode_tui/__init__.py` 追加导出 `Row, Column`。
- 测试 `tests/test_layout.py`：Row 定宽/弹性/余量弃用/行数取最高/空 children；
  Column gap；Row 含 Column 一层嵌套；窄宽不炸。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest`：`N passed`，0 失败（贴尾部原文；N ≥ W2 的数 + 本波新增，组件每文件至少一条测试）。
2. `uv run python - <<'PY'`：把所有组件各 render(40) 一次，打印 `.text` 行证明可渲染。贴输出。
3. `git diff --stat main..HEAD` 证明写入范围仅
   `src/mocode_tui/components/**`、`src/mocode_tui/layout.py`、`src/mocode_tui/__init__.py`、
   `tests/test_components_*.py`、`tests/test_layout.py`。

## 禁触清单

- `style.py text.py lines.py ansi.py block.py screen.py viewport.py painter.py keys.py app.py testing.py`、
  `examples/**`、`docs/**`、`README.md`、`pyproject.toml`、`specs/**`。
- 不 merge / 不 push / 不 checkout main / 不碰其他 worktree；不改任何 spec。

## 诚实出口

- Markdown 子集若遇到表格/嵌套引用/HTML：按普通段落文本处理并在 docstring 写明降级规则，
  不写死报错。
- Input 视觉行几何若与 text.py 的 wrap 在极端输入（全空格行、超宽字符）下不一致：以组件内
  自洽为准并在报告登记差异，不修改 W1/W2 代码。

## 最终报告格式

同前波：工单状态表（commit hash+message）/ commit 清单 / 自测真实结论 / 偏差与取舍 / 未决问题。

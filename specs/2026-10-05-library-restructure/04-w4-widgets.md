> ✅ 2026-10-05 @ 分支 lib-w4 — 已合并 main

# Spec W4 · 新通用组件(波次 W4)

> 分支 `lib-w4-widgets`;前置:W1 已合并;深读:总纲、`docs/COMPONENTS.md` 的「Building your own component」一节(ProgressBar 现成参考)、`src/mocode_tui/widgets/choice.py`(Select 现状,Autocomplete 以其为底)、`src/mocode_tui/widgets/layout.py`。

## 目标

补齐通用组件库:Autocomplete、ProgressBar、Tabs、Tree、Spacer、Padding。全部遵循组件协议、Theme 规则(`style=None` + `theme=None`,显式 > theme > DEFAULT_THEME)、纯渲染无副作用。**只新增文件 + 每个组件一个测试文件;不改任何现有文件。**

## 工单(按序执行,每项一个 commit)

### T1 `widgets/autocomplete.py`

- `Autocomplete(*, options=(), max_rows=8, label_style=None, hint_style=None, selected_style=None, theme=None)`;options 为 `Option`(复用 choice.py)。
- `set_query(query: str)`:过滤 options——前缀匹配优先,其次子串包含,保序;结果存内部。
- `move(delta)` 游标(在过滤结果内 clamp);`selected -> Option | None`;`is_empty`。
- `render(width)`:最多 max_rows 行;选中行 `selected_style`;label + 右对齐或尾随的 dim hint(布局与 Select 行一致);空结果渲染零行。
- 纯组件,不读键不挂载;键盘路由归宿主(W6 的 SlashPalette 是它的消费者)。
- `tests/test_widgets_autocomplete.py`:过滤排序、游标 clamp、max_rows 截断、样式注入、空查询行为(空查询=显示全部,裁决写明)。

### T2 `widgets/progress.py`

- `ProgressBar(fraction=0.0, *, label="", width_chars=None, done_style=None, todo_style=None, theme=None)`;fraction clamp [0,1]。
- 渲染 `[███░░░]` 形态(COMPONENTS.md 的示例即蓝本,但收敛为库组件:label 前缀可省,`width_chars` 固定轨道宽,None 则吃满可用宽)。
- 语义色默认:done=SUCCESS 系、todo=DIM 系(走 Theme)。
- `tests/test_widgets_progress.py`:0/0.5/1 三态、clamp、label、窄宽度 `fit` 不溢出。

### T3 `widgets/tabs.py`

- `Tabs(tabs: list[str], *, active=0, active_style=None, inactive_style=None, divider="│", theme=None)`。
- `move(delta)`/`activate(i)`;`active` 属性;渲染单行:` name │ name │ name `,活动项高亮(默认 selection 系),超宽 `fit` 省略。
- `tests/test_widgets_tabs.py`:切换、clamp、渲染行数恒 1、超宽截断。

### T4 `widgets/tree.py`

- `TreeNode(label, children=(), *, expanded=False)`(frozen dataclass 或普通类,选简洁);`Tree(root_nodes, *, indent=2, guide_style=None, label_style=None, cursor_style=None, theme=None)`。
- 维护可见节点扁平化 + 游标:`move(delta)`、`toggle()`(展开/折叠)、`selected -> TreeNode`;有子节点的显示 `▸/▾` 指示,叶子留空位对齐;缩进用空格(guide 从简:不做 │ 连线,裁决写明)。
- `tests/test_widgets_tree.py`:展开折叠改变行数、游标移动、嵌套缩进、toggle 幂等。

### T5 `widgets/layout.py` 增加 Spacer/Padding

- `Spacer(rows=1)`:N 行空白(现 demo 用 `Text("")` 凑,收编为正式件)。
- `Padding(child, *, left=0, right=0, top=0, bottom=0, fill_style=None, theme=None)`:子件四周留白;`fill_style` 非 None 时空白区以该 bg 填充(供色带场景)。
- **只追加**,不动 Row/Column 现有代码。
- `tests/test_widgets_layout_extras.py`:行数、留白位置、fill 行为。

## 验收

1. `uv run pytest -q` 全绿(贴真实输出,列出新增用例数)。
2. `uv run python examples/pi_demo.py < /dev/null | diff - specs/2026-10-05-library-restructure/ref/w1-demo-dump.txt` 为空(零现有行为变化)。
3. 五个新模块逐一 `uv run python -c "from mocode_tui.widgets.<mod> import ..."` 可导入。

## 禁触清单

除上述新文件与对应新测试外的**一切**现有文件(包括 `widgets/__init__.py`、`widgets/choice.py`、`src/mocode_tui/__init__.py`、`tests/test_api_root.py`、`examples/`、`docs/`)。Autocomplete 复用 Option 用 `from .choice import Option`,不改 choice.py。

## 最终报告格式

工单状态表 / commit 清单 / 门禁真实输出 / 每组件公开 API 签名表 / 偏差与取舍 / 未决问题。

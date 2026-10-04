# Spec W5 · pi 风格组件（波次 W5）
> 分支 `wfs5-pi-components`；前置：**W4 已合并**（从合并时刻最新 main 切出）；深读：`00-overview.md` + `03`（组件风格先例）

## 目标

为「pi 式全屏编码助手」界面补四块新组件：`Message`（角色化消息块）、`ToolBlock`（工具调用块）、
`EditBlock`（编辑 diff 块）、`Table`（盒线表格），配测试并收口导出面。
最高约束：仍遵守组件协议 `render(width) -> list[Line]`；只 import 内核（block/lines/style/text）；
每个 render 是给定宽度的纯函数；行宽永不超 width。

## 设计参照（用户给的 pi UI 截图，lead 已定格的行为）

- **Message**：user 消息 = 通栏色带（左右各 1 cell 内边距，bg 蓝）；assistant = 无底普通段落；
  thinking = 斜体暗灰（截图中的 "The user greets…" 段）。
- **ToolBlock**：bash/工具调用 = 通栏色带（bg 绿系），首行标题（如 `$ echo …`）、空行、输出行、空行、
  尾行 `Took 0.1s`（暗斜体）；code 色调用暗底（bg 黑系）。
- **EditBlock**：路径行（亮色）、上下文行（朴素）、`-{n} 旧行`（红）、`+{n} 新行`（绿，末行带
  `(edited)` 徽标）；中性暗底色带。
- **Table**：盒线表格（`│` 分隔），表头行 + 分隔线；自然列宽，超宽按比例收缩并 ellipsize；
  单元格支持 (text, Style)。

## 工单（按序，每项一个 commit，每 commit 独立过 `uv run pytest`）

### T1 `components/message.py` — Message
- `Message(role, text, *, style=None)`：role ∈ `"user"` / `"assistant"` / `"thinking"`。
  - user：每行 = `" "` + 内容 + 补齐，全部段带 `USER_BG`（`Style(bg="blue")`，可被 `style` 覆盖）；
    文本区宽 = width-2，wrap_text + fit。
  - assistant：朴素行（wrap_text + fit），无底色、无缩进。
  - thinking：斜体暗灰（`MUTED.merge(Style(italic=True))`，可被 style 覆盖）。
  - 空 text：user 出一个空色带行；其余出一个空行。未知 role → 当 assistant（不抛）。
- 语义常量放 `style.py`？**不行——style.py 是 W1 禁触层**。新语义常量定义在
  `components/message.py` 模块级（`USER_BG` 等），命名注释说明由来。
- 测试 `tests/test_components_message.py`：三角色行形状；wrap 与 CJK；width=1/0 不炸；
  style 覆盖；空文本；render 行宽 ≤ width（含宽字符）。

### T2 `components/tools.py` — ToolBlock / EditBlock
- `ToolBlock(title, body=(), *, tone="tool", footer="")`：
  - tone → 底色：`"tool"`=绿系（`TOOL_BG = Style(bg="green")`）、`"code"`=暗系（`CODE_BG = Style(bg="black")`）、
    `"plain"`=无底色；未知 tone → plain（不抛）。
  - 行结构：标题行（`Style(bold=True)`）、空行、body 各行、空行、footer 行（暗斜体）；
    body 空或 footer 空时省掉对应空行。所有行 1 cell 左内边距 + 通栏底色补齐。
  - body 元素为 str（按原文一行），调用方自理换行。
- `EditBlock(path, context=(), removed=(), added=())`：
  - 行号从 1 起跨 context/removed/added 连续编号；
  - 前缀：context `"{n} "`、removed `"-{n} "`（ERROR）、added `"+{n} "`（SUCCESS）；
  - 末个 added 行尾追加 `" (edited)"`（SUCCESS bold）；路径行 `path`（ACCENT bold）；
  - 中性暗底色带（`CODE_BG`），1 cell 左内边距。
- 测试 `tests/test_components_tools.py`：三 tone 的底色段与结构（空 body/footer 省空行）；
  行号连续性；badge 只在末 added 行；超宽 fit；空 removed/added；行宽 ≤ width。

### T3 `components/table.py` — Table
- `Table(headers, rows, *, header_style=None, first_column_style=None)`：
  - rows 单元格为 str 或 `(str, Style)` 元组；header_style 默认 `Style(bold=True)`；
    first_column_style 默认 `Style(fg="magenta", bold=True)`（只作用于数据行首列，不影响表头）。
  - 盒线：`│ cell │ cell │`；表头下分隔线 `├───┼───┤` 形状（按列宽）。
  - 列宽 = 该列自然最大宽 + 2（左右各 1 padding）；总宽（含分隔符）> width 时按比例 Floor 收缩
    （每列至少 1），单元格 ellipsize 到列预算；总宽 < width 时右边界不拉伸（左对齐即可）。
- 测试 `tests/test_components_table.py`：自然列宽形状；超宽收缩+ellipsize（确定性：给定 width 断言精确字符串）；
  样式单元格；空 rows（只表头）；单列；CJK 列宽；行宽 ≤ width。

### T4 导出面收口 + 同步 W4 钉测
- `components/__init__.py` 导出 Message/ToolBlock/EditBlock/Table；根 `__init__.py` 同步追加这 4 个。
- `tests/test_app.py` 的导出面 pin 测：**只允许**把 `contract` 集合加入
  `"Message", "ToolBlock", "EditBlock", "Table"` 四个名字；该文件其余部分零改动。
- 全量 `uv run pytest` 绿（贴尾部输出）。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest` → `N passed`（N ≥ 399），0 失败（贴尾部原文）。
2. `uv run python -c "import mocode_tui as m; print(len(m.__all__)); assert {'Message','ToolBlock','EditBlock','Table'} <= set(m.__all__)"` 贴输出。
3. `git diff --stat main..HEAD`：写入范围仅 `src/mocode_tui/components/{message,tools,table,__init__}.py`、
   根 `src/mocode_tui/__init__.py`、`tests/test_components_{message,tools,table}.py`、`tests/test_app.py`（仅 contract 集）。

## 禁触清单

- `style.py text.py lines.py ansi.py block.py screen.py viewport.py painter.py keys.py app.py testing.py layout.py`、
  `components/{text,chrome,choice,input,status,spinner}.py`、`examples/**`、`docs/**`、`README.md`、
  `pyproject.toml`、`specs/**`；`tests/test_app.py` 除上述 contract 单点外一切改动。
- 不 merge / 不 push / 不 checkout main / 不碰其他 worktree；不改任何 spec。

## 诚实出口

- 16 色调色板拍不出截图的「暗绿/暗蓝」精确色：以最近命名色（bg="green"/bg="blue"/bg="black"）实现，
  在报告登记色差；**不得**引入 256 色/真彩色（总纲写死）。
- Table 超宽收缩若出现「某列预算 < 1」的极端：该列预算夹取 1，单元格 ellipsize 掉；如实登记。

## 最终报告格式

同前波：工单状态表（T1..T4：commit hash + message + 结论）/ commit 清单 / 自测真实结论 / 偏差与取舍 / 未决问题。

# W2c 交接包（data and content）

> 分支 `motui-2/w2c` / 起点 `eb9e835`（W1 合并 + W2 工单）/ 2026-10-21
> 源码 commit `f4b4386`；本文件为最后一个 commit。

## A. 自动事实

### 门禁真实输出

```text
uv run pytest -q -p no:cacheprovider
896 passed in 10.17s

uv run python tools/golden.py --check
golden: 58 topics match

uv run python tools/framebench.py
render-hash  : f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1

uv run python -m motui < /dev/null
exit 0，输出 70 行

uv run python -m motui --pages > /tmp/pages.txt
exit 0，4130 行
```

render-hash 与 W1 基线 `f872187a…d6e1` 逐字符相同；58 个 golden topic 未变；
demo 两条命令的退出码与行数与 W1 基线一致。

### Commit 清单

| commit | 内容 |
|---|---|
| `f4b4386` | `widgets: read the 2.0 role groups in the data and content family` |
| 本文件所在 commit | `specs: hand off the W2c data migration` |

### 变更范围 / 禁触审计

`git diff --name-only eb9e835..HEAD`（源码 commit）只有 9 个文件：

```text
src/motui/widgets/table.py
src/motui/widgets/decor.py
src/motui/widgets/diff.py
src/motui/widgets/indicators.py
src/motui/widgets/syntax.py
src/motui/widgets/markdown/blocks.py
src/motui/widgets/markdown/nested.py
src/motui/widgets/markdown/inline.py
src/motui/widgets/markdown/component.py
```

- `widgets/markdown/context.py` 在写入范围内但**没有任何 theme token 读取**
  （只把已解析的 `theme` 放进 `RenderContext` 透传），零 diff。
- `tests/` 零 diff：W1 的机械迁移已把这些测试的 Theme 构造改到 group 形式，
  W2c 的读取迁移不需要再动任何构造；所有断言逐字未改。
- 零 diff：`kernel/`、`interaction/`、`app.py`、`keys/`、其他 widget 文件
  （含 `widgets/bands.py`）、`tests/golden/`、`tools/`、`docs/`、`pyproject.toml`、
  `uv.lock`。未运行 `golden --update`，未 merge/push/tag。

## B. 只有存在于脑子里的东西

### 旧字段 -> group 的精确映射（本波落地值）

| 组件 | 旧读取 | 新读取 |
|---|---|---|
| `Table` header | 常量 `NONE` | `text.base`（legacy `NONE`） |
| `Table` first column | `first_column` | `text.base` |
| `Table` grid | `table_border` | `borders.grid` |
| `Table` disabled cell text | `dim` | `text.faint` |
| `Table` 行带 | `RowBands.from_theme`（兼容属性） | `rows.band(...)`，见下 |
| `Divider` 线 | `border` | `borders.base` |
| `Panel` 边框（`frame=True`） | `border` | `borders.base` |
| `Diff` 删除 | `error` | `status.danger`（仍去 `bold`） |
| `Diff` 插入 | `success` | `status.success` |
| `Diff` hunk / gutter | `muted` | `text.muted` |
| `ProgressBar` filled | `success` | `status.success` |
| `ProgressBar` empty | `dim` | `text.faint` |
| `Slider` filled | `accent` | `content.accent` |
| `Slider` empty / disabled | `dim` | `text.faint` |
| `Slider` hover | `hover` | `surfaces.hover` |
| `Slider` focus | `focus` | `controls.focus` |
| `Spinner` | `accent` | `content.accent` |
| `Syntax` comment | `muted + italic` | `text.muted + italic` |
| `Syntax` string / number | `success` / `warning` | `status.success` / `status.warning` |
| `Syntax` keyword | `accent.fg` | `content.accent.fg` |
| `Syntax` builtin / plain | `code` | `content.code` |
| `Markdown` headings | `headings` | `content.headings` |
| `Markdown` link | `link` | `content.link` |
| `Markdown` inline code | `inline_code` | `content.inline_code` |
| `Markdown` list/task marker | `list_marker` | `content.marker` |
| `Markdown` quote bar | `muted` | `text.muted` |
| `Markdown` quote body italic | `Style(italic=True)` | `content.emphasis` |
| `Markdown` bold/italic/strike | 常量 `Style(...)` | `content.strong/emphasis/strike` |
| `Markdown` fence 行 | `muted` | `text.muted` |
| `Markdown` hover | `hover` | `surfaces.hover` |

实现形式统一为 `self.pick(explicit, <token>)`；没有显式参数的读取（Diff 三条带、
Markdown 的规则与 hover）直接取 group 字段。

### Table 行带：为什么不是一条纯 `rows.band()` 调用

默认路径确实走 `theme.rows.band(active=..., hovered=..., focused=..., disabled=...)`：

- 焦点游标行 -> `rows.active`，非焦点游标行 -> `rows.inactive`
  （legacy 值 `DIM`，逐字节复现旧 `active.merge(dim)`）；
- 悬停行 -> `rows.hover`，disabled 行 -> `rows.disabled`，其余 -> `rows.base`；
- header 与网格线是 chrome，仍走 seed 的 `ground`（`surfaces.base`）。

两个桥接点必须知道：

1. **hover 兼容别名。** legacy 下 `rows.hover == NONE`，而 1.x 的
   `theme.hover` 映射到 `surfaces.hover`。默认路径在 `rows.hover is NONE`
   时把 `surfaces.hover` 当作 hover token（构造期解析成 `_row_styles`）。
   若不这样做，`tests/widgets/test_action.py::test_hover_at_marks_and_clears_one_row_across_components`
   的 Table 分支会失败：该测试（W2a 的写入范围，W2c 不能改）只设置
   `surfaces.hover` 并断言 Table 的悬停行带上它。W3 切到暗色默认值后
   `rows.hover` 非 `NONE`，这条别名自然失效；W4 可随兼容层一起删。
2. **显式 bands 的旧路径。** `bands=` 参数、`ground_style`/`active_style`/
   `disabled_style` 覆盖，或宿主构造后给 `.bands` 重新赋值时，仍走
   `RowBands` 的 `resolve_band`（并保留“非焦点 active 合并 dim、有背景则跳过”
   的旧语义）。判断用 `self.bands is self._band_seed`：seed 未被替换 = 主题路径。
   `bands` 仍留在构造签名与 `revision()` 里，签名零变化。

`RowBands` 的 seed 直接由 group 构造（不再调用 `from_theme` 的兼容属性）：
`ground=surfaces.base`、`active=rows.active`、`hover` 用上面的别名、
`dim=text.faint`（旧 `theme.dim`）、`disabled=text.faint`（旧 `theme.dim`）。
legacy 下逐字段等于 `RowBands.from_theme(DEFAULT_THEME)`。

### 与工单的一处偏差（有意）

工单 2 写“Divider label 用 `text.muted`（旧 `theme.muted`）”，但 1.x 的
`Divider.label_style` 默认**一直是 `NONE`**（`git show ac281ad:.../decor.py`
可核对；只有显式传入才着色）。把默认值改成 `text.muted` 会给
`Divider(label=...)` 的 label 上色（demo 的 `components_layout` 有带 label 的
divider），直接改变 golden/`--pages` 字节，违反零视觉变化。因此本波保持
`label_style is None -> NONE`，没有新增 theme 读取；若 W3 想让 label 走
`text.muted`，应作为视觉切换显式记录并重录 golden。

### Syntax 的 token 来源

工单第 5 条要求按旧字段映射（`text.muted` / `content.accent.fg` /
`status.success` / `status.warning` / `content.code`），本波照此落地，**没有**
改成读 `theme.syntax.*`。原因：`tests/widgets/test_syntax.py` 的
`test_token_colors_follow_the_injected_theme` 通过覆盖 `status.warning` 来断言
number token 变色；若读 `syntax.number` 会忽略该覆盖。legacy 下本波映射后的五类
值与 `SyntaxStyles` 的字段默认值逐字节相等；W3 切默认主题时再决定是否把
`SyntaxStyles` 接进来（两者在暗色 palette 下同源）。

### 测试

- `tests/` 零改动；无需机械迁移（W1 已完成 group 构造）。
- Markdown task 仍用 `TASK_OPEN`/`TASK_DONE` 与 `pair_seat`，未引入 `glyphs=`。

### 未迁移、但相关的东西

- `widgets/bands.py::RowBands.from_theme` 仍读兼容属性；Table 本波已不再调用它，
  但 List/Tree/NavList 等仍会（W2b/W4 的写入范围）。
- 源文件 docstring 的旧角色词已随本次读取改成 group 路径；`Decor` 的
  `label_style` 文档保持原样（语义未变）。

## C. 指针

- 工单：`specs/2026-10-21-0856-motui-2-0/02-W2c-data.md`
- 接口：`specs/2026-10-21-0856-motui-2-0/ref/interfaces.md` §3.1/§3.3/§3.4/§5
- 源：`src/motui/widgets/{table,decor,diff,indicators,syntax}.py`、
  `src/motui/widgets/markdown/{blocks,nested,inline,component}.py`
- 基线：起点 `eb9e835`；源码 commit `f4b4386`；render-hash
  `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`

## 未决问题

1. **Divider label 的 `text.muted`**：工单描述与 1.x 实现不符；本波按零视觉
   约束保持 `NONE`。W3 若切换，需要重录 golden 并记录变化类别。
2. **`bands.py` 归属**：`RowBands.from_theme` 的兼容属性读取仍无 W2 工单覆盖
   （W2a 交接包已提出同一问题）。W4 删除兼容属性前必须迁移或删除它。
3. **Table hover 别名**：`rows.hover is NONE -> surfaces.hover` 是 W2 桥；
   W3 默认值切换后 `rows.hover` 生效，W4 删除兼容层时应一并删掉这条回退。

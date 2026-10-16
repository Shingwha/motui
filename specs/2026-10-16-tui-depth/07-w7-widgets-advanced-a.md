# Spec tui-depth · W7 组件进阶 A（波次 W7）
> 分支 `td7-widgets-a`；前置：W6；深读：`00-overview.md`（D17）。
> **最高约束：`Diff` 与 `List` 都是纯「状态 + render」组件（数据在构造时给全，窗口化只影响渲染）；
> grapheme 边角是 `core/text.py` 的纯函数收口，不许改既有宽度契约的既有用例。**

## 目标

1. `Diff(before, after)`：行级统一 diff 视图（纯展示、可滚动、无交互状态）。
2. `List(items, *, window=…)`：窗口化大列表（只渲染可见行；cursor/chosen/hover_at/前缀跳转）。
3. grapheme 边角：组合附标/变体选择符/ZWJ 零宽、RI 对成旗（`core/text.py`）。
4. gallery 新增 `diff` 页（第 14 页）；`List` 进 `/data` 页；文档与 pin 同步。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| 宽度与折行的唯一来源 | `core/text.py:156-188,306-460` |
| 组件惯例（`Themed`、`chosen`、`hover_at`） | `widgets/choice.py`、`widgets/table.py` |
| `Table` 的窗口/光标/hover 先例（可借其骨架） | `widgets/table.py` |
| gallery 页注册一行一处 | `examples/gallery/registry.py:55-80` |
| 黄金帧（W5 起）在页数变化时必须重录 | `tools/golden.py`、`tests/golden/pages/` |
| 既有宽度测试（不可回归） | `tests/test_core_text.py`（含宽字符/emoji 组） |

## 工单（按序执行，每项一个 commit）

### T1 `widgets/diff.py`：`Diff`

- `Diff(before: str, after: str, *, context=3, theme=None)`：构造时算一次行级 LCS → hunks
  （`context` 行上下文，hunk 之间用 `…` 行）；`render(width)` 输出统一 diff 行：
  `-` 前缀 + `theme.error` 底纹（dim 化）、`+` 前缀 + `theme.success`、` ` 前缀 + 默认、
  `@@` 头 + `theme.muted`；行 `fit(width)`。
- 纯展示：不实现交互协议（无 chosen/cursor）；大文件（2000 行）构造函数内有上限（如 20k 行对，
  超限退化为「整段替换」两 hunk，docstring 写明）。
- 测试：增/删/改/不动四种行的字节；hunk 合并与 `context=0`；空 before/after；上限退化路径。

### T2 `widgets/list.py`：`List`

- `List(items, *, window=8, theme=None, focused=False, prefix_jump=True)`（`items: list[str]`）；
  字段：`index`（光标，可见窗口跟随）、`hover`、`focused`、`chosen: str | None`（`activate()`/`click`
  置当前项，读一次）；能力：`Hoverable + Focusable + Clickable + Activable`，`hover_at` 行级高亮。
- **窗口化渲染**：`render(width)` 只输出 `window` 行（± 半窗滚动），行首带 `▸` 光标标记；
  顶部/底部越界时输出 `↑/↓ N more` 之类的计数行（不新增组件）。
- 前缀跳转：键入单个可打印字符 → 跳到第一个以该字符（大小写不敏感）开头的项，光标更新；
  `move(delta)` 上下；`home/end` 首尾（`handle` 消费这些键）。
- 测试：1000 项只渲染 window 行；光标跟随与计数行；前缀跳转；chosen/hover 三态与归零字节。

### T3 `core/text.py`：grapheme 边角（D17）

- `visible_width` / `wrap_text` 的簇规则补齐（同层纯函数）：
  - 组合附标（Mn/Me 区块——用紧凑常量表）与变体选择符（FE00-FE0F、E0100-E01EF）零宽（并入前簇）；
  - ZWJ（200D）零宽、其后字符并入前簇（宽度取前簇）；
  - Regional Indicator 对（1F1E6-1F1FF 连续两个）宽度 = 2（旗），单个 = 2 的既有行为保留，
    成对时第二枚记 0（总宽 2）。
- 每类 3+ 用例（含既有与新增的对照），并**不许**改动既有测试的期望值（若不兼容，停下上报）。
- docstring 写明「不做完整 UAX #29；以上四类之外按 wcwidth」。

### T4 gallery + 文档 + pin

- `registry.py` 加 `diff` 页（第 14 页）：静态两版本文本 + `Diff` 展示 + `api_note`；`script.py`
  的 `/page` 列表补 `diff`；`devtools` 页的黄金帧说明同步。
- `/data` 页加 `List`（与 Table/Slider 同页，`section` 分隔）；回放覆盖。
- `tools/golden.py --update` 重录（14 页，写明「新页」）。
- `docs/COMPONENTS.md` 组件表 + 两个 ## 小节；`README.md` 组件表；`docs/DESIGN.md` 命名表
  （`Diff`/`List`）；`test_api_root.py`（root 计数与顺序）。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` 只增不减（贴 before/after 与新增文件）。
2. 探针：Diff 四型行与 `context=0` 字节；List 1000 项的渲染行数与计数行；grapheme 四类宽度对照表
   （码点序列 → 宽度，改前/改后）。
3. `demo.py < /dev/null` exit 0；`--pages` → **14** 页头且新页有内容；`golden --check` 全过。
4. framebench hash 如实（工作负载不含新组件 → 预期不变）。
5. import 干净；README 块全绿。

## 禁触清单

- 既有宽度契约的既有用例（grapheme 只加法；不兼容即停下上报）
- `Table`/`Tree`/`Markdown`（W8 的活）；`Search`/`Tooltip`/`Stats`；`specs/**`

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论 / Diff 与 List 探针 / grapheme 对照表 / golden 重录说明 /
framebench hash / 偏差与取舍 / 未决问题 / 真机手测：未执行。

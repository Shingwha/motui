# Spec tui-depth · W2 行内动作（波次 W2）
> 分支 `td2-inline`；前置：W1；深读：`00-overview.md`（D4、D6、宪法 3/4、现状锚点表）。
> **最高约束：`Segment` 只长两个载荷位（`link` 参与相等性、`action` 不参与）；命中一律读
> 「上次 render 的行表」；`Markdown` 的 `(text,width)` 缓存键不变，hover 以后变换实现；无回调。**

## 目标

1. `Segment.link`（OSC 8 载体）与 `Segment.action`（应用内动作）。
2. `Line.styled()` 在 link 段外包 OSC 8；`lines.action_at(line, col)` 纯函数。
3. `Text` 与 `Markdown` 成为 `Clickable + Hoverable(+hover_at)`，`chosen` 读一次。
4. Markdown 链接同时得 `link=url, action=url`；gallery 有可点回声；文档同步。
5. render-hash 本波第二次有意重录（fixture 有 20 处链接，OSC 8 改字节）。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| `Segment` frozen（`text`/`style` + 派生 `_width`）；`Line` 不可变、`styled()` 每实例缓存 | `core/lines.py:63-96,140-165` |
| `Text.render` 每次重算（wrap + fit），无缓存 | `core/lines.py:258-293` |
| `Markdown.render` 单一入口、`(text,width)` 键控的 `_StreamCache`；行表总是副本 | `widgets/markdown/component.py:95-105,239-249` |
| 链接 URL 被丢弃、测试锁死 | `widgets/markdown/inline.py:162-176`；`tests/test_widgets_markdown.py:168,206` |
| 协议面：`Clickable`/`Hoverable`/`hover_at` 契约 | `core/block.py:47-121`；`docs/COMPONENTS.md:44-70` |
| Pointer 调 hover/hover_at 与 click 的路径 | `pointer.py:196-249`；`focus.py:203-227` |
| 行 diff 靠 `previous != row`（相等性语义要紧） | `core/painter.py:99-101` |
| gallery 的 `chosen` 读一次在 `_read_picks`；toast/echo 惯例 | `examples/gallery/session.py:351-383` |

## 工单（按序执行，每项一个 commit）

### T1 `core/lines.py`：`Segment.link` / `Segment.action` + OSC 8

- `Segment` 加两个字段：`link: str | None = None`（**参与**相等性——链接变要重画）、
  `action: str | None = None`（`compare=False`，纯元数据）。既有构造形态不变（默认 None）。
- `Line.styled()`：遍历段时，段的 `link` 非空 → 该段文本外包 `OSC 8` 开/关
  （`"\x1b]8;;{url}\x1b\\"` … `"\x1b]8;;\x1b\\"`；选择 ST 终止，避免与 BEL 混用）；
  其余拼接与 RESET 规则**逐字节不变**（无 link 的行输出与改前完全一致）。
- 字节只从 ansi.py 构造：新增 `ansi.hyperlink_open(url)` / `ansi.hyperlink_close()`（两个 helper），
  `lines.py` 调它们（模块 docstring 的「一切转义字节只在这里构造」契约）。
- 测试：无 link 行与改前逐字节相同；有 link 行的字节原文；相等性语义（link 变则不相等、action 变仍相等）。

### T2 `core/lines.py`：`action_at` 纯函数

- `action_at(line, col) -> tuple[str, int, int] | None`：按段宽累加找 `col` 所在段；该段有 `action`
  → `(action, start_col, end_col)`（列区间左闭右开）；越界/无 action → None。
- 加进 `core` facade 导出与 `core/__init__.py` 的 docstring；`tests/test_api_root.py` 同步
  （`LAYER_ALLS["mocode_tui.core"]` 与 `DOWN_LISTED`）。
- 测试：多段行（含宽字符段）的命中/未命中/越界；纯函数无状态。

### T3 `core/lines.py`：`Text` 可点可悬停（D6）

- `Text` 实现 `Hoverable + Clickable`：
  - `hover: bool`（协议字段；Text 的视觉在段级，组件级翻转**不改变渲染**——docstring 写明）；
  - `hover_at(row, col) -> bool`：用 `self._rows`（上次 render 的行表，`render` 时缓存）定位段，
    段有 `action` → 记 `_hover_span=(row,start,end)` 并在渲染时对该段 `merge(theme.hover)`（渲染时
    对副本合并，不改缓存文本）；`row < 0` 清空。返回是否变化；
  - `click(row, col) -> bool`：命中带 action 的段 → `chosen = action`、返回 True；否则 False（不消费，
    让宿主/其他策略继续）；
  - `chosen: str | None`。
- `render(width)` 里缓存行表（`self._rows`）：未 hover 时输出与改前**逐字节一致**。
- 测试：hover 进/出/换段三态与字节（含 `hover_at(-1,-1)` 归零）；click 命中/未命中；`chosen` 读一次语义。

### T4 `widgets/markdown/`：链接载荷 + Markdown 可点（D6）

- `inline.py` 的 `LinkInlineRule`：`Segment(label, theme.link, link=url, action=url)`（URL 仍不进文本）。
- `Markdown` 实现 `Hoverable + Clickable`：`render` 缓存的行表之外再缓存「行 → 段列区间」的
  索引（一次性从渲染出的 `Line` 派生，不改任何 rule）；`click`/`hover_at` 语义与 `Text` 相同；
  hover 的渲染 = **对缓存基行的后变换**（复制行、命中段 `merge(theme.hover)`），基行缓存保持
  hover 无关；`chosen: str | None`。
- 测试：链接段的 `link`/`action` 载荷；点击链接 → `chosen == url`；hover 高亮该段 + 归零字节；
  既有「label only」测试的更新说明（文本不变，只是 Segment 多了载荷）。

### T5 gallery + 文档

- gallery：`/content` 页的一处链接改由「点击 → toast + 页内 echo 行」回路演示（用现成
  `_read_picks` 或页面内读取）；`/overview` 索引行若已有 `Select` 则不动。
- `docs/COMPONENTS.md`：协议表补 `link`/`action` 语义（段级载荷 + OSC 8 + `action_at`）；
  `Markdown`/`Text` 条目补能力（Clickable/Hoverable）；build-your-own 加「给自定义组件加行内动作」
  小节的半页 recipe（用 `action_at`）。
- `docs/DESIGN.md`：命名 charter 加 `link`/`action`/`action_at`；Markdown 段补一句 OSC 8 链接。
- `README.md`：组件表 `Text`/`Markdown` 行补「clickable spans / OSC 8 links」。
- `tools/framebench.py`：基线注记更新（新 hash + 「OSC 8 链接字节」原因）。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` → 只增不减；被更新的既有 pin 清单（预期：`test_widgets_markdown.py` 的段相等
   断言、`test_api_root.py` 的 core 名单与 root 计数）。
2. `uv run python tools/framebench.py` → 新 hash（两次一致）+ 注记 diff。
3. `demo.py < /dev/null` exit 0；`--pages` 12 页头且 dump（`row.text`）与改前**逐字符一致**（OSC 8 不进文本）。
4. 探针：`Text` 的 click/hover 三态 + `chosen`；Markdown 链接点击 → `chosen`；`action_at` 的宽字符命中。
5. 归零证据：`hover_at(-1,-1)` 前后 `render` 与 `styled()` 字节相等（Text 与 Markdown 各一组）。
6. `NO_COLOR=1 --pages` exit 0；import 干净；README 块全绿。

## 禁触清单

- `Markdown` 的 `(text,width)` 缓存键与 `_StreamCache` 的续渲染语义（后变换必须在其外）
- 既有 `Line.styled()` 无 link 路径的字节（防回归）
- `Pointer`/`FocusRing` 的派发代码（本波不改它们；命中语义由组件实现）
- `examples/` 除 T5 点名的两处；`specs/**`

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论（逐条 + 关键输出行 + pytest 数）/ 字节与命中探针 /
dump 逐字符一致证据 / framebench 新旧 hash 与注记 / 被更新的既有 pin 清单 / 偏差与取舍 /
未决问题 / 真机手测：未执行（OSC 8 的原生 cmd+click 属 lead 终验）。

# Spec tui-depth · W1 协议与色彩（波次 W1）
> ✅ 已合并 2026-10-17 @ `td1-protocol`（tip `3a34faa`）→ main `2925ef6`；1029 passed，hash 重录 `de48e747…`。
> 分支 `td1-protocol`；前置：无（从最新 main `0d8bdc7` 切出）；深读：`00-overview.md`（D1–D5、D16、
> 门禁、现状锚点表）。
> **最高约束：默认参数下既有字节 pin 只允许因「2026 包裹」一处变化（本波有意重录 render-hash）；
> 其余新能力一律默认关/维持现状，`Line.styled()` 与 `Style.prefix()` 的缓存语义不得改变。**

## 目标

1. DECSET 2026 同步输出：一帧字节并入 painter 的单次 join。
2. DECSET 1004 焦点事件：screen/TUI 开关 + decoder 解 `ESC[I`/`ESC[O`。
3. 颜色模式：`ColorMode`、环境探测、纯函数降级，painter 取字节路径应用。
4. OSC 2 窗口标题 + DECSCUSR 光标形状（ansi helper + TUI 方法 + gallery 接线）。
5. VT 的 CSI 修饰参数（shift+方向/Home/End）→ `s-*` 键名。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| 帧字节唯一出口（join + flush）；未变化帧零字节契约 | `core/painter.py:84-115`、`:106`；`docs/DESIGN.md:382` |
| 样式→SGR：`Style.prefix()`（`_prefix` 实例缓存）、`Line.styled()`（每 Line 缓存） | `core/style.py:138-151`、`core/lines.py:140-165` |
| 颜色形态：名字 / `#rrggbb` / `(r,g,b)`；`FG_CODES` 16 名；无降级 | `core/style.py:35-108` |
| enter/leave 字节顺序契约（1049h → 25l → tracking → paste，leave 严格反序） | `core/screen.py:123-150`；`tests/test_screen.py:60-119,157-172` |
| 环境探测/能力概念：全无（grep `NO_COLOR/COLORTERM/1004/2026/DECSCUSR` 零命中） | —— |
| decoder CSI 现状：修饰位被丢弃 | `keys/decoder.py:300-345`、`:315-316` |
| Painter 构造点与 TUI 参数 | `app.py:239-252`、`app.py` 的 `self.painter` |
| 字节 pin 清单（预期同步更新） | `tests/test_painter.py:36-37,51-52,85,140-142,174`、`test_screen.py:60-119,157-172`、`test_ansi.py:30-93`、`test_style.py:33-58`、`test_api_root.py:70-74` |

## 工单（按序执行，每项一个 commit）

### T1 `core/ansi.py` + `core/painter.py` + `app.py`：同步输出（D1）

- `ansi.py`：`begin_sync_update() -> "\x1b[?2026h"` / `end_sync_update() -> "\x1b[?2026l"`，
  加进 `__all__`（分组顺序不变）。
- `painter.py`：`Painter(screen, *, sync=True)`；`paint()` 里把本次 **非空** 字节并入同一 join：
  `payload = "".join(writes)`；`payload` 非空时写 `begin + payload + end`（仍是一次 write + 一次 flush）；
  空 payload 仍零字节。光标锚路径（只动光标的那次 write）同样包裹。
- `app.py`：`TUI.__init__(..., sync=True)` → `Painter(..., sync=sync)`；类 docstring 一句
  「同步输出默认开，终端不支持则忽略；空帧零字节契约不变」。
- 测试：`test_ansi` 两条字节；`test_painter` 现有 pin 更新为含包裹的形态 + 新增「未变化帧零字节」
  「sync=False 还原旧字节」两条。
- **有意变化**：`tools/framebench.py` 的 render-hash 本波重录（把新值写进 docstring 注记，并写明
  原因「2026 包裹字节」）。先跑两次证明确定性。

### T2 `core/ansi.py` + `core/screen.py` + `keys/decoder.py` + `app.py`：焦点事件（D2）

- ansi：`enable_focus_events() -> "\x1b[?1004h"` / `disable_focus_events() -> "\x1b[?1004l"`。
- screen：`TerminalScreen(*, mouse=True, paste=True, hover=False, focus_events=False)` 与
  `HeadlessScreen(..., focus_events=False)`；enter 在 paste 之后追加 focus 字节，leave 在最前
  （严格反序）；默认 False → 现有字节 pin 不动。
- decoder：`ESC[I` → `Key("focus_in")`、`ESC[O` → `Key("focus_out")`（加进 CSI 已知表；两序列
  与既有 `ESC[A` 系列同层解析）。
- `TUI.__init__(..., focus_events=False)` → 默认 screen 透传。
- 测试：decoder 两条；screen enter/leave 开关两态；app 透传一条。
- **宿主契约（写进 docstring）**：Pointer 仍只看鼠标；`focus_out` 的 scrub（hover 清理、动画暂停）
  由宿主做（gallery 在 W1 的 T4 接线）。

### T3 `core/style.py` + `core/lines.py` + `core/painter.py` + `core/screen.py` + `app.py`：颜色模式（D3）

- `style.py`（新增公开面，纯函数）：
  - `ColorMode = Literal["truecolor", "256", "16", "none"]`；
  - `detect_color_mode(env=None) -> ColorMode`：`NO_COLOR` 存在或 `TERM == "dumb"` → `"none"`；
    `COLORTERM` ∈ {`truecolor`,`24bit`} → `"truecolor"`；`TERM` 含 `256color` → `"256"`；
    其余 → `"truecolor"`（保持现状）；
  - `sgr_prefix(style, mode="truecolor") -> str`：`truecolor` 直接委托 `style.prefix()`（缓存不变）；
    `256`/`16` 把 hex/tuple 量化（6×6×6 立方 + 灰阶 / 最近 16 色，标准 xterm 参考表为模块常量；
    命名色在两模式下保持其基础码）；`none` 去 fg/bg、保留属性（bold/dim/italic/underline/reverse/strike）。
- `lines.py`：`styled_with(line, mode) -> str` —— 与 `Line.styled()` 同样的段拼接与 RESET 规则，
  但不缓存；`Line.styled()` **一行不改**。
- `painter.py`：`color_mode` 取自 screen（`getattr(screen, "color_mode", "truecolor")`）；
  `mode == "truecolor"` 走 `row.styled()`，否则 `styled_with(row, mode)`。
- `screen.py`：`TerminalScreen(color_mode="auto")`（`__init__` 里 `detect_color_mode()` 解析成具体模式，
  存 `self.color_mode`）；`HeadlessScreen(color_mode="truecolor")`（测试确定性）。
  `TUI.__init__(..., color_mode: ColorMode | None = None)` → 非 None 时透传给默认 screen。
- 测试：`test_style` 量化/前缀各模式（含一组已知 RGB → 256 索引的对照）、`detect_color_mode` 的
  env 矩阵、painter 三模式字节各一条、`HeadlessScreen` 默认仍 truecolor。
- **验收补充**：`NO_COLOR=1 uv run python examples/demo.py --pages` → exit 0（无颜色路径不抛）。

### T4 `core/ansi.py` + `app.py` + gallery：标题与光标形状（D5）

- ansi：`set_window_title(text) -> str`（OSC 2 + BEL；清洗 `ESC`/`BEL`/C0 控制字符）、
  `cursor_shape(shape) -> str`（`block|beam|underline|default` → DECSCUSR 2/6/4/0）。
- `app.py`：`TUI.set_title(text)`、`TUI.set_cursor_shape(shape)`（写 screen；非 live 也记录，
  测试可断言）。
- `widgets/input.py` / `widgets/editor.py`：类属性 `cursor_shape = "beam"`（纯声明）。
- gallery（`examples/gallery/`）：`show()` 里 `tui.set_title(f"mocode-tui gallery · {page.name}")`；
  宿主循环里在 ring 变化后 `tui.set_cursor_shape(getattr(ring.focused, "cursor_shape", "block"))`；
  `demo.py` 的 TUI 调用保持不动（`hover=True` 已有）。
- 测试：ansi 两条（含标题清洗）；app 两条；gallery 探针（show 后 title 字节、聚焦 Input 后 beam 字节）。

### T5 `keys/decoder.py`：CSI 修饰参数（D16）

- 支持 `ESC[1;2X`（X ∈ {A,B,C,D,H,F}）→ `Key("s-up"/"s-down"/"s-right"/"s-left"/"s-home"/"s-end")`；
  无参形态（`ESC[A` 等）与其余修饰组合（如 `1;5A`）**维持现状**（后者仍按未知丢弃）。
- 测试：六键两条（up/right + home 抽样）、`1;5A` 仍丢弃、无参对照。

### T6 文档与基线注记

- `docs/DESIGN.md`：新节「Terminal capabilities」（2026/1004/ColorMode-探测-降级/OSC 2/DECSCUSR
  各自的契约与「为什么默认这样」）、命名 charter 表加新名（`begin_sync_update` 等不进表则不加——
  只加概念名：`ColorMode`/`detect_color_mode`/`sgr_prefix`/`styled_with`/`focus_in`/`focus_out`/`s-*`）、
  「非 TTY 契约」段补颜色与开关口径。
- `README.md`：驱动一览加 `sync/color_mode/focus_events` 与 `set_title/set_cursor_shape`；
  What-lives-where 的 `mocode_tui.core` 行补色彩与能力；「Testing without a terminal」段补
  `NO_COLOR=1 --pages` 一条。
- `docs/COMPONENTS.md`：Keys 段补 `s-*` 键名；若协议表无需改则不动。
- `tools/framebench.py`：docstring 基线注记更新（新 hash + 原因）。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` → 只增不减；贴 before/after 与**所有被更新的既有 pin**（文件名+条数）。
2. `uv run python tools/framebench.py` → 新 render-hash（贴两次一致）+ 注记 diff。
3. `uv run python examples/demo.py < /dev/null; echo exit=$?` → exit 0；`--pages` → 12 页头。
4. `NO_COLOR=1 uv run python examples/demo.py --pages` → exit 0。
5. `uv run python -c "import mocode_tui"` 干净；`uv run pytest tests/test_readme_examples.py -q` 全绿。
6. 字节探针（贴输出）：sync 包裹后的 `delta()`；`enable/disable_focus_events()`；`set_window_title` 清洗例；
   `cursor_shape` 四值；`ESC[1;2A`/`1;5A` 两态。
7. 颜色探针：同一 `Style(fg="#58a6ff")` 在四模式下的 prefix 原文；`detect_color_mode` 的 env 矩阵表。
8. 真机项（颜色升降级观感、无闪烁、标题/光标形状）→ 未执行，列 lead 终验。

## 禁触清单

- `Line.styled()` 与 `Style.prefix()` 的既有实现与缓存语义（只加旁边的新函数）
- 既有开关的默认值（`mouse/paste/hover`）与 1000/1002/1003/1006 的字节顺序
- `examples/` 除 T4 点名的两处接线外不改；`tests/test_readme_examples.py` 的 README 块结构
- `specs/**`（spec 归 lead）

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论（逐条 + 关键输出行 + pytest 数）/ 字节探针 / 颜色探针 /
framebench 新旧 hash 与注记 / 被更新的既有 pin 清单 / 偏差与取舍 / 未决问题 / 真机手测：未执行。

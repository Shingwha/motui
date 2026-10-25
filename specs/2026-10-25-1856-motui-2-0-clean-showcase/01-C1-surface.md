# C1 · 公开兼容层删除

> 分支 `2.0-clean/c1-surface`；前置：main @ `9d60730`；写入范围：`src/motui/app/{runtime,workspace,application,scrollbar}.py`、`src/motui/kernel/{document,frame,layout}.py`、`tests/**`、`examples/**`、`src/motui/demo/**`（仅可执行代码）、`tools/api-2.0.txt`
> 权威：`specs/2026-10-25-0900-motui-2-0-architecture/ref/source/{05-api-surface,04-runtime,02-core-contracts}.md`

## 目标

删除所有公开兼容层与旧参数，**行为与字节不变**：

1. `Runtime`/`App` 只收新构造面（`Terminal`/`TerminalOptions`），删旧 `screen/keys/mouse/hover/color_mode/focus_events/sync/interactive` 参数；
2. `split(axis: Axis, weights=...)`、`dock(placement=Placement)`、`undock(placement)`、`dock_region(placement)`；删字符串方向/`edge=`/`ratios=`；
3. `Section(id, widget, placement, sizing)`；删 `Section.component`/`Section.pin`；`Document.add` 删 `pin=`；
4. `App.open_palette(registry)` 只吃 `CommandRegistry`；删 list 路径；
5. `Scrollbar` 用 `ScrollbarStyles`；删 `style/thumb_style/track/thumb`；
6. 清理 `TUI`/`EveryHandle`/`take_result` 残留 docstring（仅文案）；
7. 1592 用例、57 byte/semantic、hash 不变。

**本波结束：`grep "pin="`/`split("`/`dock(edge=`/`Section.component`/`App(mouse=`/旧 Scrollbar 参数 = 0；全量绿；字节不变。**

## 前置上下文

- 必读：`../2026-10-25-0900-motui-2-0-architecture/handoff/W5-final.md` → 本组 `00-overview.md` → 本工单。
- 基线：`uv sync --locked`；`pytest`（1592 passed）；`golden --check`（57）；`semantic --check`（57）；hash `e7ca544b…`。
- 现状（grep 计数）：
  - `split("`/`dock(edge=`/`pin=` 约 136 处；
  - `Section.component`/`.pin` 约 54 处；
  - `App(`/`Runtime(` 构造约 56 处；
  - `open_palette(` 4 处；
  - `Scrollbar(` 14 处；
  - `TUI`/`EveryHandle`/`take_result` 残留 14 处（多为 docstring）。
- 新构造面（目标）：
  ```python
  App(theme=None, terminal: TerminalOptions | None = None, throttle=0.03,
      auto=True, title="", on_selection=None, handlers=None)
  Runtime(terminal: Terminal, *, throttle=0.03, interactive=False, theme=None)
  ```
  `TerminalOptions(screen=HeadlessScreen(...), input=ScriptedEvents(...))` 是测试/headless 的入口。
  `headless_tui` 构造 `Runtime(Terminal(TerminalOptions(screen=..., input=...)), interactive=False)`。
- 迁移规则：
  - `split("vertical", ratios=(...))` → `split(Axis.X, weights=(...))`；`"horizontal"` → `Axis.Y`。
  - `dock(component, edge="bottom")` → `dock(component, placement=Placement.BOTTOM)`；`"top"` → `Placement.TOP`。
  - `undock("bottom")` → `undock(Placement.BOTTOM)`；`dock_region` 同理。
  - `pin="top"` → `placement=Placement.TOP`；`pin=None` → `Placement.FLOW`；`pin="bottom"` → `Placement.BOTTOM`。
  - `section.component` → `section.widget`；`section.pin is None` → `section.placement is Placement.FLOW`。
  - `Document.add(..., pin=...)` → `placement=...`。
  - `App(screen=X, keys=Y, interactive=False)` → `App(terminal=TerminalOptions(screen=X, input=Y))`；`App(mouse=True, hover=True)` → `TerminalOptions(mouse=MouseMode.MOVE)`。
  - `Runtime(screen=X, keys=Y, interactive=False)` → `Runtime(Terminal(TerminalOptions(screen=X, input=Y)), interactive=False)`。
  - `open_palette([...])` → `CommandRegistry([...])` + `open_palette(registry)`。
  - `Scrollbar(tui, style=..., thumb_style=..., track=..., thumb=...)` → `Scrollbar(tui, styles=ScrollbarStyles(track=..., thumb=...))`；无覆盖时不用 styles。
- 已知坑：
  - `Split`/`Pane.split` 内部字符串方向要一起改成 `Axis`，否则 Runtime 与 kernel 不一致；`Split.rects` 用 `axis is Axis.X` 判断宽度。
  - `Section` 目前有 `widget`/`placement` 别名；本波删除 `component`/`pin`，不是只删调用——属性本体也删。
  - `App`/`Runtime` 删旧参数会破坏大量测试/示例；用 codemod + 逐文件修，不要保留 `**kwargs` 兜底。
  - `headless_tui` 的 signature 不变（`width,height,script,keys`），只改内部构造。
  - `Scrollbar` 的 `styles` 只覆盖 track/thumb；未给时仍从 theme/glyphs 解析；不改变 demo 字节。
  - `open_palette` 的 registry 用 `.options()`；`CommandPalette` 仍收 Option 列表。
  - docstring 里的 `TUI`/`EveryHandle`/`take_result` 改为 `Runtime`/`Timer`/`take()`；不涉及行为。
  - 57 golden/hash 不能变；本波只改构造/参数/属性名。
- 不改深层模型（Revisioned/ScrollState/RowRange/Themed 留 C2）；不改 demo 结构/文案（C4）。

## 工单（按序，每步一个 commit）

### T1 Runtime/App 新构造面

- `app/runtime.py`：
  - `Runtime.__init__(self, terminal: Terminal, *, throttle=0.030, interactive=False, theme=None)`；删除 `screen/keys/mouse/hover/focus_events/sync/color_mode` 参数与分支；`self.terminal=terminal`、`self._screen=terminal.screen`、`self.keys=terminal.input`（或属性代理）。
  - `read_event/enter/leave` 走 Terminal（已有）。
  - 保留 `screen`/`keys` 只读属性（内部/测试用），不是构造参数。
- `app/application.py`：
  - `App.__init__(*, theme=None, terminal: TerminalOptions|None=None, throttle=0.03, auto=True, title="", on_selection=None, handlers=None)`；构造 `Terminal(options)` + `Runtime(...)`。
  - `self.terminal`/`self.runtime`/`self.workspace`；`interactive` 由 `runtime`/terminal 推导。
- `testing/__init__.py`：`headless_tui` 内部改新构造；签名不变。
- 更新 `tests/**`、`examples/**`、`demo/**` 的 `App(`/`Runtime(` 调用；`App(screen=..., keys=...)`、`App(mouse=..., hover=...)` 全部迁移。
- 验证：`uv run pytest -q -p no:cacheprovider`；golden/hash 不变。

### T2 Axis/Placement

- `kernel/frame.py`：`Split(axis: Axis, weights, min_size=1)`；`rects` 用 `axis is Axis.X`；`Pane.split(axis, weights, ...)`。
- `app/runtime.py`：`split(axis: Axis, *, weights=(1,1), min_size=1, separator=True, pane=None)`；`dock(component, *, placement: Placement=Placement.BOTTOM, size=None)`；`undock(placement)`；`dock_region(placement)`。
- `app/workspace.py`/`application.py` 代理签名同步；`App.split/dock/undock` 只收 Axis/Placement。
- 全仓调用点 codemod：`split("vertical")`→`split(Axis.X)`、`"horizontal"`→`Axis.Y`；`dock(edge=)`/`undock(edge=)`/`dock_region(edge=)`→`placement=`；`ratios=`→`weights=`。
- 测试 `test_driver/test_app/test_frame`：枚举路径；`Placement.FLOW` 在 dock 抛 ValueError。
- 验证：`uv run pytest -q tests/app tests/kernel`。

### T3 Section.widget/placement

- `kernel/document.py`：
  - `Section.__init__(id, widget, *, placement=Placement.FLOW, sizing=Sizing.NATURAL)`；删除 `component`/`pin` 属性与 `_pin`/`_component` 字段（用 `_widget`/`_placement`）。
  - `Document.add(component, *, id=None, placement=Placement.FLOW, sizing=Sizing.NATURAL)`；删除 `pin`。
  - `Section.__repr__` 用 placement。
- `app/runtime.py`/`workspace.py`/`application.py`：`add` 删 `pin`，传 `placement`；`_holder`/`get/remove` 用 `.widget`。
- 全仓 `.component`→`.widget`、`.pin`→`.placement`；`pin="top"`→`placement=Placement.TOP`。
- 测试：`test_document`/`test_layout`/`test_driver`/`test_hit` 更新。
- 验证：`uv run pytest -q tests/kernel tests/app`。

### T4 registry-only palette + ScrollbarStyles

- `app/application.py`：`open_palette(registry: CommandRegistry, **kwargs)`；`commands = registry.options()`；其它类型抛 TypeError。更新测试/demo。
- `app/scrollbar.py`：
  ```python
  @dataclass(frozen=True, slots=True)
  class ScrollbarStyles:
      track: Style | None = None
      thumb: Style | None = None
  class Scrollbar:
      def __init__(self, host, *, pane=None, axis=Axis.Y, size=1, min_thumb=1,
                   styles: ScrollbarStyles | None = None, glyphs=GLYPHS, theme=None, scroll_tick=0.05)
  ```
  删除 `style/thumb_style/track/thumb`；`_resolve_track/_resolve_thumb` 先读 styles，再 theme。
- 测试 `test_scrollbar.py`/`test_app.py`/`test_command_palette.py` 更新。
- 验证：`uv run pytest -q tests/app`。

### T5 docstring 残留

- 清理 `TUI`/`EveryHandle`/`take_result` 的 docstring/注释（改为 `Runtime`/`Timer`/`take()`）；不改变展示字符串与 golden。
- 验证：`grep -rn "TUI\|EveryHandle\|take_result" src/motui --include=*.py` 只剩历史说明（报告列出）。

### T6 收口

- `tools/api.py --update`；全量验收；`grep` 门禁：
  - `grep -rn "pin=" src tests examples` = 0；
  - `grep -rn "split(\"" src tests examples` = 0；
  - `grep -rn "dock(.*edge=\|undock(\"" src tests examples` = 0；
  - `grep -rn "\.component\b\|\.pin\b" src tests` = 0；
  - `grep -rn "App(.*mouse=\|App(.*screen=\|Runtime(.*screen=" src tests examples` = 0；
  - `grep -rn "style=\|thumb_style=\|track=\|thumb=" src/motui/app/scrollbar.py` 只剩 styles 字段。
- 报告行数与剩余旧名。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. 57 byte golden、57 semantic、hash `e7ca544b…` 不变。
3. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
4. T6 grep 门禁全 0。
5. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth --quick` 全绿。

## 禁触清单

`kernel/{cell,hit,overlay,selection,style,glyphs,theme,text,events,keymap,geom,layout}.py`、`terminal/**`、`widgets/**`、`tests/golden/**`、`tools/{golden,framebench,semantic,growth}.py`、`README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`。

## 交接包

最后 commit 写 `handoff/C1-surface.md`：A 节给新构造面/Axis/Placement/Section/Registry/ScrollbarStyles/门禁；B 节给 codemod 策略、剩余旧名、C2 清单、坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验 / 探索审计 / 未决问题。

# C1 · 公开兼容层删除 · 交接

> 分支 `2.0-clean/c1-surface`；起点 `9d60730`；5 个工单 commit + 本 handoff。

## A. 交付面

```python
App(theme=None, terminal: TerminalOptions | None = None, throttle=0.03,
    auto=True, title="", on_selection=None, handlers=None)
Runtime(terminal: Terminal, *, throttle=0.03, interactive=False, theme=None)
```

- `App` 只构造一个 `Terminal(TerminalOptions)`；`runtime`/`workspace`/`terminal`
  三件套不变，`interactive = terminal.live and isatty()`。
- `Runtime` 删 `screen/keys/mouse/hover/focus_events/sync/color_mode` 参数与分支；
  `keys` 镜像 `terminal.input`，交互式 `_enter_run` 仍可挂 `RawTerminalKeys`。
- `headless_tui` 签名不变，内部 `Runtime(Terminal(TerminalOptions(...)), interactive=False)`。
  `handlers=` 已进签名并保存在 `self.handlers`；消费留给 C3 的 Router（dispatch 顺序未改）。

### Axis / Placement

- `Split(axis: Axis, weights, min_size=1)`；`Axis.X` 切宽、`Axis.Y` 切高；
  `Pane.split(axis, *, weights=(1,1), min_size=1)`。
- `Runtime/Workspace/App.split(axis, *, weights=(1,1), ...)`；非 `Axis` 抛
  `ValueError("split axis must be an Axis ...")`。
- `dock(component, *, placement=Placement.BOTTOM, size=None)`、
  `undock(placement=Placement.BOTTOM)`、`dock_region(placement=...)`；
  `FLOW`/非枚举值抛 `ValueError`。字符串 edge 与 `ratios` 全删。

### Section / Document

- `Section(id, widget, *, placement=Placement.FLOW, sizing=Sizing.NATURAL)`；
  属性只剩 `widget`/`placement`/`sizing`，`.component`、`.pin` 本体删除。
- `Document.add(component, *, id=None, placement=..., sizing=...)`；
  `Pane/Runtime/Workspace/App.add` 同步；`snapshot`/layout 改读 placement，
  输出格式不变（`[id | top]`）。

### Registry-only palette / ScrollbarStyles

- `App.open_palette(registry: CommandRegistry, **kwargs)`；其它类型 `TypeError`。
- `Scrollbar(tui, *, pane, axis, target, size, min_thumb, styles, glyphs, theme,
  scroll_tick)`；`ScrollbarStyles(track, thumb)` 是唯一显式样式面；
  `track`/`thumb` 字形改由 `glyphs.bar_empty/bar_full` 提供（`replace(GLYPHS, ...)`），
  主题回退顺序不变。

### 门禁（真实输出）
```
pytest -q -p no:cacheprovider -> 1592 passed in 35.30s
golden / semantic --check     -> 57 / 57 topics match
framebench                    -> e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da
python -m motui < /dev/null   -> exit 0, 70 lines；--pages -> exit 0, 4059 lines
ruff / pyright                -> All checks passed / 0 errors, 0 warnings
lint-imports / api --check    -> 4 kept, 0 broken / 185 names match
growth.py                     -> pytest/golden/api pass, OK (full probe)
```

T6 grep（`src tests examples`）：`pin=` 0；`.split("vertical"|.split("horizontal")` 0；
`dock(.*edge=|undock("` 0；`.pin` 0；`block/section.component` 0；严格
`App(screen=|App(mouse=|Runtime(screen=` 0（宽松 regex 的 13 条均为
`TerminalOptions(screen=...)` 误命中）；`scrollbar.py` 只剩 `ScrollbarStyles` 字段与
`min_thumb` 文档。

## B. 过程、剩余与 C2

- codemod：按文件枚举调用点，`"vertical"→Axis.X`、`"horizontal"→Axis.Y`、`ratios→weights`、
  `pin="top"→placement=Placement.TOP`、`edge="top"→placement=...`；再逐文件修语义测试
  （字符串拒绝、FLOW 拒绝、weights 比例）。无 alias/`**kwargs` 兜底。
- 工单外但门禁必需（无行为变化）：`tools/{framebench,semantic}.py`（仅构造调用）、
  `app/{pointer,focus}.py`（`.widget` 与 docstring）、`widgets/table.py`（recipe docstring）、
  `kernel/layout.py`（pin→placement 读取）。
- 剩余旧名：`TUI` 8 处——`motui/__init__.py` 的 “TUI toolkit” 文案 + `terminal/terminal.py`、
  `widgets/{choice,list,table,textfield}.py` 的失效交叉引用（禁触文件）；
  `EveryHandle`/`take_result` 0。非 Section 的 `.component` 21 处
  （`FormField.component`、markdown 模块路径）保留。
- demo 展示字符串未改：`overview.py` `_INTRO` 仍写 `App(hover=True)`，`interactions.py`
  api_line 仍列旧 Scrollbar 参数；按“demo 展示字符串不改”保留，C4 统一更新。
- C2：`Revisioned→touch()`、`Themed→Widget.style()`、`RowRange→RowSpan`、`ScrollState→Scroll`；
  `App.dispatch` if 链→Router 并消费 `App.handlers`；Runtime/Workspace/Application 继续实拆。
- 坑：`Split.rects`/`Pane.close` 统一用 `axis is Axis.X`；`_dock_edge` 是 placement→edge 的唯一校验点，`FLOW` 在进入 frame 前拒绝。

## C. 路径、提交与行数

关键路径：`src/motui/app/{runtime,workspace,application,scrollbar}.py`、`src/motui/kernel/{document,frame,layout}.py`、`src/motui/testing/__init__.py`、`tests/**`、`examples/dashboard.py`、`src/motui/demo/**`（仅可执行代码）、`tools/api-2.0.txt`。

commit：`10ac982` runtime 构造面 · `077e56c` Axis/Placement · `cca5874` Section.widget/placement
· `75e5195` registry/ScrollbarStyles · `cc5ff55` frame docstring · 本 handoff commit。

行数（wc -l）：runtime 1496（原 1617）、application 847（891）、workspace 274（285）、
scrollbar 683（671）、document 538（571）、frame 1709（1714）、layout 998（未改）。
C3 目标 Runtime/Workspace ≤450、App ≤250。

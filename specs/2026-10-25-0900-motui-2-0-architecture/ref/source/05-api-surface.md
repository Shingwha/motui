# 05 · API 面：公开层、命名、返回类型、扩展规则

> 上级：`01-architecture.md`　相关：`02` `03` `10-waves/W4-runtime-api.md`
> 状态：ready

## 1. 目标

让 2.0 的公开面**更短、更一致、更可扩展**，同时不引入新层。四条规则：

1. 值拥有行为，函数只做构造/度量（ADR-016）；
2. 一个概念一个门（ADR-017）；
3. 引擎值类型 `kw_only + 默认值 + 类方法入口`（ADR-011）；
4. 调用面收敛：`Section` / `Axis` / `Placement` / `TerminalOptions` / `take()` / `walk()`（ADR-018/019/022/023）。

## 2. 公开层

| 命名空间 | 内容 | 目标数量 |
|---|---|---|
| `motui`（root） | 应用作者需要的东西 | ~28 |
| `motui.kernel` | 值、协议、`text` 度量、构造入口 | ~35 |
| `motui.terminal` | `Screen` `Terminal` `TerminalOptions` `MouseMode` `Clipboard` `Capability` `Decoder` | ~15 |
| `motui.widgets` | 组件 | ~42 |
| `motui.app` | `App` `Runtime` `Workspace` `Router` `Command` 等 | ~18 |
| `motui.testing` | `headless` `advance` `snapshot` `emulator` | ~10 |

**硬规则**

- `kernel` 不导出任何“第一个参数是 `Line`/`Surface`/`Selection`/`Scroll`/`MarkSet`”的自由函数；
- `terminal` 不导出 escape 构造器；`ansi` 私有；
- root 不导出 `clear_screen` / `cursor_position` / `enter_alt_screen` 之类字节函数。

## 3. 命名对照表（1.x → 2.0）

| 1.x | 2.0 | 理由 |
|---|---|---|
| `render(width)` | `render(Constraints)` | 几何 |
| `Block` / `pin="top"` | `Section` / `Placement.TOP` | 枚举替代字符串 |
| — | `Sizing.FILL` | 尺寸策略 |
| `Revisioned.revision()` | `Widget.touch()` | 自动失效 |
| `handle(event) -> bool` | `on_key/on_mouse/on_paste/on_resize/on_focus` | 类型化 |
| `Clickable/Activable/...` | `clickable/activatable/...` | 能力是属性 |
| `Clickable.click(row,col)` | `on_click(pos: Pos)` | 坐标值 |
| `Container.child_at(row,col)` | 保留，但由 `children` 兜底 | 结构显式 |
| `TUI` | `Runtime` + `Workspace` + `Terminal` | 单一职责 |
| `TUI.refresh()` / `paint()` | `Runtime.invalidate()` / `paint_now()` | 语义 |
| `ScrollState` | `Scroll(x: Axis, y: Axis)` | 两轴形状 |
| `ScrollView` | `ScrollPanel(axis=)` | 一套滚动 + L1 |
| `Hit.chain` | `HitPath` | 语义 |
| `EveryHandle` | `Timer` | 与 `every` 对称 |
| `App.add() -> str` / `TUI.get() -> Component` / `Document.add() -> Block` | `Workspace.add/get/remove -> Section` | 返回类型统一 |
| `split("vertical")` / `dock(edge="bottom")` | `split(Axis.X)` / `dock(placement=Placement.BOTTOM)` | 枚举替代字符串 |
| `ratios` | `weights` | 它们是权重不是比例 |
| `List(window=8)` / `Select(max_rows=8, window=True)` | `height=8` + `window="top"` | 同名不同义修正 |
| `take_result()` / `Resultful` | `take()` / `HasResult` | 读一次清空；`None` = 无事件 |
| `set_focus_targets` / `FocusManager.add/remove` | 删除；树推导 | 加控件即可聚焦 |
| `App(mouse=, hover=, ...)` | `App(terminal=TerminalOptions(...))` | 三份开关归一 |
| `Command(name, description, ...)` | `Command(name=..., group=..., ...)` | `kw_only`，补 `group` |
| `open_palette(list[object])` | `open_palette(registry)` | 类型明确 |
| `line.fit/fill/fuse/overlay/rest` | `line.clip/pad/fused/under/band` | 值方法 + 词表 |
| `cut_line/slice_line/action_at/styled_with/wrap_line` | `line.cut/slice/action_at/styled/reflow` | 值方法 |
| `fuse/overlay/rest` | `line.fused/under/band` | 值方法 |
| `highlight/extract` | `selection.highlight/extract` | 值方法 |
| `descend/descend_chain` | `HitPath.of(...)` | 值方法 |
| `mark_prefix` | `MarkSet.prefix` | 值方法 |
| `visible_width` | `text.width` | 命名空间 |

## 4. 返回类型：`Section`

```python
section = app.add(Text("hello"), placement=Placement.TOP)
section.id        # str
section.widget    # Component
section.placement # Placement
section.sizing    # Sizing
```

`Workspace.add/get/remove` 都返回 `Section`；`Document` 内部同样返回 `Section`。不再有“有时 id、有时组件、有时 block”。

## 5. 位置：`Axis` / `Placement`

```python
left, right = app.split(Axis.X, weights=(1, 2))   # X = 左右切
app.dock(StatusLine(), placement=Placement.BOTTOM)
```

- `Axis.X` 切宽度，`Axis.Y` 切高度；
- `Placement` 与 `Section.placement` 是同一个枚举；
- 字符串入口删除，不保留 alias。

## 6. 终端：`TerminalOptions`

```python
app = App(
    terminal=TerminalOptions(mouse=MouseMode.MOVE, color_mode="auto"),
    theme=Theme.dark(),
    throttle=0.03,
)
```

- `App` 不再有 `mouse/hover/color_mode/focus_events/sync/keys/screen`；
- `TerminalOptions` 是唯一配置面；
- `MouseMode` 只有 OFF/BUTTON/DRAG/MOVE。

## 7. 命令：`Command` / `CommandRegistry`

```python
registry = CommandRegistry()
registry.add(Command(
    name="theme.next",
    group="Appearance",
    description="Switch theme",
    keys=("c-t",),
    handler=self.next_theme,
))
registry.bind(app)                 # 接 keys -> invoke
app.open_palette(registry)         # 直接吃 registry
```

- `Command` 是 `kw_only`，避免 demo 里“第二个位置参数是 description”的误用；
- `group` 是一等字段（demo 曾把 `topic.group` 塞进 `description`）；
- `bind` 把 `keys` 接到 `invoke(name)`，`open_palette` 直接接受 registry。

## 8. 结果：`take()` / `walk()`

```python
picked = select.take()             # Option | None
checked = box.take()               # bool | None
if checked is not None: ...        # False 是真实结果
```

- 状态属性（`selected`/`checked`/`text`/`open`）可反复读；
- `take()` 读一次清空，`None` = 无事件；
- 批量收集用 `Widget.walk()`，**不做** per-widget `on_result`（ADR-023）。

## 9. 行操作词表

| 动词 | 含义 |
|---|---|
| `reflow(mode, width)` | 换行/截断的总入口 |
| `clip(mode, width)` | 单行截断 |
| `pad(width, style)` | 补宽 |
| `band(width, style)` | clip + pad（行带） |
| `under(style)` | 底层样式 |
| `over(start, end, style)` | 区间叠加 |
| `cut(start, end)` | 按列切 |
| `slice(start, end)` | 按字符切 |
| `styled(mode)` | SGR 渲染 |
| `action_at(col)` | 点击载荷 |

`text.*` 只做字符串度量：`width` / `wrap` / `spans` / `fit` / `ellipsize` / `index_at` / `bounds`。

## 10. 扩展规则（加东西时怎么加）

| 想加什么 | 正确做法 | 禁止 |
|---|---|---|
| 新组件 | 新文件 + `Widget` 子类 + 测试 | 改 kernel |
| 新控制器 | `app/tiers/<name>.py`，构造 `(host, ...)` | 改 `App.dispatch` |
| 新终端开关 | 加进 `TerminalOptions` | 在 App/TUI/Screen 各加一遍 |
| 新终端能力 | `Screen` 上带默认值的属性 / 注入协作者 | 预置空字段 |
| 新媒体 | `terminal/graphics.py` + `Painter(..., graphics=)` | 改 `Component`/`Surface` 公开契约 |
| 新主题组 | `Theme` 加字段 | 组件里写死颜色 |

## 11. 刻意不做的抽象

- ❌ `WidgetContext` / `AppContext` 传进 `render`。
- ❌ `Controller` 基类（只要构造约定）。
- ❌ `TableSpec` / `Column` 值（保持 kwargs）。
- ❌ 应用级 `App(wrap=...)` / `App(mouse=...)` 开关。
- ❌ 为统一而统一（`Rect.of` 这种没有行为的构造器不塞方法）。
- ❌ `Label` / `StyledText` 拆分（没有真实需求）。
- ❌ `DocPos`（待讨论；见 `13-risks-migration.md` 未决项）。

## 12. 迁移与验收

- 迁移表见 `13-risks-migration.md`；
- 验收：`tools/api.py --check` 快照 + 第 2 节的导出面计数；
- 每个公开 API 有 docstring 与一个可执行示例（CI 跑）。

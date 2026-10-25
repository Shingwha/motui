# 13 · 风险与迁移

> 上级：`README.md`
> 状态：ready

## 1. 风险登记

| # | 风险 | 影响 | 概率 | 对策 | 触发/回滚 |
|---|---|---|---|---|---|
| R1 | 自动失效漏掉就地修改（`list.append`） | 界面不刷新 | 中 | `touch()` 逃生口；每个可变 widget 一个“变更即失效”测试；`MOTUI_NO_CACHE=1` 对照跑 | 发现即补 `touch()`，不影响架构 |
| R2 | 单趟 sizing 的 FILL 顺序 | 布局不可预测 | 中 | `Document.add` 校验“至多一个 FILL、在所有 FLOW 之后” | 构造期 `ValueError` |
| R3 | 一次性改 33k 行 | 长期不绿 | 高 | 分波 + 字节级门禁 + 每波可独立合并 | 回退当前波 |
| R4 | golden 全变 | 无法判断重构/回归 | 高 | 语义 golden + 差异分类报告 | W2 重录，W5 删旧 |
| R5 | 性能回退（树传播 + Surface） | 帧成本上升 | 中 | framebench 阈值 + 每波跑 | 超 10% 阻断 |
| R6 | Canvas 引入第二渲染路径 | 选择/hit/golden 失效 | 中 | 硬规则：Canvas 只产 Surface；CI 检查 import | 架构评审 |
| R7 | Screen ABC 影响第三方实现 | 兼容性 | 低 | 只加带默认实现的成员；growth 演练 | 保留旧 Protocol 适配器？不，2.0 断代 |
| R8 | 横向滚动与文档流混淆 | 视觉怪异 | 中 | L1 只给 ScrollPanel；文档 pane 仍 y-only | 文档 5.6 |
| R9 | `Input` 单行水平跟随的游标几何 | 输入错位 | 中 | 复用 `text.spans` + 专门测试 | 回退 `WORD` 默认 |
| R10 | 包大小/启动变慢 | 用户体验 | 低 | 无新依赖；import 图检查 | — |

## 2. 迁移总表（1.x → 2.0）

| 1.x | 2.0 | 备注 |
|---|---|---|
| `App(mouse=, hover=, color_mode=, focus_events=, sync=, keys=, screen=)` | `App(terminal=TerminalOptions(...))` | MouseMode |
| `App.tui` | `App.runtime` / `App.workspace` / `App.terminal` | TUI 删除 |
| `app.add(...) -> str` | `app.add(...) -> Section` | `section.id` |
| `app.get(id) -> Component` | `app.get(id) -> Section` | `section.widget` |
| `app.split("vertical", ratios=...)` | `app.split(Axis.X, weights=...)` | 枚举 |
| `app.dock(c, edge="bottom")` | `app.dock(c, placement=Placement.BOTTOM)` | 枚举 |
| `ScrollView` | `ScrollPanel(axis=)` | 两轴 |
| `take_result()` | `take()` | `None` = 无事件 |
| `Resultful` | `HasResult` | 协议名 |
| `set_focus_targets` / `FocusManager.add/remove` | 删除 | 树推导 |
| `handle(event)` | `on_key/on_mouse/...` | hooks |
| `Clickable/Activable/...` | 能力属性 | — |
| `Revisioned.revision()` | `touch()` | 自动失效 |
| `Themed` | `Widget` + `style(group)` | 一套解析 |
| `EveryHandle` | `Timer` | runtime |
| `RowRange` | `RowSpan` | layout |
| `Block` | `Section` | — |
| `pin="top"` | `placement=Placement.TOP` | — |
| `Line.fit/fill/fuse/overlay/rest` | `line.clip/pad/fused/under/band` | 值方法 |
| `cut_line/slice_line/action_at/styled_with/wrap_line` | `line.cut/slice/action_at/styled/reflow` | 值方法 |
| `highlight/extract` | `selection.highlight/extract` | 值方法 |
| `descend/descend_chain` | `HitPath.of(...)` | 值方法 |
| `mark_prefix` | `MarkSet.prefix` | 值方法 |
| `visible_width` | `text.width` | 命名空间 |
| `Command(name, description, ...)` | `Command(name=..., group=..., ...)` | kw_only |
| `open_palette(list[object])` | `open_palette(registry)` | 类型 |

## 3. 迁移配方

### 3.1 App

```python
# 1.x
app = App(theme=Theme.dark(), mouse=True, hover=True, throttle=0.03)

# 2.0
from motui import App, MouseMode, TerminalOptions
app = App(
    theme=Theme.dark(),
    terminal=TerminalOptions(mouse=MouseMode.MOVE),
    throttle=0.03,
)
```

### 3.2 结果

```python
# 1.x
if (picked := sel.take_result()) is not None: ...

# 2.0
if (picked := sel.take()) is not None: ...

# 批量
for w in self.walk():
    if isinstance(w, HasResult) and (v := w.take()) is not None: ...
```

### 3.3 自定义 widget

```python
# 1.x
class Mine(Widget):
    def render(self, width): ...
    def handle(self, event): ...

# 2.0
class Mine(Widget):
    focusable = True
    keymap = {"enter": "activate"}
    def render(self, c: Constraints) -> Surface: ...
    def on_action(self, name: str) -> bool: ...
```

### 3.4 自定义 Screen

```python
# 1.x: Protocol（结构性）
class MyScreen: ...

# 2.0: 继承 ABC；只实现稳定成员
class MyScreen(Screen):
    ...
```

### 3.5 主题

```python
# 1.x
Widget(theme=...); Themed(theme=...)

# 2.0
Widget(theme=..., styles=Styles(rows=RowStyles(...)))
self.style("rows")
```

### 3.6 测试

```python
# 1.x
tui = headless_tui(80, 24); tui.paint()

# 2.0
from motui.testing import headless
tui = headless(AppUnderTest)
tui.advance(0.1); tui.press("enter")
assert tui.cell(0, 0) == "…"
```

## 4. 删除名单（不保留 alias）

`take_result`、`Resultful`、`TUI`、`App.tui`、`Revisioned`、`Themed`、`set_focus_targets`、`EveryHandle`、`RowRange`、`ClampedCursor`、`mark_prefix`、`fit/fill/fuse/overlay/rest` 自由函数、`ansi.*` 公开导出、`core/` 包、`Block`、`pin` 字符串、`ScrollView`、`ScrollState`、`split("vertical")`、`dock(edge=...)`、`Table(wrap=bool)`。

## 5. 未决项（不阻塞 2.0）

| 项 | 状态 | 说明 |
|---|---|---|
| `DocPos` | 待讨论 | 若 `Find`/`Hit`/选区都要读字段，2.1 加 |
| `Table` 列规格 | 不做 | 保持 kwargs |
| `Styles` dict | 不做 | 保持 dataclass |
| `Label`/`StyledText` | 不做 | 除非真实需求 |
| `on_result` | 不做 | ADR-023；将来只考虑 App 级单钩子 / `Modal.on_close` |
| 图片协议 | 2.x | 不预置字段（ADR-011） |
| 文档流横向滚动 | 2.x | L1 已覆盖不换行内容 |

## 6. 回滚策略

- 每波一个合并点；失败只回退该波。
- W0/W1 有字节级基线，回退确定。
- W2 之后 golden 有差异分类，回退需附分类回滚说明。
- 发布前不 tag/push/PyPI，除非用户明确要求。

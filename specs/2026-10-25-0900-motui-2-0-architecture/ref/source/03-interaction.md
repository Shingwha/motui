# 03 · 交互：Widget 树 + 类型化 hooks + keymap→action

> 上级：`01-architecture.md`　相关：`10-waves/W3-tree-interaction.md`
> 状态：ready

## 1. 目标

把“组件是什么、能做什么、键位怎么映射、焦点怎么走、事件怎么派发”收成一套显式模型：

1. 显式树：`parent` / `children` / `walk()`；
2. 能力是属性：`focusable` / `clickable` / `hoverable` / `activatable`；
3. 交互是类型化 hooks：`on_key` / `on_mouse` / `on_paste` / `on_resize` / `on_focus` / `on_click` / `on_hover` / `on_drag` / `on_action`；
4. 键位是数据：`keymap: key → action`；
5. 焦点从树推导，不注册；
6. 结果只经 `take()`；遍历用 `walk()`。

## 2. 为什么

| 1.x 问题 | 证据 | 后果 |
|---|---|---|
| 树靠属性名遍历 | `_CHILD_ATTRS = ("child","children","body","input","list","_fields")` | 新容器改个子节点名，主题/焦点静默失效 |
| 交互靠反射 | `_looks_interactive` 检查类是否覆盖 `handle/activate/select/move/toggle` | 能力判定隐式 |
| 能力靠 isinstance | 116 处 `isinstance`，18 处能力协议 | 每层都要 import 协议并探测 |
| 键位硬编码 | `FocusManager.handle` 写死 up/left/down/right/enter；`keymap` 只给文本框用 | 列表不能 rebind `j/k` |
| 焦点要注册 | `set_focus_targets`、`FocusManager.add/remove`、`owns_focus` | 加控件要手动登记 |
| 结果靠轮询 | 21 个 `take_result()`；demo 每轮 walk 整棵树 | 遍历难看，但回调会带来重入 |

## 3. Widget 契约

```python
class Widget:
    parent: Widget | None
    children: list[Widget]

    def walk(self) -> Iterator[Widget]: ...   # 深度优先，含 self

    focusable: bool = False
    clickable: bool = False
    hoverable: bool = False
    activatable: bool = False

    keymap: Mapping[str, str] = {}            # key → action

    def on_key(self, e: KeyEvent) -> bool: ...
    def on_mouse(self, e: MouseEvent) -> bool: ...
    def on_paste(self, e: PasteEvent) -> bool: ...
    def on_resize(self, e: ResizeEvent) -> None: ...
    def on_focus(self, gained: bool) -> None: ...
    def on_click(self, pos: Pos) -> bool: ...
    def on_hover(self, pos: Pos | None) -> bool: ...
    def on_drag(self, pos: Pos, phase: DragPhase) -> bool: ...
    def on_action(self, name: str) -> bool: ...

    def touch(self) -> None: ...              # 失效（见 04）
```

规则：

- 返回 `True` = **消费**；返回值永远不表示“改变了”，改变由 `touch()` 表达。
- 容器只实现 `children`；坐标路由通过 `child_at`（可选）或默认矩形推导。
- `Component`（纯渲染）不需要继承 `Widget`；只有需要交互/失效的才继承。
- 容器可以设置 `focus_scope = True`（原 `owns_focus`），把焦点路由收进自己的子字段（`Form`）。

## 4. keymap → action

```python
class List(Widget):
    keymap = {"up": "prev", "down": "next", "home": "first", "end": "last",
              "pgup": "page_prev", "pgdn": "page_next", "enter": "activate"}

    def on_action(self, name: str) -> bool:
        return getattr(self, f"_do_{name}")()
```

- 默认 keymap 是类属性；实例可覆盖，合并规则是 `{**Type.keymap, **instance.keymap}`。
- `FocusManager` 不再硬编码方向键；它只把 key 交给当前焦点 widget 的 keymap。
- 未映射的 key 继续走 `on_key`，再走 App 绑定，再走 host。
- 用户 rebind：`lst.keymap["j"] = "next"`。

**为什么**

- 当前同一族里键位处理分散在 `FocusManager`（方向键）、widget 的 `handle`、`App.bind` 三处；改一个键要改三处。
- keymap 也让行为可按 action 测试（`lst.on_action("next")`），不必构造 `KeyEvent`。

## 5. 焦点：从树推导

- `Widget.focusable = True` 的节点自动进入焦点环，顺序 = 树的前序遍历；
- `Workspace.focus(widget)` / `focus_next()` / `focus_previous()` 是唯一入口；
- `FocusManager` 内部化；删除 `set_focus_targets` / `add` / `remove`；
- `focus_scope = True` 的容器（`Form`）自己路由到子字段；
- `Modal`/`Router` 的 trap 由 `Router` 内部 push/pop，不暴露给用户。

**为什么**

- 注册式焦点是 1.x 最大的“加控件忘登记”来源；树推导让“挂上去就能聚焦”。

## 6. 派发：Router

```python
Handler = Callable[[Event], bool]

DEFAULT_HANDLERS = (
    PaletteHandler(), ModalHandler(), FindHandler(), ToastHandler(),
    ControllersHandler(), WheelHandler(), DragHandler(), GestureHandler(),
    PointerHandler(), PaneFocusHandler(), FocusHandler(),
    PageKeyHandler(), BindingHandler(), HostHandler(),
)

app = App(handlers=DEFAULT_HANDLERS)
```

- 顺序即文档；`auto=False` 等价于 `handlers=()`。
- 每个 tier 是一个对象，只回答“是否消费”；不再在 `App.dispatch` 里写 10 层 if。
- 自定义策略：插入自己的 handler，或替换整个元组。

## 7. 指针 / 拖拽 / 选择

- `Pointer` 负责位置、hover、静止点击；
- `Drag` 负责 press/motion/release 三阶段，先于选择手势；
- `SelectionGesture` 负责文档空间选择与边缘自动滚动；
- 三者的顺序在 `DEFAULT_HANDLERS` 里可见；
- 横向滚动时，`Hit.col + Scroll.x.offset` 映射到组件列（见 `02` 第 6 节）。

## 8. 结果：`take()` / `HasResult` / `walk()`

```python
class HasResult(Protocol):
    def take(self) -> object | None: ...

# 状态可反复读：selected / checked / text / open
# 事件读一次清空：
picked = select.take()
if picked is not None: ...
```

- `None` = 没有待处理事件；`False`/`""`/`0` 是真实结果。
- `bool | None` 的组件必须用 `is not None` 判断（`Checkbox`/`Collapsible`/`Link`）。
- **不做 per-widget `on_result`**（ADR-023）：回调会在 dispatch 中引入重入/顺序副作用，并滑向消息总线。
- 需要批量收集时用公开树遍历：

```python
for widget in self.walk():
    if isinstance(widget, HasResult) and (value := widget.take()) is not None:
        self.handle_result(widget, value)
```

- `walk()` 同时替代 demo 的 `walk_objects` 与 `application.py` 的 `_walk`。

## 9. 重构方式（W3）

1. 新建 `widgets/base.py`：`Widget`（parent/children/walk/hooks/touch）、`Container`、`Cursor`、`MarkSet`。
2. 所有组件继承新 `Widget`；`__slots__` 保留；构造签名统一 `(theme=None, styles=None, glyphs=GLYPHS, ...)`。
3. 把 `handle(event)` 拆成 `on_*`；按键匹配迁移到 `keymap` + `on_action`。
4. 删除 `_CHILD_ATTRS` / `_walk` / `_looks_interactive` / 能力协议 `isinstance`。
5. `FocusManager` 内部化；删除 `set_focus_targets`。
6. 结果门：`take_result()` → `take()`；`Resultful` → `HasResult`。
7. 测试：每个 action 一个行为测试；焦点环前序；hover/click 坐标；`walk()` 去重。

## 10. 测试与门禁

- `isinstance` 总数从 116 降到 <10（能力探测为 0）；
- `handle()` 实现 ≤3（仅保留特殊控制器，如 Modal 的吞事件）；
- `lst.keymap["j"] = "next"` 生效；
- `Form`/`Dialog` 多字段路由仍正确；
- `Widget.walk()` 覆盖所有挂载组件，且不重复；
- `take()` 的 `None`/`False` 两条路径各有测试；
- 全量交互测试 1:1 平移（同一按键 → 同一状态变化）。

## 11. 不做的

- ❌ 消息总线 / retained tree / CSS。
- ❌ per-widget `on_result`（ADR-023）。
- ❌ 键位字符串别名表（`"esc"`/`"escape"` 只保留一种）。
- ❌ 多 stroke 和弦键位（2.x）。
- ❌ 自动把所有 `Widget` 注册进焦点（只有 `focusable=True`）。

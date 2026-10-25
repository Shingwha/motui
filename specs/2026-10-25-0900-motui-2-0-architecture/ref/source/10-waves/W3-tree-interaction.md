# W3 · Widget 树与交互

> 上级：`README.md`　依赖：`W1-kernel-split.md`　下一波：`W4-runtime-api.md`
> 状态：ready

## 1. 目标

把交互从“反射 + isinstance + 手写 handle”迁到：

- 显式树：`parent` / `children` / `walk()`；
- 类型化 hooks：`on_key/on_mouse/on_paste/on_resize/on_focus/on_click/on_hover/on_drag/on_action`；
- 能力属性：`focusable/clickable/hoverable/activatable`；
- `keymap → action`；
- 焦点从树推导；
- `take()` / `HasResult` / `walk()`。

## 2. 为什么

| 1.x | 证据 |
|---|---|
| 属性名遍历 | `_CHILD_ATTRS` + `_walk` |
| 反射判定交互 | `_looks_interactive` |
| 能力 isinstance | 116 处总数，18 处能力协议 |
| 手写 handle | 22 处 |
| keymap 只给文本框 | lists/trees 的方向键写死在 FocusManager |
| 焦点注册 | `set_focus_targets` + `FocusManager.add/remove` |
| 结果轮询 | 21 个 `take_result()`；demo 整树 walk |

## 3. 契约

见 `03-interaction.md`。关键点：

```python
class Widget:
    parent; children
    def walk(self) -> Iterator[Widget]: ...
    focusable/clickable/hoverable/activatable: bool
    keymap: Mapping[str, str]
    def on_key/on_mouse/on_paste/on_resize/on_focus/on_click/on_hover/on_drag/on_action(...)
    def touch(self) -> None: ...
```

- 返回 `True` = 消费；改变由 `touch()` 表达。
- `on_resize` 广播给整棵树（不只焦点）。
- `focus_scope=True` 的容器自己路由（`Form`）。

## 4. 任务

### 4.1 基座

- 新建 `widgets/base.py`：`Widget`、`Container`、`Cursor`、`MarkSet`。
- `Widget.walk()`：前序、含 self、按对象去重（防御共享子节点）。
- `Widget.touch()`：自身 + 祖先 generation。
- `Widget.__setattr__`：状态变更自动 `touch()`；`_` 开头跳过；`touch()` 作为就地修改逃生口。

### 4.2 hooks 迁移

- `handle(event)` 拆成 `on_*`；删除每个 widget 的按键 if 链。
- 能力属性替换能力协议；`isinstance` 检查改为 `if widget.clickable:`。
- `on_resize` 广播；`on_focus` 替换直接写 `focused` 的地方。
- `click(row,col)` → `on_click(pos: Pos)`；`hover_at` → `on_hover(pos | None)`；`drag` → `on_drag(pos, phase)`。

### 4.3 keymap → action

- 每个族定义默认 `keymap`；实例可覆盖。
- `FocusManager` 只把 key 交给焦点 widget 的 keymap；删除硬编码方向键。
- `on_action(name)` 是唯一行为入口；测试按 action 断言。
- `App.bind` 仍是全局绑定；顺序：widget keymap → widget on_key → App bindings → host。

### 4.4 焦点

- 焦点环 = `focusable` 节点的前序遍历。
- `Workspace.focus/focus_next/focus_previous` 唯一入口。
- 删除 `set_focus_targets` / `FocusManager.add/remove`；`FocusManager` 内部化。
- `owns_focus` → `focus_scope`。

### 4.5 结果与遍历

- `take_result()` → `take()`；`Resultful` → `HasResult`。
- 删除所有 `_pending` 的命名差异（统一 `_pending`）。
- 不加 `on_result`；demo 的 `_read_picks` 改用 `walk()`。
- `bool | None` 组件测试 `None`/`False` 两条路径。

### 4.6 组件迁移

按族迁移（每族一个 PR）：

1. `Text`/`Decor`/`layout`；
2. `List`/`Tree`/`Table`/`Choice`/`Nav`/`Tabs`/`Menu` → 统一 `Cursor`；
3. `Input`/`Editor` → `TextField`；
4. `Form`/`Dialog`/`Collapsible`；
5. `ScrollPanel`/`Scrollbar`；
6. `Find`/`Palette` → `Picker`（可与 W4 合并）。

## 5. 删除清单

- `_CHILD_ATTRS`、`_walk`、`_looks_interactive`
- `Clickable`/`Activable`/`Focusable`/`Hoverable`/`Container`/`Controller`/`Resultful` 能力协议（保留 `Component`/`Overlay`/`Scrollable` 消费侧协议）
- `set_focus_targets`、`FocusManager.add/remove`（公开）
- `ClampedCursor`（`widgets/strip.py`）
- `take_result` / `Resultful`

## 6. 门禁

- `isinstance` 总数 <10；能力探测 0；
- `handle()` 实现 ≤3；
- 交互测试 1:1 平移；
- `lst.keymap["j"]="next"` 生效；
- `Form`/`Dialog` 多字段路由；
- `Widget.walk()` 覆盖 + 去重；
- `take()` 的 `None`/`False` 测试；
- `pyright`（widgets）0 error。

## 7. 退出条件

- [ ] 树/hooks/keymap/焦点全部落地；
- [ ] 旧反射/注册 API 删除；
- [ ] `Cursor` 只有一套；
- [ ] `take()`/`walk()` 生效；
- [ ] 行为无回归。

## 8. 回滚

- 按族迁移，每族一个 PR；某族失败只回退该族。
- 基座（4.1–4.5）先合，组件迁移后合。

## 9. 交接

`W3-handoff.md`：各 widget 的迁移状态、剩余 `handle`、keymap 表、焦点环测试、`walk()` 用法。

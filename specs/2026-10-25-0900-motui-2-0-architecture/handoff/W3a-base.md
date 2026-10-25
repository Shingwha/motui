# W3a 交接 · Widget 树 / hooks / 失效基座（纯加法）

> 分支 `2.0/w3a-base`；起点 `eef1ae6`（W2.6b 合并后的工单排序 commit）。
> 前置：`ref/interfaces.md`、`handoff/W2.6b-overflow.md`、工单 `13-W3a-base.md`。
> 结论：T1–T3 完成；**1422 passed**（1393 旧 + 29 新）；57 byte / 57 semantic /
> render-hash `e7ca544b…2986da` 全不变；无组件、App、kernel 协议改动。

## A. 交付面与门禁

### Widget 实际签名（`src/motui/widgets/base.py`）
- `__slots__ = ("_generation", "children", "focused", "hover", "parent", "styles", "theme")`
- `parent: Widget | None`（默认 None）、`children: list[Widget]`（默认 `[]`）
- `generation` 只读属性：构造后为 0，随 `touch()` 单调 +1
- `walk() -> Iterator[Widget]`：前序、含 self、`id` 去重、只读 `children`、非 Widget 子节点也 yield
- `touch() -> None`：自身与祖先 generation 各 +1；迭代实现、`seen` 防环、父链无 `touch` 即停
- 能力类属性：`focusable/clickable/hoverable/activatable = False`；
  `keymap: Mapping[str, str] = {}`；`focus_scope = False`；旧 `owns_focus = False` 保留
- hooks（默认委托旧动词）：
  - `on_key/on_mouse/on_paste(e) -> self.handle(e)`
  - `on_resize(e) -> None`
  - `on_focus(gained) -> self.focused = gained`
  - `on_click(Pos) -> self.click(pos.y, pos.x)`
  - `on_hover(Pos | None) -> hover_at(pos.y, pos.x)`，`None` → `hover_at(-1, -1)`
  - `on_drag(Pos, phase: str) -> self.drag(pos.y, pos.x, phase)`
  - `on_action(name) -> self.activate() if name == "activate" else False`
  - `take() -> self.take_result()`
- `HasResult`：`@runtime_checkable Protocol`，唯一成员 `take() -> object | None`
- `Container(Widget)`：`__slots__ = ()`，`child_at(row, col) -> None`（默认不认领任何 cell）
- re-export：`Cursor`（`widgets/cursor.py`）、`MarkSet`（`widgets/mark.py`），同一对象，无重复实现
- `revision()` **仍返回 None**：没有启用任何缓存

### 门禁（本 worktree，Python 3.12.14 / uv 0.12.21）
- `pytest -q -p no:cacheprovider`：**1422 passed**
- `golden.py --check`：57 topics match；`semantic.py --check`：57 topics match
- `framebench.py`：`e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da`
- `python -m motui < /dev/null`：exit 0，70 行；`--pages`：exit 0，4059 行
- `ruff` All checks passed；`pyright` 0 errors；`lint-imports` 4 kept；
  `api --check` 181 names；`growth --quick` OK
- `grep -rn "def handle(" src/motui` = 22；`grep -rn isinstance src/motui` = 134（均与基线一致）

## B. 实现细节 / W3b 迁移提示

1. **`__setattr__` 规则（顺序）**：`parent` → 直接 `object.__setattr__`，不 touch；`children` →
   先 `list(...)`，写入后用 `hasattr(child, "parent")`（不是能力探测）给子对象设 `parent=self`，
   再 `touch()`；`_` 开头 → 直接写、不 touch；其它 → 写入后 `touch()`。
2. **构造**：`__init__` 用 `object.__setattr__` 装 parent/children/_generation/theme/styles/
   focused/hover，因此新建 widget 的 generation 为 0（构造不是“变更”）。子类即使不调
   `super().__init__()`，`touch()`/`walk()`/`generation` 也会用 `getattr(..., 默认)` 安全工作。
3. **children 重赋值不 detach 旧 child**（旧 child.parent 保持原值）；这是明确行为并已测试。
   `parent` 赋值不反向改 `children`；共享 child 只保留最后一次赋值的 parent，`walk()` 仍按 id 去重。
4. **touch 只向上**：root.touch() 不触及子节点；parent 链环（a↔b）只各加一次。祖先约定为
   Widget（`hasattr(parent, "touch")` 才继续，因此链上的普通对象会终止冒泡）。
5. **walk 只读显式 `children`**：不猜 `child/body/input/list/_fields`；非 Widget 子节点（纯
   Component）会被 yield 但没有 children；`Row`/`Column` 目前不是 Widget，本波未迁移。
6. **类级 keymap 共享**：基类 `{}` 是契约默认；W3b 合并规则放路由点
   `{**type(w).keymap, **instance.keymap}`，实例 rebind 前要复制，别原地改类字典。
7. **hooks 返回值 = 消费**：默认 hook 不 touch；组件迁移时保持“返回 True 只表示消费，
   变更由 state setter/touch 表达”。
8. **W3b 建议顺序**：先 `List/Tree/Table/Choice/Nav/Tabs/Menu` 统一 `Cursor` 与 on_action；
   再 `Form` 的 `focus_scope`；再 `Input/Editor`；最后把 `take_result` 调用点换 `take()`。
   每族只改组件文件与对应测试，基类不再动。
9. **re-export 只此一处**：`motui.widgets.base.Cursor is motui.widgets.cursor.Cursor`（测试锁定）；
   不要在新文件里复制 `Cursor`/`MarkSet`。根 facade 未导出
   `Container/HasResult/Cursor/MarkSet`（W5 收敛）。
10. **api 快照**：`--update` 重写后 181 行零 diff（Widget 构造签名未变）；
    `tools/api-2.0.txt` 无内容变化。

## C. 位置与 commit

- 源码：`src/motui/widgets/base.py`；测试：`tests/widgets/test_base.py`（新增 29 例）。
- commit：
  - `e7b50d6` widgets: the base widget grows an explicit tree and a generation counter（T1）
  - `b1f670f` widgets: typed hooks and capability flags delegate to the 1.x verbs（T2）
  - 本文件（T3 收口；含 facade 隔离测试）
- 禁触清单零 diff：`kernel/**`、`terminal/**`、`app/**`、其余 `widgets/**`、`tests/**`（除
  `tests/widgets/test_base.py`）、`tools/**`（除 `api-2.0.txt`）、`demo/**`、`tests/golden/**`、
  `pyproject.toml`、`uv.lock`、`README.md`、`docs/**`、`CHANGELOG.md`。
- `git diff --name-only eef1ae6`（代码）：仅 `src/motui/widgets/base.py`、`tests/widgets/test_base.py`。

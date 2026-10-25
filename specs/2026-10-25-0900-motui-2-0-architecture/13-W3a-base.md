# W3a · Widget 树 / hooks / 失效基座（加法，不改行为）

> 分支 `2.0/w3a-base`；前置：W2.6b 已合并（`0207647`）；写入范围：`src/motui/widgets/base.py`、`tests/widgets/test_base.py`、`tools/api-2.0.txt`
> 权威：`ref/source/03-interaction.md` §1–8、`10-waves/W3-tree-interaction.md` §4.1–4.5

## 目标

在**不改变任何现有行为**的前提下，把 W3 的基座作为加法引入：

1. `Widget` 树：`parent` / `children` / `walk()`（前序、含 self、对象去重）；
2. 类型化 hooks：`on_key/on_mouse/on_paste/on_resize/on_focus/on_click/on_hover/on_drag/on_action`，默认委托到旧动词（`handle/click/hover_at/drag/activate`）；
3. 能力属性：`focusable/clickable/hoverable/activatable`（类默认 False）；
4. `keymap`（类默认 `{}`）、`focus_scope`（默认 False）；
5. `touch()` + generation 向上冒泡；`__setattr__` 对公开属性自动 touch（`_` 开头跳过）；
6. `take()` 默认委托 `take_result()`；`HasResult` Protocol；
7. `Container` 基类（`Widget` + `children` + 默认 `child_at=None`）；`Cursor`/`MarkSet` 从现有模块 re-export。

**本波结束：1393 个旧用例全绿；57 byte + 57 semantic + hash 不变；新基座有独立测试；旧组件无需改动即可继续工作。**

## 前置上下文

- 必读：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W2.6b-overflow.md` → 本工单。
- 基线：`uv sync --locked`；`pytest`（1393 passed）；`golden --check`（57）；`semantic --check`（57）；`framebench` hash `e7ca544b…`。
- 现状：
  - `widgets/base.py:Widget` 有 `theme/styles/focused/hover` 与旧动词 `handle/click/drag/hover_at/activate/take_result/revision`，无树、无 hooks、无 touch。
  - `kernel/document.py` 有 `Clickable/Activable/Focusable/Hoverable/Container/Controller/Resultful/Revisioned` 协议与 `descend_chain`；本波**不删**。
  - `app/focus.py:FocusManager` 注册式；`app/application.py:_walk/_looks_interactive` 仍用属性名/反射；本波**不改**。
  - `widgets/cursor.py:Cursor`、`widgets/mark.py:MarkSet` 是独立模块；本波 re-export，不合并。
- 已知坑：
  - `Widget` 的子类都定义了 `__slots__`；基类新增 slot 会自动被继承，不要重复声明。
  - `__setattr__` 在 `__init__` 里触发 touch：`parent` 尚未设置时必须安全；`touch()` 只向上冒泡，不反向。
  - `children` 赋值要给有 `parent` slot 的子对象设置 `parent`（用 `hasattr`/`object.__setattr__`，不要 `isinstance` 能力探测）；纯 `Component` 没有 parent，跳过。
  - `walk()` 要能遍历挂在容器里的非 Widget 组件（它们没有 `children`），但只对 Widget 设置 parent。
  - 旧 `owns_focus` 必须继续可用（Form 等）；`focus_scope` 是新名，本波只加默认 False，不改任何组件。
  - `on_action("activate")` 默认委托 `activate()`；其它 action 返回 False。真正的 keymap 路由在 W3b。
  - 自动 touch 只对公开属性生效；`focused`/`hover`/`theme`/`styles` 变化会 touch（未来 Section 缓存用），本波没有消费者，不能用它改变渲染。
  - 不要改 `revision()` 的默认值（仍返回 None），否则未实现 revision 的组件会意外变成可缓存。
- 不改 `kernel/document.py` 的协议、不改 FocusManager、不改 App、不改任何组件文件。

## 工单（按序，每步一个 commit）

### T1 树与 touch

- `widgets/base.py`：
  - `__slots__` 增加 `parent`、`children`、`_generation`。
  - `__init__`：`self.parent = None`；`self.children = []`；`self._generation = 0`；再设 theme/styles/focused/hover。
  - `__setattr__` 规则：
    - `parent`：直接 `object.__setattr__`（不 touch、不递归）；
    - `children`：转 list，`object.__setattr__`，给每个有 `parent` 属性的 child 设 `parent=self`，然后 `touch()`；
    - `_` 开头：直接设；
    - 其它：设完 `touch()`。
  - `touch()`：`self._generation += 1`；若 `self.parent is not None` 且不是自己，`self.parent.touch()`；防止环（parent 链；测试用共享 child 时不要死循环）。
  - `walk()`：前序、含 self、按 `id` 去重；遍历 `getattr(node, "children", ())`；对非 Widget 子节点也 yield。
  - `@property generation`。
- 测试 `tests/widgets/test_base.py`：
  - 三层树的前序；共享 child 只出现一次；parent 指针正确；
  - child.touch() 让 child/parent/root generation 都 +1；
  - 设置公开属性触发 touch；设置 `_x` 不触发；设置 parent/children 不递归；
  - `children` 重新赋值后旧 child 的 parent 不变（或按实现明确行为），新 child 的 parent 正确。
- 只允许改：`widgets/base.py`、`tests/widgets/test_base.py`。
- 验证：`uv run pytest -q tests/widgets/test_base.py`。

### T2 hooks 与能力属性

- `widgets/base.py`：
  - 类属性：`focusable=False`、`clickable=False`、`hoverable=False`、`activatable=False`、`keymap: Mapping[str,str] = {}`、`focus_scope=False`；保留 `owns_focus=False`。
  - 方法（默认实现）：
    ```python
    def on_key(self, e): return self.handle(e)
    def on_mouse(self, e): return self.handle(e)
    def on_paste(self, e): return self.handle(e)
    def on_resize(self, e): return None
    def on_focus(self, gained): self.focused = gained
    def on_click(self, pos): return self.click(pos.y, pos.x)
    def on_hover(self, pos): return self.hover_at(-1, -1) if pos is None else self.hover_at(pos.y, pos.x)
    def on_drag(self, pos, phase): return self.drag(pos.y, pos.x, phase)
    def on_action(self, name): return self.activate() if name == "activate" else False
    def take(self): return self.take_result()
    ```
  - `HasResult` Protocol（runtime_checkable）：`take() -> object | None`。
  - `Container` 类：`class Container(Widget)`，`child_at(row,col)` 默认 `None`；`__all__` 增加 `Container`、`HasResult`、`Cursor`、`MarkSet`。
  - re-export `Cursor`/`MarkSet`：`from .cursor import Cursor`、`from .mark import MarkSet`（避免重复实现）。
- 测试：
  - 旧式子类覆盖 `handle/click/hover_at/drag/activate/take_result`，默认 hooks 正确转发（Pos/None/phase）；
  - `on_focus(True/False)` 设置 focused；
  - `on_action("activate")` 调 activate；未知 action False；
  - `take()` 委托 take_result（None 与具体值）；
  - 能力属性默认值；`keymap` 默认空；`focus_scope`/`owns_focus` 默认 False；
  - `Container` 实例的 `child_at` 默认 None。
- 只允许改：`widgets/base.py`、`tests/widgets/test_base.py`。
- 验证：`uv run pytest -q tests/widgets/test_base.py`。

### T3 收口

- `widgets/__init__.py`/`kernel/__init__.py` 是否导出 `HasResult`/`Container`：本波只在 `widgets.base` 公开；根 facade 不动（W5 收敛）。
- `tools/api.py --update`（新方法/类会改变 `motui.widgets` 的公开面？base 不在 `widgets.__all__`，但 `Widget` 从根导出，类签名不变；以 `--update` 实际结果为准）。
- 全量验证：旧用例、golden、semantic、hash 不变；`grep` 确认没有组件被修改（`git diff --name-only` 只允许 base/test/api）。
- 只允许改：`tests/widgets/test_base.py`、`tools/api-2.0.txt`。
- 验证：全量验收。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. 57 byte golden、57 semantic、hash `e7ca544b…` 不变。
3. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
4. `walk()` 前序/去重/parent 正确；`touch()` 向上冒泡；hooks 默认转发旧动词；`take()` 委托。
5. `grep -rn "def handle(" src/motui` 仍是 22（本波不迁移组件）；`isinstance` 数量不变。
6. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth --quick` 全绿。

## 禁触清单

`src/motui/**` 除 `widgets/base.py`；`tests/**` 除 `tests/widgets/test_base.py`；`tools/**` 除 `api-2.0.txt`；`pyproject.toml`、`uv.lock`、`README.md`、`docs/**`、`CHANGELOG.md`、`tests/golden/**`。

## 交接包

最后 commit 写 `handoff/W3a-base.md`：A 节给 Widget 树/hooks/能力/touch/take 的实际签名、门禁；B 节给 `__setattr__` 规则、children/parent 处理、re-export、W3b 迁移顺序与坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W2.6b 事实）/ 探索审计 / 未决问题。

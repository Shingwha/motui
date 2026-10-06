# Spec interaction-model · 激活动词唯一（波次 W3）
> 分支 `im3-activate`；前置：**W2 已合并**；深读：`00-overview.md`（宪法第 2 条、决策 D2/D3）、
> `ref/audit-interaction.md`。
> **最高约束：`activate()` 只有一个含义——"执行光标下的那件事"。** 任何"设值"语义不许叫 activate。

## 目标

`Activable.activate() -> bool` 成为选择族（`Select` / `Autocomplete` / `Confirm` / `Tree`）的唯一激活动词；
`Select` 收编 `chosen` 契约（读一次清一次），`SlashPalette` 退化为"键路由 + value 映射"；
`Tree.toggle()` 同波删除（`Tabs.activate(index)` 已在 W2 改名为 `select(index)`）。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| 三套"选择"语义各写各的 | `widgets/choice.py` 的 `Select.selected`（纯读）；`widgets/tree.py` 的 `Tree.toggle()`；`chat/slash.py` 的 `SlashPalette.handle("enter")`（自己从 `_auto.selected.value` 取值写 `chosen`） |
| 就绪的协议先例 | `core/block.py` 的 `Clickable`（`runtime_checkable` Protocol，与 `Activable` 同堂） |
| Tabs 已改名（W2） | `widgets/tabs.py` 的 `select(index)`；**Tabs 不是 Activable**——它没有"光标指着的东西"，选中就是它的状态 |
| 命名表 | `docs/DESIGN.md` 的 "List movement / activation" 行、`docs/COMPONENTS.md` 的交互表 |

## 工单（按序执行，每项一个 commit）

### T1 协议 + 菜单族 `chosen` / `activate`

- `core/block.py`：新增 `Activable` 协议（`@runtime_checkable`，与 `Clickable` 并列）：
  `def activate(self) -> bool`。docstring 定义边界：**只属于"光标指着一个东西、回车就是拿走它"
  的组件**；字段、tab 条、表格容器不实现；返回是否真的拿到了东西（空表 → False）。
- `widgets/choice.py`：
  - `Select.__slots__` 加 `chosen`；构造时 `self.chosen: Option | None = None`；
  - `Select.activate() -> bool`：`self.chosen = self.selected; return self.chosen is not None`；
  - **清理规则与 `SlashPalette` 现行契约一字不差**（这是把 palette 的私有规则上收成家族契约）：
    `move()` 与 `set_query()` 清空 `chosen`；宿主读一次后自己置 None；
  - docstring 写明宿主用法（`component.activate()` 后读 `chosen`）；
  - `Confirm` / `Autocomplete` 继承即得（`Confirm` 的 chosen 是 `Option("Yes", True)` / `Option("No", False)`）。
- `widgets/tree.py`：`toggle()` → **`activate()`**（同一实现体改名；docstring 保留"叶子无可展开 → False"，
  并补一句它是 `Activable`：展开/折叠就是这棵树的主操作）。

### T2 `SlashPalette` 退化

- `chat/slash.py`：
  - `handle("enter")`：`self._auto.activate()` → 从 `self._auto.chosen` 取 Option →
    `self.chosen = None if option is None else option.value` → `self._auto.chosen = None` → `close()`；
  - `open()` 里重置内核的 `chosen`（若已由 `set_query("")` 覆盖则只补注释）；
  - **公开契约零变化**：`SlashPalette.chosen: str | None`、`is_open`、`handle` 的消费集合、
    `render` 关闭时零行——这三点在测试里逐条保持。
- 验证：`tests/test_chat_slash.py` 全绿**且不需要改断言**（这是"委托是等价改造"的证据）。
  若必须改断言，说明行为漂了，停下上报。

### T3 示例、测试与文档

- 示例：`examples/showcase/components.py`（`tree.toggle()` → `tree.activate()`）、
  `examples/showcase/session.py` 与 `page.py`（若 `Play.enter` 仍包着 toggle 调用则同改；
  W4 会重写这块，本波只做最小同步）。
- 测试：
  - `tests/test_widgets_basics.py`：`tree.toggle()` → `activate()`（逐处，含叶子/空树用例）；
  - `tests/test_widgets_choice.py`：新增 `Select.activate`/`chosen` 用例——
    空表 False、读一次清一次、`move` 清空、`set_query` 清空（Autocomplete 过滤后 activate 拿到的是命中项、
    而不是全集项）、Confirm 的 value 是 `True`/`False`、与 `Clickable` 的关系（`isinstance(Select(...), Activable)`）。
- 文档：
  - `docs/COMPONENTS.md`：交互表——删 `toggle()` 行与 `activate(index)` 行，新增
    `activate() -> bool`（`Select` / `Confirm` / `Autocomplete` / `Tree`）与 `select(index) -> bool`（`Tabs`）两行；
    `Tree` 组件行与 `Select`/`Confirm` 组件行同步（写 `chosen` 契约）；
  - `docs/DESIGN.md`：命名表 "List movement / activation" 行改为 `move(delta)` / `activate()` / `select(index)`；
    "Palette selection" 行改为"选择族在 `activate()` 后把当前项写进 `chosen`"；
  - `widgets/__init__.py` 的模块 docstring（"move(delta) 或 activate(index)" 措辞）；
  - `README.md` 组件表若提到 `toggle`/`activate(index)` 同步。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` → 全绿（总数 = 基线 + 本波新增；`test_chat_slash.py` 断言零改动）。
2. `uv run python examples/demo.py < /dev/null; echo exit=$?` → exit 0；
   `grep -c 'picked option' <dump>` 证明展示台的 Enter 激活路径仍走通。
3. `uv run python tools/framebench.py` → render-hash 不变。
4. 全仓 grep 验证旧名零残留：`grep -rn "toggle()" src/ tests/ examples/ docs/ README.md` 只应剩下
   `TreeNode.expanded` 的**文档措辞**（若有），不得再有方法调用；`grep -rn "activate(index)"` 零命中。
5. 真机：`/lists` 页 Enter 弹 toast；`/structure` 页 Enter 折叠/展开 Tree。

## 禁触清单

- `widgets/tabs.py`（W2 已完成改名；本波不回头动它）。
- `widgets/{table,textbuf,field,input,editor}.py`（W5/W6）。
- `core/events.py`、`keys/`、`app.py`（事件与驱动不动）。
- `specs/`。

## 最终报告格式

工单状态表 / commit 清单 / 自测真实结论 / "委托是等价改造"的证据（`test_chat_slash.py` 零改动 diff）
/ 偏差与取舍 / 未决问题。

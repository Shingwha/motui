# Spec interaction-model · 焦点层（波次 W4）
> 分支 `im4-focus`；前置：**W3 已合并**；深读：`00-overview.md`（宪法第 3 条、决策 D4/D8）、
> `ref/audit-interaction.md`。
> **最高约束：焦点是"层"，不是组件的责任。** 组件只多一个 `focused: bool` 与一条失焦渲染规则；
> 谁在被聚焦、怎么循环、事件发给谁，全在 `focus.py` 一处。
>
> ✅ **2026-10-07 已合并** @ `im4-focus`（终态 `915 passed, 1 skipped`；`Play` 已删，`tab`/`c-o` 键位已迁移；
> 键路由顺序按实测修正为"composer 为空时才交给环"，理由见该波 commit 与报告）。

## 目标

新增 app 层 `FocusRing`：注册目标、循环焦点、把键盘/点击转发给聚焦者、点谁聚焦谁
（再点一次 = 激活）。列表族获得 `focused` 与"失焦 = 光标样式 merge `theme.dim`"的渲染规则；
展示台的私有 `Play` 适配器（`examples/showcase/page.py`）**同波删除**，换成焦点环——
这是"焦点层缺位"的直接证据，删除即验收。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| 展示台的残缺替身 | `examples/showcase/page.py` 的 `Play(target, move, enter, hint)`：每页只能有一个可玩目标；`session.py` 的 `_play_key` 把 `↑↓/enter` 硬绑给它 |
| 字段族已有 `focused` | `widgets/field.py` 的 `_TextField.focused`（画不画块光标）；`Input`/`Editor` 构造参数 |
| 列表族没有 | `Select` / `Tree` / `Tabs` 渲染光标/激活样式时不看任何焦点标志 |
| 层先例 | `gesture.py`（选择策略层，import app）——`focus.py` 与它平级 |
| 协议先例 | `core/block.py` 的 `Clickable`（W2 起是 `click(row, col)`）；`mocode_tui.core` facade 已导出它（`core/__init__.py:61,109`）；`README.md:189,229` 有它的条目 |
| 键位现状 | `tab` = 窗格焦点（`examples/showcase/session.py` 的 `_cycle_focus`）；composer 的 keymap 不绑 `c-o`（`keys/keymap.py` 三张表） |

## 工单（按序执行，每项一个 commit）

### T1 `Focusable` 协议 + `focus.py`

- `core/block.py`：新增 `Focusable` 协议（`@runtime_checkable`）：`focused: bool`（可读写）。
  docstring：一个组件声明"我能被聚焦"的最低面——焦点环设置它，组件只按它渲染。
- 新文件 `src/mocode_tui/focus.py`（层：与 `gesture.py` 平级；import `core` + `app`）：

```python
class FocusRing:
    """The focus tier: who is focused, how it cycles, where events go."""

    def __init__(self, targets: Sequence[Component] = (), *, wrap: bool = True) -> None:
        # 构造即校验：每个目标都必须满足 Focusable，否则 TypeError（编程错误，早爆）
        # 非空环构造后 focus 落在 targets[0]（页面一打开就能玩）；空环 focused = None
    @property
    def targets(self) -> tuple[Component, ...]: ...
    @property
    def focused(self) -> Component | None: ...
    def focus(self, target: Component) -> bool: ...      # 未注册目标 → False，原焦点不动
    def focus_next(self, delta: int = 1) -> bool: ...    # wrap 循环；空环 False
    def handle(self, event: Key | Paste) -> bool: ...
    def click(self, hit: Hit) -> bool: ...
```

- **`handle` 路由表**（写进类 docstring，逐条落到测试）：
  1. 焦点为空 → False；
  2. 聚焦者若有 `handle`，**先给它**（字段/控制器消费自己的键；`TextBuffer.handle` 会吃掉可打印字符、
     方向键、退格……这是既有契约）；
  3. 未被消费时，仅认 `Key`：`up`/`left` → `move(-1)`；`down`/`right` → `move(+1)`；
     目标没有 `move` 时分别退到 `move_up()`/`move_left()` 与 `move_down()`/`move_right()`；
     `enter` → `activate()`（目标不是 `Activable` → False）；
  4. 其余事件 → False（宿主继续自己的路由：提交、面板、退出……）。
- **`click` 策略**（一次点击 = 命中 + 聚焦 + 可能的激活）：
  1. `component = hit.block.component`；若它满足 `Clickable` → `component.click(hit.row, hit.col)`
     （**任何可点组件都派发**，不限于环内目标）；
  2. 若 component 在环内且**不是**当前焦点 → `focus(component)`（首点只聚焦）；
  3. 若 component 在环内且**已经是**当前焦点 → `activate()`（二点即激活，标准桌面语义）；
  4. 返回"是否有组件消费了这次点击"（宿主据此决定要不要重绘/toast）。
- **不实现的东西**（写进 docstring 的"边界"）：不做 hover、不做 Tab 之外的热键、不认识鼠标拖动
  （拖动是 `SelectionGesture` 的）、不接管窗口/窗格（窗格是 `Frame` 的事）。

### T2 列表族 `focused` 与失焦渲染

- `Select` / `Tree` / `Tabs`：加 `focused: bool = True`（构造参数 + `__slots__`，默认 True
  → **现行渲染字节零变化**）；构造时按既有章程解析一个 `_dim`（explicit > theme `dim` > 默认）。
- 渲染规则（三处同一句话）：`focused` 为假时，光标行的样式 = 原样式 `.merge(self._dim)`。
  仅此一条：`Select` 的 marker+label（描述列保持 dim 不变）、`Tree` 的 cursor_style、`Tabs` 的
  `active_style`。**不加新 theme 字段**（`dim` 是纯属性样式，merge 保住色相只降权重）。
- `Input` / `Editor`：已满足 `Focusable`（`focused` 控制块光标），零改动；docstring 补一句
  "焦点环设置的也是这个标志"。
- 验证：`tests/test_widgets_choice.py` / `tests/test_widgets_basics.py` 加用例——
  `focused=True` 的渲染与旧字节逐段相等（回归），`focused=False` 时目标段样式 == 原样式 `.merge(dim)`。

### T3 展示台换轴（删除 `Play`）

- `examples/showcase/page.py`：删 `Play`；`PageBody` 改 `focus: FocusRing | None = None`，
  `hint: str = ""` 保留（页面自己写"这一页能玩什么"）。
- `examples/showcase/session.py`：
  - 删 `_play_key` 与 `_play_click` 里的 target/toggle 特例；事件路由插一行
    `if self.body and self.body.focus and self.body.focus.handle(event): ... continue`（在 palette 与 editor
    **之后**、宿主的 tab/enter/c-c 分支**之前**——即"编辑器/面板没要的键才轮到焦点环"）；
    鼠标事件在 chrome/overlay 未消费时调用 `self.body.focus.click(hit)`；
  - **Tab 归焦点环**（`ring.focus_next()`），窗格焦点改绑 `c-o`（`_cycle_focus`）；
  - `_banner_labels`：hint 文案改为同时说清 `tab` 焦点、`c-o` 窗格、`↑↓/enter` 玩法。
- 页面接线（`components.py`）：
  - `structure`：`FocusRing([tabs, tree])`（顺序即 Tab 顺序）；
  - `lists`：`FocusRing([long_menu, danger_confirm, plain_confirm, filtered])`；
  - `fields`：`FocusRing([editor, windowed])`；
  - 其余页面 `focus=None`（hint 相应改写，不再提 ↑↓ 玩法）。
- `examples/showcase/script.py`：加 `tab`（换焦点）→ `down` → `enter`（激活新聚焦者）的回放；
  原先靠 `tab` 切窗格的两处改成 `c-o`。
- 文档：`README.md` 的 demo 段（键位说明：tab 焦点 / c-o 窗格）、`examples/demo.py` 的模块 docstring。

### T4 测试与文档（库面）

- 新 `tests/test_focus.py`：空环；构造即聚焦首目标；`focus` 未知目标 False 且焦点不动；
  两侧 `focused` 标志翻转；`focus_next` 循环（wrap=True/False）；`handle` 路由表逐条
  （含"目标无 move → move_up/move_down"、"enter 非 Activable → False"、"字段 handle 优先"）；
  `click` 四步策略（非目标可点组件也派发；首点聚焦不激活；二点激活；返回值）；
  非 `Focusable` 目标 → `TypeError`。
- 导出：`FocusRing` 进根 `__init__.py`（`__all__` + curated 面）；`Activable`/`Focusable` 进
  `mocode_tui.core`（与 `Clickable` 同面，`core/__init__.py` 的 import 与 `__all__`）。
- 文档：`docs/COMPONENTS.md` 新增"焦点层"小节（`FocusRing` 的路由表与 click 策略，
  与 `SelectionGesture` 并列介绍）；`docs/DESIGN.md` 的层图/模块表加 `focus.py`；
  `README.md` 的模块表（`app.py gesture.py chrome.py` 那一行附近）与组件协议段同步。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` → 全绿（含新 `test_focus.py`）。
2. `uv run python examples/demo.py < /dev/null; echo exit=$?` → exit 0（脚本含 tab/c-o/enter 回放）。
3. `uv run python tools/framebench.py` → render-hash **不变**（`focused=True` 是默认，渲染零变化；
   若变了，说明失焦规则误伤了默认路径，停下上报）。
4. 全仓 grep：`Play` 在 `examples/showcase/` 零命中；`_play_key` / `_play_click` 零命中。
5. 真机：`/structure` 页 `tab` 在 Tabs ↔ Tree 间切焦点（失焦者光标变暗），`↑↓/enter` 作用于聚焦者，
   点 Tabs 第一个 tab → 聚焦；再点 → 激活（`activate` 对该组件不适用 → 无副作用，仅聚焦）；
   点 Tree 行 → 聚焦 + 折叠；`c-o` 在 `/split` 后切窗格。

## 禁触清单

- `core/events.py`、`keys/`、`chrome.py`、`gesture.py`（事件、滚轮/拖动策略不动）。
- `widgets/{table,textbuf,field,input,editor}.py` 的实现（仅 `field.py` 的 docstring 可补一句）。
- `chat/`（composer 的编辑器**不进环**：提交手势仍由宿主拥有，本波明确不动）。
- `specs/`。

## 最终报告格式

工单状态表 / commit 清单 / 自测真实结论 / 行为变化 A/B（默认渲染不变、失焦样式的新字节）/
`Play` 删除前后的展示台 diff 规模 / 偏差与取舍（尤其 Tab 与窗格键位的迁移） / 未决问题。

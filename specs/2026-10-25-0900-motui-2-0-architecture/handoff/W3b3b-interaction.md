# W3b3b 交接 · 交互层收口（协议删除、hooks 全量、take 统一）

> 分支 `2.0/w3b3b-interaction`；起点 `202fc36`。结论：T1–T5 完成；**1531 passed**（1529 基线 + 2 个 T4 新增）；57 byte / 57 semantic / hash `e7ca544b…` 全不变；demo 70 / 4059 行，exit 0。除 demo 调用点外，禁触清单零 diff（见 B5）。

## A. 交付面与门禁

### 协议与别名删除
- `kernel/document.py`：删除 `Clickable/Activable/Focusable/Hoverable/Container/Controller/Resultful`；保留 `Component`/`Revisioned`。`__all__` 现为 `Component, Document, Fill, Placement, Revisioned, Section, Sizing, descend, descend_chain`（9 名）。`descend_chain` 的能力探测改为 `getattr(component, "child_at", None)`。
- `widgets/base.py`：删除 `handle/click/hover_at/drag/activate/take_result` 与 `owns_focus`；`on_key/on_mouse/on_paste/on_click/on_hover/on_drag/on_action` 默认 `False`，`take` 默认 `None`，`on_focus` 仍翻转 `focused`。`Container` 基类保留（坐标门 `child_at`，不是能力协议）。
- 全仓组件删除旧动词（含 `handle = on_key`、`take_result = take` 别名）；唯一 `def handle(` 在 `widgets/textbuf.py`（编辑引擎，非 widget）。

### 能力表（全部属性）
| 属性 | 判定处 | 设置者 |
|---|---|---|
| `focusable` | `focus.focus_targets` | Button/Checkbox/Link、菜单族、Tree/Table/List/Nav/Tabs、TextField、ScrollPanel、Form/ComboBox |
| `clickable` | `FocusManager.click`、`Pointer._dispatch_click` | 动作/数据组件 + Markdown + ScrollPanel |
| `hoverable` | `Pointer._set_hovered` 决定是否调 `on_hover` | 所有画 hover 带的组件 + Markdown |
| `activatable` | enter 回退、click 二次激活 | 菜单族/Table/Tree/Collapsible/Slider/MenuBar |
| `focus_scope` | `focus.focus_targets` | Form、Dialog、ComboBox |

### take 路径
- 每个有结果的组件只有 `take() -> object | None`；`bool | None` 组件用 `is not None` 判别（Button/Checkbox/Link/Collapsible）。
- `Modal.take`/`CommandPalette.take`/`Dialog.take`/`Form.take` 一次性读取；`Modal._collect` 仍优先私有 `_take_decision()`（区分 `None` 决策与无决策）。
- `Pointer._dispatch_click` 使用 `clickable` + `on_click(Pos)`；无能力协议探测。

### 门禁（本 worktree，Python 3.12.14 / uv 0.12.21）
- `pytest -q -p no:cacheprovider`：**1531 passed**（1529 基线 + 2 新增）；golden **57**；semantic **57**；hash `e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da`
- `python -m motui < /dev/null`：exit 0，**70** 行；`--pages`：exit 0，**4059** 行
- ruff All checks passed；pyright 0；lint-imports 4 kept；`api --update/--check` **181 names，零内容变化**；`growth --quick` OK
- `def handle(` in widgets：仅 `textbuf.py`；capability isinstance 0；src `owns_focus` 0；`_walk` 0；`_CHILD_ATTRS/_looks_interactive/set_focus_targets` 0
- src `take_result` 仍 12 处，全部是 demo 文档/`api_line` 字符串（无执行代码），见 B6

### 复跑命令
```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/semantic.py --check
uv run python tools/framebench.py
uv run ruff check . && uv run pyright && uv run lint-imports
uv run python tools/api.py --check
uv run python tools/growth.py --quick
```

## B. 实现细节 / 坑

1. **Pointer 的 hover cue**：`hover` 标志对任何带该属性的组件翻转（含 `hoverable=False` 的 ScrollPanel），因此拖动后的 motion 仍返回 `True`（既有断言不变）；`on_hover(pos|None)` 只发给 `hoverable=True` 的组件。click 只认 `clickable` + `on_click(Pos)`。
2. **拖拽派发**：`App._drag_press/_drag_event` 用 `type(component).on_drag is not Widget.on_drag` 找目标，再发 `on_drag(Pos(x=col, y=row), phase)`；ScrollPanel 的 bar 列逻辑不变。
3. **Gesture**：选择手势本身不发 widget drag；私有 `_walk` 更名为 `_advance_head`（只改名）。`copy_on_select` 仍走 `Selection` + `extract`。
4. **Modal/Palette**：`Modal._route` 按事件类型调 `on_key`/`on_paste`（不再回退 `handle`）；面板点击改 `on_click(Pos)`；`_arm/_collect` 改读 `take`。CommandPalette 内部 panel 拆成 `on_key`/`on_paste`，控制器 `handle` 保留。
5. **demo 例外（唯一越界）**：删除 `take_result`/`handle` 后 demo 无法构建。为保住“57 golden 字节不变”，只迁移调用点，不改任何 `api_line`/输出文案：`demo/{session,topics/components_actions,components_data,components_forms,topics/styling}.py` 共 5 文件（`take_result()→take()`、`activate()→on_action("activate")`、`combo.handle→on_key/on_paste`、`hover_at→on_hover(Pos)`）。若要求 demo 零 diff，只能恢复 shim，与本波门禁不可兼得。
6. **剩余 `take_result` 12 处**：`demo/model.py`、`demo/stage.py` 文档 2 处 + 10 个 `api_line`/`summary` 字符串。后者直接进入 golden/semantic，改动即破坏“字节不变”，留给 W5 的 demo 文案收敛。
7. **isinstance 总数 125**（基线 144，本波减 19；能力探测 0）：事件 49（KeyEvent 25 / MouseEvent 15 / PasteEvent 8 / FocusEvent 1）、结构/领域值 46（Widget/Revisioned/Scrollable/Option/Section 等）、值/容器 29、注释 1。
8. **scope**：`focus_targets` 只读 `focus_scope`；Form/Dialog/ComboBox 三家设置。`Form._sync_focus`/`on_focus` 改读 `focusable`，只镜像到可聚焦字段。
9. **ScrollPanel 子树**：`__init__` 在 `super().__init__` 后 `self.children=[child]`；`child` 属性与 `child_at` 不变。App 的 theme/focus/resize 现在能进入内容；byte golden 未变（新增 2 个 T4 用例覆盖）。
10. **测试迁移**：`tests/**` 全量改为 `on_click(Pos)`/`on_hover(Pos|None)`/`on_key`/`on_paste`/`on_mouse`/`on_action("activate")`/`take()`；删除了“别名等价”断言，改为能力/行为断言；新增 `test_the_untyped_verbs_are_gone_from_the_base`。

## C. 位置与 commit

- 源码：`kernel/document.py`；`widgets/{base,action,choice,collapsible,dialog,form,combobox,indicators,list,markdown/*,menubar,navlist,scroll,strip,table,tabs,text,textfield,tree,__init__}.py`；`app/{application,pointer,gesture,focus,modal,find,command_palette,driver}.py`
- demo（例外）：`demo/{session.py,topics/{components_actions,components_data,components_forms,styling}.py}`
- 测试：`tests/app/{test_app,test_focus,test_pointer,test_modal,test_command_palette,test_gesture}.py`、`tests/widgets/**`、`tests/kernel/{test_text,test_selection}.py`
- commit：
  - `3bc2c81` widgets: capability flags replace the interaction protocols（T1）
  - `77eb479` app: pointer and gesture dispatch typed hooks with Pos（T2）
  - `863c8f8` app: modal, find and palette route typed hooks and take results（T3）
  - `781ba39` widgets: scroll panels mount their child and forms scope focus（T4）
  - 本文件（T5 收口；`tools/api-2.0.txt` 无内容变化）

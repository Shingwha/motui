# W3b1 · 控件/编辑/容器族迁移到树与 hooks

> 分支 `2.0/w3b1-controls`；前置：W3a 已合并（`b5e1997`）；写入范围：`src/motui/widgets/{text,decor,layout,action,collapsible,combobox,dialog,form,indicators,textfield,autocomplete}.py`、对应 `tests/widgets/*`、`tools/api-2.0.txt`
> 权威：`ref/source/03-interaction.md` §3–9、`10-waves/W3-tree-interaction.md` §4.1–4.6

## 目标

把控件、编辑与布局/装饰容器迁到 W3a 基座，**行为 1:1、字节不变**：

1. 容器接入树：`Row`/`Column`/`Padding`/`Panel`/`Dialog`/`Form`/`Collapsible` 设置 `children`（parent 自动），`walk()` 覆盖；
2. 能力属性：`focusable/clickable/hoverable/activatable` 按组件语义设置；
3. hooks：`on_key/on_mouse/on_paste/on_click(Pos)/on_hover(Pos|None)/on_drag(Pos,phase)/on_action(name)/on_focus`；旧 `handle/click/hover_at/drag/activate/take_result` 可保留薄别名到 W3b3；
4. `Form`：`focus_scope=True`，字段路由内部化；`Dialog`：`focus_scope=True`（自管按钮键）；
5. `Text` 从 `Themed` 迁到 `Widget`，保留 hover span/action；
6. `take()` 落地（`take_result` 别名保留）；
7. 现有测试与 57 byte/semantic golden 不变。

**本波结束：1422+ 用例绿；golden/hash 不变；这些文件无 `def handle(`（用 `on_key` + `handle = on_key` 别名）；能力属性正确；Form/Dialog 路由测试通过。**

## 前置上下文

- 必读：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W3a-base.md` → 本工单。
- 基线：`uv sync --locked`；`pytest`（1422 passed）；`golden --check`（57）；`semantic --check`（57）；hash `e7ca544b…`。
- 迁移模式：
  - 新 hook 是行为本体；旧动词用薄别名（`handle = on_key` 或 `def handle(self,e): return self.on_key(e)`；`click`/`hover_at`/`drag`/`activate` 同理）暂时保持 App 兼容。W3b3 删除别名。
  - `on_click(pos)` 用 `pos.y, pos.x` 调原 `click` 逻辑；`on_hover(None)` 表示离开。
  - `on_action(name)` 调原 `activate()`/`toggle()` 等；返回 bool。
  - keymap 路由：`key = event.key`; `action = {**type(self).keymap, **self.__dict__.get("keymap", {})}.get(key)`；有 action 则 `on_action(action)`；否则 `on_key` 继续。
  - `take()` 返回原 `take_result()` 的值；`take_result` 别名保留。
- 已知坑：
  - `Row`/`Column` 当前不是 Widget；改为 `Container` 后调用 `super().__init__()`，从 `__slots__` 删除 `children`（基类已有）；`self.children = list(children)` 设置 parent。
  - `Spacer` 可保持轻量，但为 touch/walk 统一建议继承 `Widget`（无 children）；`isinstance(Spacer, Container)` 仍为 False。
  - `Text(Themed)` → `Text(Widget)`：`self.pick(...)` 改为 `self.group("surfaces").hover`；构造签名 `(text, *, style=None, theme=None)` 保持；`styles` 可作为可选参数加。
  - `Panel`/`Collapsible`/`Dialog` 的 `__slots__` 不要重复 `children`；`child` 属性和 `children` 列表要保持一致（例如 Panel.children=[child]）。
  - `Form` 当前 `owns_focus=True`；改为 `focus_scope=True`（可同时保留 `owns_focus` 类属性直到 W3b3）。字段列表来自构造参数；`on_key` 路由到当前 `self.focused` 字段。
  - `Dialog` 当前 `handle` 处理按钮键；迁 `on_key`，`focus_scope=True`；`children` 包含 body + 每个 Button。
  - Input/Editor 的 `handle` 逻辑很大；把 `_TextField.handle` 改名为 `on_key`（保留 `handle = on_key`），`on_paste` 处理 PasteEvent（含 Input 的换行折叠），`on_mouse` 处理点击/滚轮（若原来有）。`TextBuffer.handle` 不动。
  - `on_resize` 不需要实现（默认 no-op）。
  - 不要改渲染算法；`children`/capabilities 不影响 Surface。
  - 测试里 `isinstance(widget, Clickable)` 之类的旧断言本波不改（W3b3 删协议）；只加新 hook/属性测试。
- 不改数据视图（W3b2）、不改 app/focus（W3b3）。

## 工单（每族一个 commit）

### T1 容器与 Text
- `text.py`：`Text(Widget)`；`children=[]`；`clickable=True`、`hoverable=True`；`on_click(Pos)`/`on_hover(Pos|None)` 调原逻辑；`on_action` 无。
- `decor.py`：`Divider(Widget)`（无 children）；`Panel` → `children=[child]`（保持 `child` 属性）；`on_click` 无。
- `layout.py`：`Row(Container)`/`Column(Container)`/`Padding(Widget)`/`Spacer(Widget)`；`super().__init__()`；`self.children=...`；删除重复 slot；`child_at`/memo/revision 不变。
- 测试：Text 的新测试放 **新建** `tests/widgets/test_text_widget.py`（不要动 `test_rows.py`，它归 W3b2）；`test_containers.py` 加 `walk()`/parent/`children` 断言；现有渲染断言不变。
- 验证：`uv run pytest -q tests/widgets/test_text_widget.py tests/widgets/test_containers.py`。

### T2 动作族
- `action.py`：Button/Checkbox/Link：
  - `clickable=True`（Link 也）、`activatable=True`、`focusable=True`；
  - `on_click(Pos)` 调原 click；`on_action("activate")` 调原 activate；`on_hover` 若有 hover 逻辑则迁；
  - `take()` 返回原 `take_result()`；`take_result` 别名。
- 测试 `test_action.py`：`on_action`/`on_click`/`take` 的 None/False 路径；旧 click 仍工作。
- 验证：`uv run pytest -q tests/widgets/test_action.py`。

### T3 折叠/表单/对话框
- `collapsible.py`：`children=[body]`；`focusable=True`、`activatable=True`；`on_action("toggle")`；`take`。
- `form.py`：`focus_scope=True`；`children=[field.widget?]`（按现有字段结构）；`on_key` 路由到 `self.focused`；`on_focus` 传播；`take` 若原有无。
- `dialog.py`：`focus_scope=True`；`children=[body, *buttons]`；`on_key` 处理按钮键；`on_click` 点击按钮。
- 测试 `test_form.py`、`test_dialog.py`、`test_containers.py`：多字段路由、按钮 key/click、walk 覆盖。
- 验证：`uv run pytest -q tests/widgets/test_form.py tests/widgets/test_dialog.py tests/widgets/test_containers.py`。

### T4 编辑族
- `textfield.py`：
  - `_TextField.handle` → `on_key`；`on_paste`（Input 折叠换行）；`on_mouse`（若原 handle 处理鼠标）；
  - `handle = on_key` 别名；
  - `focusable=True`、`clickable=True`（编辑器可点击定位）；
  - `on_action(name)` 调原 keymap action 方法；
  - `take()` 返回原结果（若字段有）。
- `tests/widgets/test_editing.py`：`on_key` 与旧 `handle` 等价；`on_paste` 折叠；`on_action("move_left")` 等；walk/abilities。
- 验证：`uv run pytest -q tests/widgets/test_editing.py`。

### T5 ComboBox / Autocomplete / Indicators
- `combobox.py`：`children=[input, list]`；`focusable/clickable/activatable`；`on_key` 路由；`on_click`；`on_action`；`take`。
- `autocomplete.py`：继承 Select（W3b2 也在改）；本波只加 `focusable/clickable/activatable` 与 `on_key` 转发（若已由 Select 提供则不动）；避免与 W3b2 冲突：**不改 `choice.py`**。
- `indicators.py`：Slider `focusable/clickable/activatable`；`on_key`/`on_click`/`on_action`；ProgressBar/Spinner 保持无交互。
- 测试 `test_combobox.py`、`test_autocomplete.py`、`test_indicators.py`。
- 验证：`uv run pytest -q tests/widgets/test_combobox.py tests/widgets/test_autocomplete.py tests/widgets/test_indicators.py`。

### T6 收口
- `grep -rn "def handle(" src/motui/widgets/{text,decor,layout,action,collapsible,combobox,dialog,form,indicators,textfield,autocomplete}.py` → 0（用别名）。
- `grep "take_result"` 只允许别名定义。
- `tools/api.py --update`；全量门禁。
- 只允许改：`tools/api-2.0.txt`、handoff。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. 57 byte golden、57 semantic、hash `e7ca544b…` 不变。
3. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
4. 上述文件无 `def handle(`；`walk()` 覆盖容器；Form/Dialog 路由与旧行为一致。
5. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth --quick` 全绿。
6. 旧测试只允许为 `walk/parent/hooks` 增断言，不允许降低原断言。

## 禁触清单

`kernel/**`、`terminal/**`、`app/**`、`widgets/{list,tree,table,choice,navlist,tabs,menubar,rows,strip,scroll,canvas,base,markdown/**}.py`、`demo/**`、`tests/golden/**`、`tools/{golden,framebench,semantic}.py`、`README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`。

## 交接包

最后 commit 写 `handoff/W3b1-controls.md`：A 节给迁移清单/能力表/签名/门禁；B 节给别名策略、Form/Dialog 路由、Text 基类切换、W3b3 要删的别名/协议清单、坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W3a 事实）/ 探索审计 / 未决问题。

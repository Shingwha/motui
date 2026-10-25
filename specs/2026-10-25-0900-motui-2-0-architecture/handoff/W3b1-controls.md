# W3b1 交接 · 控件/编辑/容器族接入树与 hooks

> 分支 `2.0/w3b1-controls`；起点 `609eb67`。结论：T1–T6 完成；**1471 passed**（1422 + 49 新）；
> 57 byte / 57 semantic / hash `e7ca544b…2986da` 全不变；demo 70 / 4059 行，exit 0。

## A. 交付面与门禁

### 迁移清单

- `text.py`：`Text(Themed)` → `Text(Widget)`；`clickable/hoverable`；`on_click(Pos)`/`on_hover(Pos|None)`
  是本体，`click`/`hover_at` 薄别名；`take()` 本体，`take_result` 别名；`children=[]`。
- `decor.py`：`Divider` 无子；`Panel.children=[child]`（parent 自动），`child` 属性与 duck `child_at` 不变。
- `layout.py`：`Row/Column → Container`，`__slots__` 删 `children`，`super().__init__()`；`Padding.children=[child]`；
  `Spacer(Widget)` 但非 Container。
- `action.py`：Button/Checkbox/Link 四能力全开；`on_click(Pos)` 本体 + `click` 别名；`on_action("activate")`；
  `take()` 本体 + `take_result` 别名。
- `collapsible.py`：`children=[body]`；四能力全开；`on_click(Pos)` + `click`；`on_action("toggle"/"activate")`；`take()`。
- `form.py`：`focus_scope=True`（`owns_focus` 保留）；`children=[field.component]`；`on_key(Event)` 按事件类型
  选 `on_key/on_paste/on_mouse` 再回退 `handle`；`handle=on_key`；`on_focus` 同步字段；`on_click(Pos)`；`take()`。
- `dialog.py`：`focus_scope=True`（自身仍非焦点目标）；`children=[body,*buttons]`；`on_key` + `handle=on_key`；
  `on_click(Pos)`；`take()`；`_take_button` 改调 `Button.take()`。
- `textfield.py`：`_TextField.handle → _route + on_key/on_mouse/on_paste`，`handle=on_key`；`Input.on_key`
  折叠 PasteEvent（`on_paste` 是折叠本体）；`on_action` 仅接受当前 keymap values 中的动作名；构造时 `dict(keymap)`。
- `combobox.py`：`children=[input,list]`；`focusable/clickable/activatable`；`on_key` + `handle=on_key`；
  `on_click(Pos)`；`on_action`（打开时 `activate`→`_take()`，其余转发 field）；`take()`；`_take` 用 `list.take()`。
- `autocomplete.py`：三能力；`on_key` 仅 `super().on_key(e)`（Select 提供路由即用；当前无 hook 时落到旧 handle）。
- `indicators.py`：Slider 四能力；`on_key`（left/up −1，right/down +1，enter activate）；`on_click(Pos)`；
  `on_action(activate/prev/next…)`；`take()`；ProgressBar/Spinner 保持无交互。

### 能力表（`focusable, clickable, hoverable, activatable`）

- `T,T,T,T`：Button / Checkbox / Link / Collapsible / Slider
- `T,T,F,T`：ComboBox / Autocomplete；`T,T,T,F`：Input / Editor；`F,T,T,F`：Text
- 全 False：Row/Column/Padding/Panel/Spacer/Divider/ProgressBar/Spinner
- `Form` / `Dialog`：无 flags，`focus_scope=True`。比工单多出的 hoverable / Collapsible.clickable 按语义补齐。

### 门禁（本 worktree，Python 3.12.14 / uv 0.12.21）

- `pytest -q -p no:cacheprovider`：**1471 passed**
- `golden --check`：57；`semantic --check`：57；`framebench`：`e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da`
- `python -m motui < /dev/null`：exit 0，70 行；`--pages`：exit 0，4059 行
- `ruff` All checks passed；`pyright` 0 errors；`lint-imports` 4 kept；`api --check` 181 names（`--update` 零 diff）；
  `growth --quick` OK
- 11 文件 `def handle(` = 0（`handle=on_key` 5 处）；全仓 22 → 17；`take_result` 只剩 9 个别名定义

## B. 实现细节 / W3b3 迁移提示

1. **待删别名**：5 个 `handle=on_key`；8 个 `click`；`Text.hover_at`；9 个 `take_result`；`Form.owns_focus`。
   字段的 `click` 仍是本体，W3b3 要翻成 `on_click(Pos)` 或让基类 hook 继续委托。
2. **keymap 不再写穿默认表**：`_TextField` 构造时 `dict(keymap)`（修复 `Input().keymap[...]` 污染
   `DEFAULT_INPUT_KEYMAP`）；实例 rebind 仍走 property → `_buf.keymap`。未使用类级 keymap，合并规则留 W3b3。
3. **Form 路由**：字段 hook 优先，其次 tab/down、s-tab/up、enter；`release` 不作导航（与旧实现一致）。
4. **Dialog**：`on_key` 只认 KeyEvent，`handle` 别名继续服务 `Modal`；`focused` 仍不是 Dialog 的键。
5. **Text**：`theme/styles` 改由 Widget 持有；`_hover_style` 仍在构造时解析（theme 后赋值不重绘 hover band）；
   App `_mount` 现在给 Text 赋 theme，但 `revision()` 不含 theme，字节不变。
6. **树**：`children` 赋值统一设 parent；Panel/Padding 的 `child`、Collapsible 的 `body`、Form 的 `_fields`、
   ComboBox 的 `input/list` 保留（App `_walk` 兼容）。Dialog buttons 首次进入 `App._walk`；Modal/demo 显式传
   theme，golden 不变；若宿主依赖“按钮不随 App theme 重绘”，W4 的树遍历需复核。
7. **Spacer** 是 Widget 非 Container；Row/Column 改 Container 子类对协议 `isinstance` 原本也为真，坐标行为零变化。
8. **on_focus**：旧 App 直接写 `.focused`，不调 hook，故 1:1；W3b3 切换后 Form 字段旗标才随进出焦点同步。
9. **测试**：新增 `test_text_widget.py`；其余 8 个测试文件只增断言；`test_rows.py` 未改（W3b2）。

## C. 位置与 commit

- 源码：`src/motui/widgets/{text,decor,layout,action,collapsible,combobox,dialog,form,indicators,textfield,autocomplete}.py`
- 测试：上述 8 个既有 `tests/widgets/test_*.py` + 新建 `test_text_widget.py`
- commit：
  - `0d3849f` widgets: text and layout containers join the widget tree（T1）
  - `29cd042` widgets: actions answer typed hooks, capabilities and take（T2）
  - `b3b5f41` widgets: folds, forms and dialogs route through a focus scope（T3）
  - `2ba76e0` widgets: text fields answer on_key, on_paste and on_action（T4）
  - `5d92dbe` widgets: combos, autocomplete and sliders expose typed controls（T5）
  - 本文件（T6 收口）
- 禁触清单零 diff：`git diff --name-only 609eb67` 仅 11 个源文件 + 9 个测试文件；`kernel/**`、`terminal/**`、
  `app/**`、W3b2 widgets、`demo/**`、`tests/golden/**`、`tools/{golden,framebench,semantic}.py`、
  `pyproject.toml`、`uv.lock` 未触碰；`tools/api-2.0.txt` 无内容变化（`--update` 后同 hash）。

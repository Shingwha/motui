# W4a 交接包

> 分支 `w2.1.2-w4a-foundation` / 起点 main @ `cec7bbc`（W1–W3 + spec）/ 2026-10-29

## A. 自动事实（命令与代码生成）

`git diff --stat main...HEAD`：8 files changed, 924 insertions(+), 225 deletions(-)；
`widgets/{base,action,strip}.py`、`app/focus.py`、四个契约测试文件；禁触清单零 diff。

commits：`424d376` T1 → `ddafcbf` T2 → `848d3ad` T3 → `da8ebed` T4 → `5af6abb` T5
→ 本 handoff。

公开接口（只在 `widgets.base.__all__`；未进 `motui.widgets` facade，`api.py` 仍 243）：

- `CURSOR_KEYMAP` (`base.py:53`)、`_MISSING` (`:67`)、`Keymap` (`:70`)。
- `Widget.keymap = Keymap({})` (`:173`)，`__slots__` 增 `_keymap`，`__init__` 安装
  实例副本 (`:201`)。
- `ResultWidget` (`:357`)：`_emit(value)` 写 pending + touch；`_clear_result()` 仅有
  pending 时清并 touch、返回 bool；`take()` 读一次即清。
- `ActionWidget` (`:403`)：`disabled/hint`；基类 `activate/toggle` 返回 False；
  `on_click(pos) → activate()`；`on_action` 只路由 activate/toggle，其余 False。
- `CursorWidget` (`:460`)：钩子 `_entry_count/_entry_at/_cursor_disabled/
  _cursor_wraps/_page_size`；只读 `index/selected`；`select/move/home/end`
  先 `_clear_result()` 再动 `_cursor`、变化时 touch；`on_action` 路由九个名字
  （open/close 在基类为 False）；`keymap = Keymap(CURSOR_KEYMAP)` (`:487`)。

`action.py`：Button/Link `activate()` emit True；Checkbox `activate() → toggle()`，
toggle 翻转 `checked` 后 `_emit(checked)`；三者删除本地 `_pending/take/on_action/on_click`。
`app/focus.py handle` (`:299`)：keymap → `on_key` → `enter`/`space` + `activatable` → `_activate`。

门禁（真实输出）：起点 `91 passed` / `semantic: 9 scenes match`；全量
`1737 passed in 14.13s`；`ruff check .` 全绿；8 个改动文件
`--config "exclude=[]"` 全绿；`pyright` 0；`lint-imports` 5 kept；semantic 9/9；
`api: 243 names match`；framebench `render-hash
e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da` 未变。

## B. 只存在于脑子里的东西

1. **`Widget.__init__` 的 keymap 守卫（对工单字面的偏差）**：不能直接
   `dict(type(self).keymap)`——`Input/Editor` 把 `keymap` 写成 property 指向
   `TextBuffer`，`dict(property)` 会 TypeError。实现为
   `table = type(self).keymap; dict(table) if isinstance(table, Mapping) else {}`
   (`base.py:199-202`)。W4c 若移除 textfield 的 property，可回收该分支。
2. **重复 `_keymap` slot 安全**：未迁移组件仍在自己的 `__slots__` 声明 `_keymap`，
   子类 slot 遮蔽基类 slot；基类 `__init__` 与它们的 `self._keymap = ...` 写同一处。
   W4b/W4c 删除时保留基类安装顺序即可。
3. **sentinel**：`take()` 对“合法 None”和“无 pending”都返回 None；内部区分靠
   `_clear_result()`（pending None 时为 True，take 消费后为 False）。Dialog 的取消
   仍是“调用过 take”这个信号。
4. **ActionWidget 构造不 touch**：`disabled/hint` 用 `object.__setattr__` 安装，
   fresh Button generation 为 0（旧实现 `self.disabled=` 会 touch）。Checkbox.toggle
   会 touch 两次（checked 赋值 + `_emit`），无契约依赖。
5. **旧断言改写**：`tests/widgets/test_action.py` 原断言
   `Checkbox.on_action("toggle") is False` 与新契约冲突，已拆成 activate 用例 +
   独立 toggle 委托用例（Button/Link 的 toggle 仍 False，因基类动词返回 False）。
6. **`_sync_cursor` 也在属性读时执行**：`index`/`selected` 先 sync（刷新
   count/disabled/wrap 并 clamp），保证“空集合 index==0 / selected None”；sync 不
   touch。W4b 的 `_entry_at` 必须无副作用。
7. **page 步长参数**：基类把 `_entry_count()` 传给 `_page_size`；默认返回原值即整段
   跳到边缘。有可见窗口的组件应覆盖为 `min(size, window_rows)`。
8. **space 回退顺序**：keymap 命中的 space 优先；其次 `on_key`（文本字段靠
   `event.char` 消费 `KeyEvent("space", " ")`）；最后才 enter/space 回退。
   Input/Editor 不是 activatable，空 char 的 space 也不会被抢。
9. **格式修正（行为零变化）**：strip.py 补 `Pos` import（原 F821 被
   `from __future__ import annotations` 掩盖）、I001/UP035；focus.py E501/UP037；
   test_focus.py F811 重复 `Constraints`、RUF012。均在写入范围内。
10. `CursorWidget.keymap` 是类属性 `Keymap(CURSOR_KEYMAP)`；实例 rebind 不污染类表，T5 已锁定。W4b 用 `{**CURSOR_KEYMAP, ...}` 建自己的表；Tree 覆盖 left/right。
11. `on_action("page_prev"/"page_next")` 会经 `move()` 再清一次 pending，结果与直接
    `move` 相同；不要在两个入口重复写 emit。

## C. 指针

- 基类：`src/motui/widgets/base.py:53` CURSOR_KEYMAP；`:70` Keymap；`:120` Widget；
  `:173` keymap；`:357` ResultWidget；`:403` ActionWidget；`:460` CursorWidget；
  `:537` `_sync_cursor`；`:595` on_action。
- 家族：`src/motui/widgets/action.py:77` Button；`:153` Checkbox；`:255` Link。
- 焦点：`src/motui/app/focus.py:299` `handle`。
- 测试：`tests/widgets/test_base.py:384` `_CursorProbe`；
  `tests/widgets/test_contracts.py:80/135/209/276`；`tests/app/test_focus.py:472`。
- 下一波：W4b（choice/navigation）按 `ref/interfaces.md` §1/§3/§4/§7 迁移。

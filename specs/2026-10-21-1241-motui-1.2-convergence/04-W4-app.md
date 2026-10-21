# W4 · App 默认编排 + raw read_event + demo 重写

> 占位；W3 合并后由 lead 补全「前置上下文」再派工。
> 分支建议 `refactor/1.2-app`。

## 目标

新增 `App`：默认挂焦点、指针、hover/click、选择手势、wheel 路由、toasts/tooltip，提供 `bind`/`on_key`/`on_mouse`/`on_event` 钩子和实时主题；`TUI.read_event()` 变为纯读取。把 demo `Session` 从手工 552 行循环改写成 App 用法，作为 API 易用性的验收。

## 范围

- `app/**`、`demo/**`、`testing.py`、`tests/app/**`。
- 删除 `TUI.focus_policy`、`TUI.scroll_keys`；默认策略移入 App。
- `Hit` 简化并携带祖先链，供 wheel/click 路由。
- `TUI.add` 返回 id、`get/remove` 返回 Component；`TUI.dock` 接受 Component。
- `App.theme` 实时传播给 `theme is None` 的 Widget。

## 依赖

W3 已合并。

## 验收

- 全量 pytest、golden、framebench、两个 demo 入口全绿。
- Quickstart（README 的新示例）≤ 20 行；demo `Session` ≤ 250 行。
- headless 抽验：Input+Button 的焦点/点击/提交无需手工挂 FocusManager/Pointer；换主题不重建控件。
- `rg "read_event" -n src/motui/app/driver.py` 附近无 scroll/focus 副作用。

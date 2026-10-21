# W4b 交接包
> 分支 `refactor/1.2-w4b-demo` / 起点 `4433fb1`（W4a merge `978a479` + 工单）/ 2026-10-21

## A. 自动事实（命令与代码实测）

- commits：`b1a072d`（T1）、`6fbeded`（T2）、`2f41252`（T3）、`c6c258a`（T4）、本文件所在 commit。
- `git diff --stat 4433fb1..c6c258a`：10 files, +453/-459：
  `app/{application,command_palette,modal,overlays,scrollbar}.py`、`demo/{__init__,script,session,shell}.py`、
  `tests/app/test_app.py`。
- `demo/session.py` **300 行**（目标 ≤300，stretch 250 未达）；`pytest` -> **882 passed**
  （880 起点 + 2 个 App 用例）；`golden --check` -> **57 topics match**（未重录）。
- `framebench.py` -> render hash `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`（基线相同；replay 432 ms）。
- 两个入口 sha256（重写前后逐字节相同，均 exit 0）：
  `python -m motui < /dev/null` -> `c793b32b7290a73a8c32c4e3318296689b5a723438df0b4d5a9eedb7b3fa9ea6`；
  `python -m motui --pages` -> `855f76fa4a315a311acab98553d0f015e255e48496061e6c44ec29aad642116c`。
- `rg` 上述控制器/`_round` 在 `demo/session.py` 无命中；只剩 `_after_round` picks 钩子。

## B. T1 App 扩展（`app/application.py`）

- 构造器新增并透传 `interactive`、`focus_events`、`sync`；另加 `on_selection`（工单外，见 F）。
- `mount(controller, *, dispatch=True)` / `unmount(controller) -> bool` / `controllers`：identity
  去重；dispatching 控制器在 toasts 后、wheel/mouse 前依注册序调用，`True` 即消费；
  `dispatch=False` 只登记/换肤，由宿主自己喂事件（demo 的 `Stats`）。
- 只读属性：`tooltip`、`palette`（懒创建前 `None`）、`find_bar`、`controllers`。
- `theme` setter：Widget 遍历之外，对 `_toasts/_tooltip/_palette/_find` 及 mounted controllers 调
  `set_theme(value)`（存在才调）。
- `_MountedOverlay.set_theme`（Tooltip 继承）、`Toasts.set_theme`（否则 toast 不换肤）、
  `CommandPalette.set_theme`（input/list/modal）、`Modal.set_theme`（scrim + Widget dialog；显式
  `scrim_style` 保留）、`Scrollbar.set_theme`（丢 strip memo + refresh）。

## C. Session 结构（`demo/session.py`）

- `class Session(App)`；`__init__` 先 `super().__init__(theme=THEMES[0][1] | 传入值, **options)`，
  再建状态、两个 dock（`Text("")` 占位，`mount_shell` 随后替换）、split、`Scrollbar`（mount）、
  clipboard、commands、`every(TICK)`、首个 topic、`paint`。
- `theme` 继承 App；`theme_index` 仍是 demo 状态，`theme_name` 由 shell 计算。
- `dispatch`：c-c -> quit；KeyEvent -> `stage.focus()`；`stats.handle(event)`（计数、不消费）；
  topic 的 `body.modal`（存在且 open）独占本轮；否则 `super().dispatch(event)`；最后 `_after_round()`。
- `on_key`：escape/c-n/c-p/[]/c-1..6//,c-k/c-f/c-t/c-g/space/q（tab 由 App 处理）；
  `on_event`：FocusEvent 失焦时 `pointer.clear()` 并消费。
- `_build_ring`：`set_focus_targets([catalog, *body targets])` 后显式
  `focus_manager.focus(body_targets[0])`（旧的“首个 body target”语义；否则 catalog 抢焦点、golden 会变）。
- `show_topic`：`_clear_stage` -> build -> `self.add(block, pane=stage)` -> `mount_shell(self)` ->
  `_build_ring` -> scroll_to(0)/stage.focus/title/status。
- 保留：`_clear_stage`（关/卸 body overlays、remove stage ids、关 find/palette）、`_read_picks`、
  `_read_modal_result`、`_read_palette_result`、`_build_commands`、`_tick`、`_copy_toast`、
  `set_theme`、`toggle_stats`。`open_palette()` 覆盖 App 同名方法（topics 调无参版），转发
  `super().open_palette(self.commands.options(), max_rows=10)`；`open_find()` -> `self.find()`。

## D. 入口点（T3）

- `render_topic`：`Session(screen=HeadlessScreen(...), interactive=False)` -> `show_topic` -> `paint()`。
- `_headless`：`Session(screen=..., keys=ScriptedEvents(script()), interactive=False)` ->
  `run_async()` -> 卸 tooltip -> `paint()` -> dump。
- 交互入口：`Session(theme=THEMES[0][1], hover=True, focus_events=True)` -> `run_async()`。
- `script.Anchors`：内部 `Session(screen=HeadlessScreen(...), interactive=False)`，
  `self.tui = self.session.tui`；锚点逻辑未改。`__main__.py`、`model.py` 未改。

## E. shell.py 增量

- `mount_header/mount_footer/mount_catalog` 改为只返回组件，不再接收 `Document`；新增
  `mount_shell(session)`（undock/忘旧组件/重建三区）、`status_left/status_right/refresh_status`、
  `follow_shell(session)`（header/catalog 点击落到 section/topic）。这些是 demo shell 逻辑，
  从 session.py 移入（为守住 300 行，见 F）。

## F. 偏差与取舍

1. `App.__init__` 多了 `on_selection`（T1 未列）：demo 的复制 toast 需要自定义 `on_end`；
   替代方案是在 Session 重建 `SelectionGesture`，但验收禁止。
2. `App.mount(..., dispatch=False)` 是“不要用 consuming mount 语义”的落地：`Stats` 只登记/换肤，
   Session 在 super 前自己 `stats.handle(event)`，避免 True 被消费。
3. `Toasts.set_theme` 超出 T1 点名的 `_MountedOverlay.set_theme`；否则 App.theme 到不了 toast band。
4. shell 装配移入 `shell.py`（session 只调用）；代价是 `Session.theme_name` / `focus_name`
   不再是公开成员（topics/入口未使用）。T2 commit 自身不能启动 demo（入口属 T3），最终 HEAD 全绿。
5. `Modal.set_theme` 同时更新 scrim（显式 `scrim_style` 保留），比工单多一步。

## G. 未决

- `page_up/page_down` 不再被 demo 消费（旧 shim 对 focused pane 滚 1 行；App 只路由 wheel）。
  `shell.mount_shell` 清理 `Session._components` 用了 App 私有列表，未新增公共 API。

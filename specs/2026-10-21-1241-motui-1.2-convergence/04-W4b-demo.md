# W4b · demo 重写到 App

> 分支 `refactor/1.2-w4b-demo`；worktree `C:\Users\shifu\.worktrees\motui\1.2-w4b-demo`
> 前置：W4a 已合并（`978a479`）；写入范围见下；波末必须全量绿。

## 目标

把 demo 的 `Session` 从“手写 590 行 host 循环 + 手工挂 8 个控制器”重写成 `App` 的子类：默认焦点/指针/手势/滚轮/toast/find/palette 由 App 提供，Session 只保留 demo 自己的导航、shell、picks 和 Stats/Scrollbar 两个自定义控制器。**最终画面、`--pages` dump、headless replay 输出必须与重写前逐字节一致。**

## 前置上下文

- 必读顺序：
  1. `ref/repo-map.md`
  2. `ref/interfaces.md`（§3 W4 App/TUI + W4a 实际交付）
  3. `handoff/W4a-w4a-app.md`
  4. 本工单
- 基线命令：

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python -m motui < /dev/null | sha256sum
uv run python -m motui --pages | sha256sum
```

起点 **880 passed / 57 topics match**；把两个 sha256 记进 handoff，重写后必须相同。
- 稳定区（勿重读/勿改）：`core/**`、`widgets/**`、全部 golden、`docs/**`、root `__all__`。
- 已知约束/坑：
  - `App` 已能默认挂 focus/pointer/gesture/toasts/tooltip，但还不能挂自定义控制器（Scrollbar/Stats）；也不能把 `interactive/focus_events/sync` 透传给 TUI。T1 补这些。
  - `App.theme` 目前只遍历 `_components` 的 Widget；app-owned overlays（Toasts/Tooltip/Palette/Find）不会自动换主题。T1 补 `set_theme` 钩子。
  - `Session` 目前通过 `TUI` 构造并手写 `_round`；W4b 改成 `Session(App)`，入口点传 `screen/keys/interactive`。
  - `demo/script.py::Anchors`、`demo/__init__.py` 各自构造 `TUI`，必须改成 `Session(...)`（App 子类）。
  - `TUI.dock` 现在接受 Component；`Session` 的 header/footer 需要从“传 Viewport”改成“传组件”。
  - `Table`/`ScrollView` 的 W5 改动不在本波；不要改它们。

## 工单（按序执行，每项一个 commit）

### T1 · App 扩展（app/application.py + overlays/command_palette）

- `App.__init__` 增加并透传给 `TUI`：`interactive: bool | None = None`、`focus_events: bool = False`、`sync: bool = True`。
- `App.mount(controller)` / `App.unmount(controller)` / `App.controllers`：
  - 自定义控制器（demo 的 `Scrollbar`、`Stats`）注册到 App；
  - `dispatch` 在 toasts 之后、wheel/mouse 之前依次调用 `controller.handle(event)`；返回 True 即消费；
  - `unmount` 只移除，不自动 detach（宿主决定生命周期）。
- `App.tooltip` / `App.palette` / `App.find_bar` / `App.controllers` 只读属性。
- `App.theme` setter：除 Widget 遍历外，对 `_toasts`/`_tooltip`/`_palette`/`_find` 和 mounted controllers 调用 `set_theme(value)`（有则调用）。
- `_MountedOverlay.set_theme(theme)`：更新 `_theme` 并 `tui.refresh()`（Toasts/Tooltip 继承）。
- `CommandPalette.set_theme(theme)`：设置 `self.input.theme`、`self.list.theme`、`self._modal.set_theme(theme)`。
- `Modal.set_theme(theme)`：更新 `_theme`，并给 dialog（若是 Widget）设 theme。
- 只允许改：`app/application.py`、`app/overlays.py`、`app/command_palette.py`、`app/modal.py`、`tests/app/test_app.py`（仅必要扩展）。
- 验证：pytest + golden 不变。

### T2 · Session 改成 App 子类

- `demo/session.py`：`class Session(App)`。
  - `__init__`：`super().__init__(...)`；保留 demo 状态（section/topic/body/last_pick/theme index 等）；建 docks、split、自定义控制器、commands、tick、首个 topic。
  - 用 `self.add/get/remove`、`self.split`、`self.dock`、`self.set_focus_targets`、`self.bind`、`self.toast`、`self.open_palette`、`self.find`。
  - `self.stage` / `self.catalog_pane` 保留为 `Pane`；`self.catalog` / `self.header` / `self.footer_bar` / `self.footer_status` 保留。
  - `Scrollbar`：创建后 `self.mount(self.scrollbar)`；`set_theme` 时 `self.scrollbar.set_theme(theme)`（若 `Scrollbar` 没有该方法，加一个最小实现，放在 `app/scrollbar.py`，允许改）。
  - `Stats`：`toggle_stats` 创建后 `self.mount(stats)`；卸载时 `self.unmount(stats)` + `stats.detach()`；在 `Session.dispatch` 里先调用 `stats.handle(event)`（它只计数、消费 False，不要用 App 的 consuming mount 语义）。
  - 删除手动 `FocusManager`/`Pointer`/`SelectionGesture`/`Toasts`/`Tooltip`/`Find`/`CommandPalette` 的构造与 `_round` 分发顺序；改用 App 的属性与方法。
  - 删除 `run`；入口点用 `await self.run_async()`。
  - `dispatch` override：
    ```python
    def dispatch(self, event):
        if isinstance(event, KeyEvent) and event.key == "c-c":
            self.quit(); return True
        if self.stats is not None:
            self.stats.handle(event)
        consumed = super().dispatch(event)
        self._after_round()
        return consumed
    ```
  - `on_key` 保留 demo 的导航键（c-n/c-p、[ ]、c-1..6、/、c-f、c-t、c-g、space、q）；`tab` 由 App 处理。
  - `_mount_shell`：header/footer 用 `undock` + `dock(component)` 重建，或保留组件并重建内容；catalog 用 `self.add(..., pane=self.catalog_pane)` 重新挂载；确保 `show_topic` 后 shell 与旧输出一致。
  - `_clear_stage` 用 `self.remove(id)`；close/detach topic overlays。
  - `_build_ring` 用 `self.set_focus_targets([self.catalog, *body.focus.targets])`；`focus_name` 用 `self.focus_manager.focused`。
  - `_read_picks` 保留；`_read_modal_result`/`_read_palette_result` 用 `self.palette`/`self.find_bar` 引用。
  - `set_theme`：`self.theme = theme`；更新 `scrollbar`/`stats`；重建 shell 文本；不再重建 Palette/Find/Toasts（App 的 set_theme 负责 overlays）。
  - 目标行数 ≤300（stretch 250）；不要为了行数把逻辑搬到无意义的文件。
- `demo/shell.py`：
  - `mount_header` 返回 `Header`（不再接收 Document）；
  - `mount_footer` 返回 `(Column, bar, status)`；
  - `mount_catalog` 返回 `NavList`；
  - 保持渲染内容/尺寸不变。
- `demo/model.py` 的类型提示若引用 `TUI`，改成 `App` 或 `Session`。
- 只允许改：`demo/session.py`、`demo/shell.py`、`demo/model.py`、`app/scrollbar.py`（仅 `set_theme`）。
- 验证：pytest + golden 不变；`python -m motui --pages` 输出 sha256 不变。

### T3 · demo 入口与 replay

- `demo/__init__.py`：
  - `render_topic`：`Session(screen=HeadlessScreen(...), interactive=False)`；`session.show_topic(...)`；`session.tui.paint()`。
  - `_headless`：`Session(screen=HeadlessScreen(...), keys=ScriptedEvents(script()), interactive=False)`；`asyncio.run(session.run_async())`；`_dump(session.tui)`。
  - 交互入口：`Session(theme=THEMES[0][1], hover=True, focus_events=True)`；`asyncio.run(session.run_async())`。
- `demo/script.py::Anchors`：`Session(screen=HeadlessScreen(...), interactive=False)`；其余锚点逻辑不变。
- `demo/__main__.py` 不变。
- 只允许改：`demo/__init__.py`、`demo/script.py`。
- 验证：两个 sha256 与重写前逐字节一致；golden 不变。

### T4 · 波末门禁

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null | sha256sum
uv run python -m motui --pages | sha256sum
```

## 验收

1. 五条门禁全绿；两个 sha256 与重写前相同；golden 57 不变。
2. `demo/session.py` 不再构造 `FocusManager`/`Pointer`/`SelectionGesture`/`Toasts`/`Tooltip`/`Find`/`CommandPalette`；不再手写 `_round` 分发。
3. `Session` 是 `App` 子类；入口点全部用 `Session(...)` + `run_async()`。
4. `demo/session.py` ≤300 行（报告实际行数）。
5. `App.mount/unmount`、`App.theme` overlay 传播、`CommandPalette.set_theme` 有最小覆盖（可复用现有测试，不新增测试文件）。

## 禁触清单

- `core/**`、`widgets/**`（除 `app/scrollbar.py` 的 set_theme）。
- W5 的 Table wrap / ScrollView bar 输入。
- `docs/**`、README/CHANGELOG/pyproject、root `__all__`、golden。
- `.zcodeignore`、`dist/`、`.venv/`。

## 交接包

完成后写 `handoff/W4b-w4b-demo.md`（60-80 行），重点写 App 扩展、Session 结构、行数、两个 sha256、入口点变化、仍保留的 demo-specific 逻辑。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 /
交接校验 / 探索审计 / 未决问题

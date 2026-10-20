# W2 · driver 生命周期、坐标与 pane/dock
> 分支 `w2-driver`；前置：W1 已合并 @ `a84bcf7`；写入范围见下。
> 深读：`00-overview.md` D6/D7、`ref/interfaces.md` §2、`docs/CONTRACT.md` §2–§4。

## 目标

把 driver 的作用域、生命周期和坐标统一，并让 frame/pane 结构变更能自动触发重绘。完成后 host 只面对一套
driver API：`read_event` / `exit` / `refresh` / `run_session` / `run_async` / `hit` / `hit_leaf` /
`pane_at` / `dock` / `undock` / `visible_range`。**渲染结果不变**（golden 不动）。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` §1（已落地）+ §2 → `handoff/W1-events.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：
  ```bash
  uv sync --locked
  uv run pytest -q -p no:cacheprovider
  uv run python tools/golden.py --check
  uv run python tools/framebench.py
  ```
  期望：1719 passed / 2 skipped；11 页 match；render-hash `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`。
- 稳定区（已验收，勿重读）：事件模型与 decoder（W1）、`widgets/markdown/**`、`demo/pages/**` 的渲染逻辑。
- W1 已知约束：键盘只认 `KeyEvent`；鼠标用 `MouseEvent.button`/`.kind`；滚轮 `kind=="wheel"`；
  不要再引入 `Key`/`Paste`/`KeySource`/`ScriptedKeys`；不要改 `TUI.stop/run/split/hit_test` 的旧行为
  之外的东西（本波正是要改它们）。

## 工单（按序执行；每个波次 HEAD 必须全绿；commit 粒度不限）

### T1 driver 生命周期（`src/motui/app.py`）

- `stop()` → `exit()`（删除 `stop`，更新所有调用点：demo、tests、interaction、README）。
- `exit()` 必须：
  - 置 `_stopped`；
  - 置一个新的 `self._exit_event`（`asyncio.Event`）；
  - 唤醒 pump；
  - 让正在 `await tui.read_event()` 的协程**立即返回 `None`**。
- 实现方式建议：`read_event` 用 `asyncio.wait` 同时等 `source.read()` 与 `_exit_event.wait()`；
  exit 胜出时取消读任务并返回 `None`；真正的 source 关闭由 teardown 的 `close()` 完成。
- `run(body)` → `run_session(body)`（保留现有 body 语义）。
  新增：
  - `async def run_async(self) -> None`：进入屏幕、启动 pump、`await _exit_event.wait()`、teardown。
  - `def run(self) -> None`：`asyncio.run(self.run_async())` 的同步包装。
- 每次 run 重置：`_stopped`、`_exit_event`、`_every`、`_selection`、`_selection_pane_id`、`_tiling`、
  `_tiling_revision`、`_dirty`；`_teardown` 后把 owned source 置回 `None`。
- key source 归属：记录 `self._owned_source: EventSource | None`，teardown 只 close 它，不再用
  `_owns_keys` bool 判断当前 `self.keys`。
- `_pump()` 修唤醒丢失：在 `tick()` **之前** `clear()` wake event；`tick` 后如果 `_dirty` 且没有定时任务，
  立即再跑一轮；不要出现 `_dirty=True` 却无限等待。
- `TUI.screen` 改只读属性（内部 `_screen`）；`Painter` 继续在构造时捕获同一个 screen。
  不再允许 host 替换 `tui.screen`。
- `invalidate()` → `refresh()`（删除 `invalidate`，更新所有调用点）。
- `TUI.paint()` 保留为低层入口（golden/tools 用），但文档标明 host 用 `refresh()`。
- 不要在本波改 `every()` 的异常语义（留 W6）。

验证：`uv run pytest -q tests/test_app.py -p no:cacheprovider`。

### T2 坐标与命中（`app.py` + `kernel/frame.py`）

- `Hit` 改为：
  ```python
  @dataclass(frozen=True)
  class Hit:
      pane: Pane
      block: Block
      row: int
      col: int
      leaf: Component | None = None
      leaf_row: int = 0
      leaf_col: int = 0
      @property
      def pane_id(self) -> str: ...
  ```
- `TUI.hit(x, y) -> Hit | None`：
  - 先做严格边界：`0 <= x < screen.width`、`0 <= y < screen.height`，否则 `None`；
  - `FrameTable.resolve` 改为严格区间：列必须落在 span 的 `[start, start+width)`，不再 snap 到最近；
  - `Hit.col` 相对 pane 的 **inner rect**（`frame.region(pane.id)`），不是 `pane.rect`；
  - 解析 leaf：`descend(hit.block.component, hit.row, hit.col)`，填 `leaf/leaf_row/leaf_col`。
- `TUI.hit_leaf(x, y)`：返回 `(Component, row, col) | None`，内部用 `hit()`。
- `TUI.pane_at(x, y) -> Pane | None`：严格边界 + table resolve；可返回 dock。
- 删除 `hit_test`、`hit_component`、`focus_at`；更新所有调用点（demo、interaction、tests、README）。
- `FrameTable.resolve` 的 docstring 与实现一致；越界返回 `None`。
- `Hit` 的 `pane_id` 只作为便捷属性，保留给现有 selection/gesture/find 使用。

验证：`uv run pytest -q tests/test_app.py tests/test_frame.py tests/test_pointer.py tests/test_gesture.py -p no:cacheprovider`。

### T3 pane/document 作用域（`app.py` + `kernel/frame.py` + `kernel/block.py`）

- `Pane` 增加委托方法：`add/get/remove` → `self.document`。
- `TUI.pane(id) -> Pane`：按 id 找 content pane 或 dock；未知 id 抛 `KeyError`。
- `TUI.add(..., pane: Pane | str | None = None)`：默认 = focused pane；显式 pane 优先。
- `TUI.get/remove(id)`：搜索**所有** pane 的 document + docks；找到多个同名 id 时抛 `ValueError`
  （列出 pane id），不再静默取第一个。
- frame 内 block id 全局唯一：`TUI.add` 自动 id 时扫描所有 document，生成下一个未占用的 `bN`；
  显式 id 冲突由 `Document.add` 抛错。
- `Pane.split()` 的 id 改为 frame 级单调计数：`pane-1`、`pane-2`…，永不复用；
  没有 frame 时用模块级 fallback（仅测试/脱离 frame 的 Pane）。
- `Pane.close()` 修复嵌套 survivor：若唯一 survivor 自身是 split container，父 pane 接管它的
  `division`/`children`，不能只拿 viewport/chrome 把子树丢掉。
- `Pane.split()`/`close()` 拒绝 dock（dock 不是窗口）。
- `TUI.split(..., pane=None)`：默认 focused pane；可显式指定。
- `TUI.document`/`TUI.viewport` 保留为 primary 的只读视图（属性），不再作为 `add` 的默认目标。

验证：`uv run pytest -q tests/test_app.py tests/test_frame.py tests/test_block.py -p no:cacheprovider`。

### T4 dock 取代 band（`app.py` + `kernel/frame.py` + `kernel/viewport.py`）

- `Frame` 的单个 `_band` 改为 `_docks: dict[str, Pane]`，键为 `"top"`/`"bottom"`。
  方法：`set_dock(edge, pane | None)`、`dock(edge) -> Pane | None`、`docks` property。
  `_adopt`/`_leaves`/`pane`/`region`/`compose`/`_regions`/`retile`/`focused_pane`/`focus`/`__repr__`
  全部适配；dock 仍不参与 focus/split。
- `TUI.add_band/remove_band/band` 删除，改为：
  ```python
  tui.dock(viewport, *, edge: str = "bottom", size: int | None = None) -> Pane
  tui.undock(edge: str = "bottom") -> Pane | None
  tui.dock_region(edge: str = "bottom") -> Rect | None
  ```
  同一 edge 重复 dock 抛 `RuntimeError`；`size=None` 用 `viewport.natural_height(width)`。
- `TUI._retile` 支持 top + bottom 同时存在：
  - 先算两个 dock 的高度（显式 size 或自然高度，clamp 到屏幕高度）；
  - content 区域 = 剩余行；`Rect(0, top_h, width, height - top_h - bottom_h)`；
  - top/bottom 各自 `Rect`；
  - 高度为 0 的 dock 不 compose、不进入 ownership table，不留幽灵行。
- `Frame.retile(rect, *, docks: Mapping[str, Rect | None] | None = None)`：
  - `None` 表示所有 dock 释放；
  - 空 Rect 的 dock 从 `_regions` 跳过。
- `TUI.viewport_rows` → `TUI.visible_range(pane=None) -> RowRange | None`：
  ```python
  @dataclass(frozen=True)
  class RowRange:
      first: int
      last: int
  ```
  `first/last` 是**屏幕行**（含 top pin 偏移）；`ScreenLayout` 增加 `viewport_start` 字段
  （body 在 pane rows 中的起始行，`top_kept`），由 `Viewport.layout` 填充；
  `Frame.compose` 的手工 layout 填 0。`visible_range` 读 `frame.pane_layout(pane.id)` +
  `frame.region(pane.id)`，不得重新 layout。
- `TUI.reveal`/`_scroll_viewport`/`Scrollbar`/`Find`/`SelectionGesture` 中的 `viewport_rows`
  调用点全部迁移；`Scrollbar` 的 pane 宽度/高度读取保持现有行为。

验证：`uv run pytest -q tests/test_app.py tests/test_frame.py tests/test_viewport.py tests/test_scrollbar.py tests/test_find.py tests/test_gesture.py -p no:cacheprovider`。

### T5 frame 结构变更自动脏（`app.py` + `kernel/frame.py`）

- `Frame` 增加 `on_change: Callable[[], None] | None`；`_touch()` 里调用它。
- `TUI` 构造后设置 `self._frame.on_change = self.refresh`。
- 这样 `pane.split()`、`pane.close()`、`pane.add_chrome()`、`frame.set_dock()`、
  `frame.add_overlay()`、`frame.remove_overlay()` 都会让 driver 自动变脏；
  host 不再需要额外 `refresh()`。
- 避免递归：`refresh()` 只置 dirty + wake，不同步 paint。
- 测试：直接调用 `tui.frame.pane("primary").split(...)` 后，下一次 `tick()` 必须产生新帧。

### T6 Screen 契约（`kernel/screen.py` + `interaction/gesture.py`）

- `Screen.copy(text)` → `Screen.copy_to_clipboard(text) -> bool`；`TerminalScreen` 实现后 flush。
- `HeadlessScreen` 同步改名；记录 output。
- `Screen` protocol 增加 `size: tuple[int, int]`（或 `width`/`height` 已有的组合）与 `color_mode`
  的只读声明；不要求本波实现所有能力。
- `copy_on_select` 使用 `copy_to_clipboard`。
- `TUI.screen` 只读（T1 已做）。

### T7 测试、demo、文档迁移

- 全仓 `stop(` → `exit(`、`invalidate(` → `refresh(`、`hit_test(` → `hit(`、
  `hit_component(` → `hit_leaf(`、`focus_at(` → `pane_at(`、`add_band(` → `dock(`、
  `remove_band(` → `undock(`、`viewport_rows(` → `visible_range(`。
- 新增测试：
  - `exit()` 能让阻塞中的 `read_event()` 返回；
  - 同一 TUI 连续两次 `run_session`；
  - `hit(-1,0)`/`hit(0,-1)`/`hit(width,0)`/`hit(0,height)` 返回 `None`；
  - 左/右 chrome 下 `Hit.col` 相对 inner rect；
  - split 子 pane 的 `tui.pane(id).add/get/remove`；
  - block id 全局唯一、重复显式 id 抛错；
  - pane id 不复用；
  - `dock("top")` + `dock("bottom")` 同时存在、空 dock 不留行、`visible_range` 含 top pin 偏移；
  - `pane.split()`/`add_chrome()` 自动触发重绘；
  - `copy_to_clipboard` flush。
- demo 的 `stop`/`add_band`/`hi_test` 调用点同步；**不改 demo 的渲染内容**。
- README/DESIGN/COMPONENTS 中 driver API 示例同步；W7 会重写整篇，本波只改被重命名的引用。

### T8 全量门禁 + handoff

- 跑 `## 验收` 全部命令，贴真实输出。
- 最后一个 commit 写 `specs/2026-10-20-1819-motui-1-2-contract/handoff/W2-driver.md`（A/B/C 三节）。
- 不 merge / push / tag。

## 验收

1. `uv run pytest -q -p no:cacheprovider`：0 failed；总数 ≥ 1719 + 新增
2. `uv run python tools/golden.py --check`：11 页全 match（本波不应移动渲染）
3. `uv run python tools/framebench.py`：exit 0；render-hash 不变（贴值）
4. `uv run python -m motui < /dev/null`：exit 0
5. `uv run python -m motui --pages`：exit 0
6. `uv run python -c "from motui import TUI; from motui.app import Hit, RowRange; assert all(hasattr(TUI,n) for n in ('read_event','exit','refresh','run_session','run_async','hit','hit_leaf','pane_at','dock','undock','dock_region','visible_range'))"`：exit 0
7. `grep -rn "hit_test\|hit_component\|focus_at\|add_band\|remove_band\|viewport_rows\|invalidate(\|\.stop(" src tests --include='*.py'`：
   零命中（历史 spec/文档除外）
8. `git diff --stat main...HEAD`：范围 = 本工单写范围并集，无 golden 变化

## 禁触清单

- 禁改：`pyproject.toml`、`uv.lock`、`specs/**`（handoff 除外）、`docs/CONTRACT.md`、`tests/golden/**`、
  `kernel/events.py`、`keys/**`、`widgets/markdown/**`、`widgets` 的渲染逻辑、`interaction` 的
  selection/modal/overlay 策略（只改调用点）。
- 禁加：兼容 alias、旧名 re-export、deprecated 转发。
- 禁做：merge / push / tag / checkout main / 碰主检出或其它 worktree。
- 遇到阻塞：写清阻塞点后停止，不越界自救。

## 交接包

完成后写 `handoff/W2-driver.md`（60–80 行）：

- A：`git diff --stat`、新增/变更公开签名、基线真实结果
- B：与 spec 的偏差、踩坑、下一波必须遵守的隐式约束、未决问题
- C：关键文件:行号、commit、稳定区

## 最终报告

工单状态表（T1–T8）/ commit 清单 / 自测真实输出 / driver API 变更清单 / 测试改动清单 /
偏差与取舍 / 交接校验 / 探索审计 / 未决问题。

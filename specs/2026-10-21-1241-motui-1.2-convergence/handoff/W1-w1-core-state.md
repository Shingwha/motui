# W1 交接包
> 分支 `refactor/1.2-core-state` / 起点 `56a2365` / 2026-10-21

## A. 自动事实（从命令与代码生成，别凭记忆）

- `git diff --stat 56a2365..HEAD`：71 files, +786/-881。地图：
  - 新增 `src/motui/kernel/scroll.py`（`ScrollState`、`Scrollable`）。
  - 重写 `src/motui/kernel/cursor.py`（`Cursor` 取代 `CursorWindow`）。
  - 滚动接入：`kernel/viewport.py`、`kernel/frame.py`（`Pane.scroll_state`）、`widgets/scroll.py`、`interaction/scrollbar.py`。
  - 游标接入：`widgets/{list,choice,table,tree,navlist,tabs,menubar,strip}.py`。
  - 删除：`widgets/delegate.py`、`tests/widgets/test_delegate.py`、`tests/golden/topics/components--delegate.txt`；`BlockState`/`Block.seal`/`Block.state`/`Block.is_open`、`DEFAULT_HEADER_STYLE`、`COLORBGBG`。
  - `kernel/__init__.py` 删 `CursorWindow`/`BlockState`，加 `ScrollState`/`Scrollable`/`Cursor`。root `src/motui/__init__.py` 未动（W6）。
- 新公开接口（kernel 层）：
  - `ScrollState(offset=0, content_height=0, viewport_height=0, stick_to_bottom=False)`；`max_offset/clamp/scroll_to/scroll_by/reveal/thumb` 按 `ref/interfaces.md` §1。
  - `Scrollable`（runtime_checkable Protocol）：`scroll_state`、`scroll_to`、`scroll_by`。
  - `Cursor(count=0, *, index=0, disabled=(), wrap=False)`；`select/move/home/end/window(size, *, anchor)`。
  - `Viewport.scroll_to` 现在返回 `bool`（原返回 `None`）；新增 `Viewport.scroll_by`、`Viewport.scroll_state`。
  - `Pane.scroll_state`（委托 viewport）。
- 行为规则：`Block.rows` 只在组件 `Revisioned` 且 `revision() is not None` 时缓存；否则每次 re-render。`testing.snapshot` 头改为 `[id]` / `[id | top]` / `[id | bottom]`。
- 环境：`uv sync --locked` 成功（uv 可用，CPython 3.13.16）；以下结果全部由 `uv run` 产生，无需 `.venv` 直调。
- 基线命令当前真实结果（本 worktree，CPython 3.13）：
  - `uv run pytest -q -p no:cacheprovider` → **885 passed in 10.61s**。
  - `uv run python tools/golden.py --check` → **57 topics match**。
  - `uv run python tools/framebench.py` → 跑完；`render-hash: a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`（与开工基线一致）。
  - `uv run python -m motui < /dev/null` → exit 0。
  - `uv run python -m motui --pages` → exit 0，4059 行。
- Cursor 策略保持：List 居中窗口、clamp；Select/ContextMenu 默认 top-stick，`window=True` 居中、默认 wrap；Tabs/NavList/MenuBar clamp + 跳过 disabled；Table/Tree clamp + 跳过 disabled。
- 测试面：`tests/kernel/test_cursor.py` 从 CursorWindow 改写为 Cursor；删 `test_seal_is_one_way`、`test_delegate.py`、COLORBGBG 参数化一例；其余只随 `.seal()` 删除做了最小改动。
- 验收 grep：
  - `rg "CursorWindow|_thumb_span" src` → 0；`_thumb_of` 仅剩 `interaction/scrollbar.py` 一个调用 `ScrollState.thumb` 的包装。
  - `rg "Delegate|BlockState|DEFAULT_HEADER_STYLE|COLORBGBG" src tests` → 0。
  - 同 grep 在 `docs` 仍有 5 处（COMPONENTS/CONTRACT/1.1.8 release），见 B。

## B. 只存在于脑子里的东西

- 偏差 1：`docs/**` 禁止修改与验收 3 冲突。docs 里的 Delegate/COLORBGBG 引用保留给 W6；src/tests 已清零。
- 偏差 2：T3 不只删除 delegate 帧。导航栏、命令面板计数（58→57）、组件表行都由 topic 集合派生，删 topic 后重录了 39 个 surviving 帧；逐 hunk 核对过，除侧栏 `Delegate` 行/末尾补空行外只有上述派生变化。T1 另重录 `components--scroll-view`、`interactions--scrollbar`（thumb 1→2 格）。
- 偏差 3：`tools/framebench.py` 调用了已删除的 `Block.seal()`，为 T4 门禁移除了两处调用（工具文件不在 T3 允许清单，但禁触清单未含 `tools/`）；性能口径不变。
- 坑（按成本）：`ScrollState.clamp` 按“上次布局 extent”决定是否贴底，所以 `Viewport.scroll_to_bottom` 必须先写 `offset=max_offset` 再置 `stick_to_bottom`，否则脱离后 scroll_to_bottom 不会在下次 layout 贴底；`scroll_by(-n)` 要显式清 stick。
- 坑：`Cursor` 构造不 clamp `index`（只 `select`/`move`/`window` 内部 clamp），这是为了保住 List/Table/Tree“stale index 读作无游标”的旧语义；控件 setter 用 `Cursor(...).clamp(value)`。
- 坑：`ClampedCursor.move` 旧实现即使走不动也再跑一次 `select(target)`，会 clamp 宿主原地替换 entries 后的越界索引；新实现必须在 move 后重设 `cursor.index = cursor.clamp(...)` 并与 pre-move 比较。
- 坑：`golden.py --update` 重写全部帧，Git 在此 worktree 上会把内容相同的帧显示成 `M`（stat cache）；以 `git diff` 为准，提交时显式 `git add` 路径。
- 坑：`Cursor.window(anchor="top")` 是旧的 top-stick 语义（cursor 在前 size 行时窗口固定 0，之后 cursor 为最后一行），不是“窗口永远贴顶”；`bottom` 才是尾对齐。别按名字反推。
- 坑：`ScrollState` 是可变 dataclass，私有 `_extent` 记录上次 clamp 的 extent（`compare=False`），语义靠它而不是靠外部标记；比较两个 state 时不要期待它参与。
- 坑：`Scrollbar` 的 thumb 公式与旧实现逐字节等价（round 两边一致），只有 `ScrollView` 从 floor 改成 round，所以 T1 的 golden 差异只出现在两个 ScrollView 帧。
- 坑：本机 framebench 绝对耗时约为 repo-map 的 2–3 倍（stream-split 12.4 vs 4.4）。用 `git archive 56a2365` 解到临时目录、同一解释器复跑得到相同数字，故为环境/负载差异，不是本波回归；hash 相同。
- 看着相关但没碰：`widgets/form.py`、`combobox.py`、`autocomplete.py` 没有自己的游标算术（Form 只是无 disabled 的 clamp，Combobox/Autocomplete 委托 Select）；`interaction/focus.py`、`dialog.py`、`find.py` 的 index clamp 不在 T2 清单。
- 下一波隐含约束：W2 搬包时 `ScrollState`/`Scrollable`/`Cursor` 要跟着进 `core/`，`interaction/scrollbar.py` 是唯一 `_thumb_of` 包装；W5b 才把 `Scrollbar` 从 `(tui, pane=...)` 泛化为 `Scrollable`。
- `ScrollView(bar=True)` 在内容不超过窗口时现在画纯 track（`ScrollState.thumb` 返回 `None`），旧实现画满格 thumb；无 golden 覆盖，已按 interfaces 语义接受。
- 未决：docs 的 Delegate/COLORBGBG 段落 W6 清理；`ref/interfaces.md` 的 “ScrollBar 接受 Scrollable” 仍属 W5b，本波未做。
- 未决：`ScrollView` 内容恰好等于窗口时 thumb 消失（只画 track）无 golden 断言；W5b 接鼠标输入时需确认这是期望行为。

## C. 指针

- `src/motui/kernel/scroll.py`（全部）、`kernel/viewport.py:255-330`、`widgets/scroll.py:141-190/259-285`、`interaction/scrollbar.py:71-101`。
- `src/motui/kernel/cursor.py`（全部）、`widgets/strip.py:54-105`、`widgets/choice.py:314-405`、`widgets/table.py:413-458`。
- `widgets/list.py:228-292`（Cursor 接入与窗口）、`widgets/tree.py:228-258`（stale 索引的 clamp 语义）、`kernel/frame.py:386-395`（Pane.scroll_state）。
- `src/motui/kernel/block.py:260-380`（缓存规则）、`src/motui/testing.py:66-84`。
- commits：`e142c6f`（T1）、`109414a`（T2）、`10a1b46`（T3）。
- 稳定区（下一波不必重读）：`tools/golden.py`、`docs/**`（W6 前不动）。

# ref · workspace 展品审计（现状与可行性底稿）

> 采集日 2026-10-07，仓库 `mocode-tui` @ `1120956`（showcase-redesign 组五波合并后：12 展品、864 行 dump）。
> 本文件是 `/workspace` 一页的"改前"依据；所有数字都是本机实跑值。

## 1. 分屏几何（实测）

```python
tui = TUI(screen=HeadlessScreen(110, 70))
left, right = tui.split("vertical", ratios=(2, 1))
# left  rect = Rect(x=0,  y=0, width=73, height=70)
# right rect = Rect(x=73, y=0, width=37, height=70)
# 每个窗格内容宽 = rect.width - 1（右列是滚动条 chrome）
```
- 右窗格内容宽 **36 列**（headless 110 宽时）。
- `Tabs(['tools','edits','reads','agent']).render(36)` → `' tools │ edits │ reads │ agent '`，31 列，**无截断**；
  加第五个标签就会截断（截断 label 不可点，interaction-model W2 的既定行为）→ **标签数封顶 4、标签名要短**。

## 2. 窗格内锚定与换装（实测，均已跑通）

| 能力 | 证据 |
|---|---|
| 窗格 document 支持 `pin="top"` | `right.document.add(Tabs(...), pin='top')` + `add(content)` → 标签条固定在窗格顶部，内容在其下滚动 |
| 换视图 = 移除 + 重挂 | `right.document.remove(block.id)` → `right.document.add(new_component)`（`remove` 收 **id 字符串**；传 Block 对象会 KeyError） |
| `Document` 公开面 | `add` / `blocks` / `get` / `remove` |
| `Pane` 公开面 | `add_chrome` / `band` / `children` / `chrome` / `close` / `division` / `document` / `focus` / `id` / `rect` / `remove_chrome` / `split` / `viewport` |
| 滚回顶部 | `pane.viewport.scroll_up(1 << 20)`（session 已有同款用法：`tui.scroll_up(1 << 20)`） |
| `Viewport` 公开面 | `at_bottom` / `document` / `layout` / `natural_height` / `offset` / `scroll_down` / `scroll_to_bottom` / `scroll_up` |

## 3. 现有 split 预览（要复用的缝）

`session.py` 的 `_open_preview()` / `_close_preview()`：

```python
_, right = self.tui.split("vertical", ratios=(2, 1))
self.preview = right
right.document.add(Column([ ...ticker 驱动的活件 + 20 行填充 ]))
self.preview_tick = self.tui.every(PAGE_TICK, lambda: self._tick_preview(spinner, bar, line))
...
self.preview_tick.cancel(); self.preview.close()   # /split 再来一次或 escape
```
→ 一个右窗格槽位、`close()` 归还、`tui.every` 驱动刷新。`/workspace` 的 aside 与它是**同一个槽位**。

## 4. 页面模型与宿主钩子（现状）

```python
@dataclass
class PageBody:
    blocks: Sequence[Component]
    focus: FocusRing | None = None
    hint: str = ""
    tick: Callable[[], None] | None = None   # 页面节拍（tui.every(PAGE_TICK) 驱动）
    note: Callable[[str], None] | None = None  # 宿主报告一次激活结果
```
- `show(page)`：清 transcript → `page.build(self)` → 逐块 append → `main.focus()` → 滚到顶 → 刷新 banner/状态行。
- `Page(name, nav, description, build)`；`PAGES` 现 12 条；导航条 `tabs.render(110)` = **97 列**（12 短标签，无 `..`）。
  加 `work` 后 ≈104 列，仍 ≤110（本波须实测复核）。
- 事件路由（`run()`）：scrollbar → toasts → gesture(+`_page_click`) → palette → `playing and ring.handle` →
  `editor.handle` → `c-c`/`tab`(ring.focus_next)/`c-o`(窗格)/`escape`/`enter`。`playing` = composer 空 + 非打印 `Key`。
- `_page_click`：stationary left click → `hit_test` → `ring.click(hit)`（**任何可点组件都派发**，不限于环内）。
- 状态行：`<页名> · focus=<聚焦对象|-`。

## 5. dump 与门禁（本组改前）

```
uv run pytest -q                                  → 948 passed, 1 skipped
uv run python examples/demo.py < /dev/null        → exit 0，70 行
uv run python examples/demo.py --pages            → exit 0，864 行、12 个 '── /' 页头
uv run python tools/framebench.py                 → render-hash 5bcfdf16…ba9a（本组不许动）
uv run pytest tests/test_readme_examples.py -q     → 6 passed
git diff --stat <base>..HEAD -- src/              → 必须为空（展示台组只动 examples + 文档）
```
`--pages` 的 dump 是**整帧的文本**（`tui.rows`）→ 分屏页会把左右两栏并排 dump 出来，这正好是
"这一页长什么样"的最强证据（但也意味着右栏内容会被 37 列宽约束）。

## 6. 本页要用到的组件（都已就绪）

`Message` / `ToolBlock` / `EditBlock`（chat 层）、`Tabs`（点击 + `select`/`move` + `focused` 失焦变暗）、
`Markdown`（语法高亮走 fence）、`Divider`、`Text`、`FocusRing`、`Toasts`、`TUI.split`/`Pane.close`、
`tui.every`。**零库改动**。

## 7. 已知边界（写进本组不变量）

- 右窗格 36 列：长行会折行，代码块也会折；视图内容要按窄栏设计（短行、少列的表）。
- 标签条只有 4 个位置；截断的标签不可点（`Tabs.click` 的既定语义）。
- 非交互路径没有真实时间：任何"长出来/换出来"的东西都必须在**构造期就能完整**（dump-safe），
  逐条或者逐步的动画只能由"交互模式 + tick"驱动。

## 8. 终态基线（组收尾实测，2026-10-07 @ 合并后）

| 命令 | 终态实测 |
|---|---|
| `uv run pytest -q` | `948 passed, 1 skipped`（组内一字未动） |
| `uv run python examples/demo.py < /dev/null` | exit=0，70 行；末帧 = `/workspace` 左对话 + 右检查器（`agent` 标签），右栏 `agent: 7/7 messages · done` |
| `uv run python examples/demo.py --pages` | exit=0，**936 行**、**13 页头**（新增 `/workspace` 在 `interaction` 与 `streaming` 之间） |
| `uv run python tools/framebench.py` | `5bcfdf164f89ca383194df2b1d3ac168137082220d690d708ba94c20423aba9a`（未动） |
| `uv run pytest tests/test_readme_examples.py -q` | `6 passed` |
| `git diff --stat 1120956..HEAD -- src/` | **空** |

**分屏页的 banner 几何（终态）**：左栏 71 内容列装不下 104 列的全量条，故该页按 T4 窗口化——
标题 `mocode-tui showcase · workspace (11/13)`、窗口条 `' interact │ work │ stream '`（26 列、无 `…`）、
短提示 62 列单行；其它 12 页保持全量 13 标签（104 列）与长提示。

**live 证据（交互模式，手工驱动 `PageBody.tick` + `paint`）**：
`agent: 0/7` → 3 拍 `3/7` → 7 拍 `7/7 · done` → 再拍仍 `7/7`；`←` 离开再 `→` 回来 → 回到 `0/7`（重播）。
非交互路径同一视图**构造即完整**（`7/7`），所以 `--pages` / piped 永远 dump 出完整报告。


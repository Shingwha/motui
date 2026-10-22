# W2 · 增量窗口索引（M2）
> 分支 `fp-w2-window-index`；前置 W1 已合并（`789da41`）；写入范围 `src/motui/core/viewport.py`、`src/motui/core/block.py`（如索引需要）、`tools/framebench.py`、`tests/core/test_viewport.py`、`docs/DESIGN.md`

## 目标

`Viewport.layout` 从"每帧无条件漫游全部块"改为增量索引，渲染字节与全部既有测试零变化：
revision 等值比较探测脏块 → 只重渲变化块 → 前缀和增量维护 → 窗口二分定位 → 只物化
与 `[offset, offset+vh)` 重叠的行。每帧成本从 O(全部块 × 各自调用开销) 降到
O(全部块的最廉比较 + 变化块渲染 + log n 定位 + 可见窗口行)。**这是结构性重构：索引
是 Viewport 的私有状态，公开 API 与 `ScreenLayout` 契约零变化；`core/scroll.py` 零 diff。**

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W1-a.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：`uv run pytest -q`（897 passed）；
  `uv run python tools/framebench.py`（关注 `scroll-long`、`text-open`、`render-hash`
  = `a82f7968…`；`idle-long` 行尚不存在）。
- 上一波交付摘要（W1，`789da41`）：`Block.rows_view`/`row_count`/`_refresh`（block.py:378-435）、
  `Document.mutation` + `blocks()` 快照缓存（block.py:490-540 附近）；行走方已全部切换，
  `grep "\.rows(" src/motui` 零命中。
- W2 直接可用的入口（handoff A/B 节）：`row_count(width)`（hit 不 render 不拷贝）、
  `Block.revision()`（None = 永远脏）、`Document.mutation`（新鲜度 = 属性读 + 整数比较）、
  `blocks()` 未变时返回同一 tuple（可当稳定数组持有）。
- 已知约束/坑：
  - **不得跨帧持有 `rows_view` 的借用列表**（借用契约：只读、不保证后续内容；W2 索引
    只存 `(block, revision, count)` 与前缀和，不存行引用）。
  - `revision() is None` / 非 cacheable 的块**永远脏**：每帧重渲重数（今天语义，红线）。
  - `tests/core/test_viewport.py` 的 render 调用计数断言零修改（render 只在 miss/脏）。
  - `ScreenLayout.__post_init__` 已跳过 tuple 输入的归一化（W1），`layout()` 传 tuple 即零拷贝。

## 工单（按序执行，每项一个 commit）

### T0 docstring 保真（W1 尾巴）

- `_refresh` 的 miss 路径是**替换**缓存对象（`self._rows_cache = rows`），借出的旧列表
  内容不会变——`rows_view` docstring 里 "a later miss refills the very same list" 措辞
  不实。改为如实描述（借用列表不得改动；跨帧读取内容不保证一致），契约仍不许跨帧依赖。
- 只允许改：`src/motui/core/block.py`（仅此 docstring）。
- 验证：`uv run pytest tests/core/test_block.py -q`。

### T1 viewport 私有索引

- 做什么：viewport.py 内私有类（如 `_BodyIndex`）：键 `(document.mutation, width)`；
  持有 body 块的 `(block, revision, count)` 数组 + 前缀和数组 + body 总高 + pinned
  （top/bottom）块引用与计数 + `block_order` tuple（按 mutation 复用同一对象）。
  API 自定（私有），但必须让 `layout`/`natural_height` 共用。前缀和用朴素 suffix 重算
  （从最脏块起，P6）。全量重建只在键变化时发生。
- 只允许改：`src/motui/core/viewport.py`。
- 验证：`uv run pytest tests/core -q` 全绿（此时 layout 尚未切换，索引应可独立编译通过——
  若选择与 T2 一个 commit 更自然，可合并提交，但职责说明写进 commit message）。

### T2 layout / natural_height 切换到索引

- 做什么：`layout()` 重写为——索引新鲜度检查（mutation/width）→ 逐 body 块
  `revision()` 等值比较（脏则 `row_count(width)` 重数、标脏前缀）→ 窗口在累积高度上
  二分（bisect 或手写，等值语义以现实现的 `pos`/`block_end` 边界为准，逐字段对齐）→
  只物化窗口内块的行切片（`rows_view`）与 owners → pinned 块行照常 `rows_view` →
  `rows`/`body_rows`/`row_blocks`/`block_order`/`offset`/`total_rows`/`viewport_start`
  输出契约逐字段不变。`natural_height` 走索引（body 总高 + pinned 计数）。
  **先写对照再动手**：以 `hash_workload` 与 golden 为逐字节裁判。
- 只允许改：`src/motui/core/viewport.py`。
- 验证：`uv run pytest -q` 全绿；`uv run python tools/golden.py --check` 57 topics；
  framebench `render-hash` 逐字不变。

### T3 framebench `idle-long` 行

- 做什么：新增 `idle_long_workload(frames)`——构造同 `scroll_long`（sealed Markdown +
  3000 行规模的单行 Text 块，见 `scroll_workload(rows=3000)`），预热 paint 后每帧仅
  `refresh()+paint()`（零滚动零变化），输出 ms/frame；`main()` 加一行（在 `scroll-long`
  之后、`text-open` 之前）；模块 docstring 加基线段落（只记录，不改既有段）。
- 只允许改：`tools/framebench.py`。
- 验证：`uv run python tools/framebench.py` 新行出现且数值稳定（跑两次）。

### T4 新增测试（≤ 4 条，落在 `tests/core/test_viewport.py`）

- 覆盖：中尾块内容变更（revision 动）只重数该块、其余块 render 计数不增；中部
  add/remove 后地址算术与 ownership 正确（对照手算）；宽度变化全量重建；非 Revisioned
  块每帧重渲不冻结（render 计数每帧 +1）。
- 只允许改：`tests/core/test_viewport.py`。
- 验证：`uv run pytest tests/core/test_viewport.py -q` 全绿。

### T5 docs/DESIGN.md viewport 段校正

- 按索引后的现实校正相关段落（"a long document costs the window plus one walk of its
  blocks" 一类的措辞），讲清增量索引与失效键。只改 viewport 相关段落，不动 frame 段
  （W3a 所有）。
- 只允许改：`docs/DESIGN.md`。

## 验收

1. 波次级全量门禁（贴真实输出）：`uv run pytest -q`（897 + 新增 passed）；
   `golden: 57 topics match`；framebench：`render-hash` 逐字 `a82f7968…`；
   `idle-long` 接近单 pane 直通下限（对照 `text-open` 的 0.1 ms 量级，如实记录）；
   `scroll-long` 在 W1 后（≈1.3-1.4）之上再降；其余行 ±10% 噪声内。
2. 核心路径抽验：`tests/core/test_viewport.py`、`tests/app/test_scrollbar.py`、
   `tests/app/test_driver.py` 全绿且零修改。
3. `git diff main --stat` 只含写入范围文件。

## 禁触清单

`core/scroll.py`、`core/frame.py`、`core/painter.py`、`core/lines.py`、`core/screen.py`、
`core/selection.py`、`app/**`、`widgets/**`、`tests/` 下除 `tests/core/test_viewport.py`
外的一切、`pyproject.toml`、`CHANGELOG.md`。`src/motui/core/block.py` 仅允许 T0 的
docstring 修正。handoff 文件是唯一允许的写入范围外文件。

## 交接包

完成后在分支最后一个 commit 写 `handoff/W2-a.md`。重点：A 节贴 `idle-long`/
`scroll-long`/`render-hash` 前后对比与索引的关键不变量；B 节写 W3a（compose 容器复用）
需要知道的 viewport 侧现实（如 `layout` 每帧仍 O(height) 物化窗口行的下限）。

## 最终报告

工单状态表 / commit 清单（hash + message）/ 自测真实结论 /
偏差与取舍（摘要，详情进 handoff B 节）/ 交接校验（W1 handoff 中哪些被验证、哪些被推翻）/
探索审计（handoff 之外读了哪些文件、为什么）/ 未决问题。

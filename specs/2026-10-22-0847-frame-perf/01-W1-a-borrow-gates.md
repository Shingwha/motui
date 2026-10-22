# W1 · 借用门与快照复用（M1+M3+M4）
> 分支 `fp-w1-borrow-gates`；前置 无；写入范围 `src/motui/core/block.py`、`src/motui/core/viewport.py`、`src/motui/app/driver.py`、`src/motui/app/find.py`、`src/motui/app/gesture.py`、`src/motui/core/selection.py`、`tests/core/test_block.py`

## 目标

对外行为与渲染字节零变化的前提下，把每帧"为只读调用方付出的全量列表拷贝"与
"文档快照的 O(n) 重建"消掉：`Block` 增只读借用门与计数门并切换全部内部行走方
（清单 M1）；`ScreenLayout` 归一化对 tuple 输入跳过（M3）；`Document` 增 mutation
计数并缓存 `blocks()` 快照（M4，同时为 W2 预埋失效机制）。**公开契约一行不改；
这是把"门"放对位置的结构整理，不是在每个调用点打补丁。**

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → `ref/perf-checklist.md`（M1/M3/M4 节）→ 本工单。
- W1 无前置 handoff，跳过。
- 基线命令（开工先跑，贴真实输出）：
  `uv run pytest -q`（893 passed）；`uv run python tools/framebench.py`（关注
  `scroll-long` ≈1.6、`text-open` ≈0.1、`render-hash` = `a82f7968…`）。
- 稳定区（已验收，勿重读）：`core/scroll.py`、`core/lines.py`、`core/painter.py`、
  `widgets/markdown/**`、`tools/framebench.py`（本波禁改）。
- 已知约束/坑：
  - `tests/core/test_viewport.py` 的 render 调用计数断言是 render-cost D1 红线，必须
    不改一行通过（`rows_view`/`row_count` 只在 miss 时 render，与 `rows` 相同）。
  - `revision() is None` / 非 Revisioned 的块**永远不缓存**（现状语义，`block.py:375-382`）。
  - 清单行号对 main `58c5edb` 负责；若与你所见有出入，以代码为准并在报告记录。

## 工单（按序执行，每项一个 commit）

### T1 `Block` 的两个内部门 + `Document` 的 mutation 与快照缓存

- 做什么：
  - `Block.rows_view(width) -> Sequence[Line]`：cacheable 且命中 → 返回 `self._rows_cache`
    本体；miss → render、入缓存、返回缓存本体；非 cacheable → 返回 render 原列表。
    docstring 写清借用契约（borrowed, read-only, do not mutate; `Line` 值不可变可共享；
    the caller that owns a mutable copy wants `rows`）。
  - `Block.row_count(width) -> int`：hit → `len(self._rows_cache)`；miss → render、入缓存、
    `len`；非 cacheable → `len(render(width))`。实现与 `rows_view`/`rows` 共用同一条
    miss 路径（避免三份 render 判定逻辑漂移——考虑一个私有 `_refresh(width)` 或等效
    结构，公共 docstring 各自讲清契约）。
  - `Document`：私有 `_mutation = 0`，`add`/`remove` 各 +1；公开只读属性 `mutation`；
    `blocks()` 缓存 `(_mutation, tuple)`，未变返回同一 tuple。快照语义 docstring 保留
    （"immune to later mutation"——返回的 tuple 在下一次 mutation 前后都不变）。
- 只允许改：`src/motui/core/block.py`、`tests/core/test_block.py`。
- 验证：`uv run pytest tests/core/test_block.py tests/core/test_viewport.py -q` 全绿。

### T2 viewport 切换到借用门 + `ScreenLayout` 归一化跳过

- 做什么：
  - `Viewport.layout`（viewport.py:172）：`rendered = block.rows(width)` →
    `block.rows_view(width)`（后续 `len` / 切片 / `extend` 全是只读，逐处确认）。
  - `Viewport.natural_height`（viewport.py:251）：→ `sum(block.row_count(width) ...)`。
  - `ScreenLayout.__post_init__`：`type(x) is tuple` 时跳过 `tuple()` 归一化（四字段同
    规则）；docstring 注明归一化只为手构 layout（list 输入）服务，`layout()` 自己传
    tuple。**不许改公开契约**（构造仍接受任意 iterable）。
- 只允许改：`src/motui/core/viewport.py`。
- 验证：`uv run pytest tests/core/test_viewport.py tests/core/test_frame.py -q` 全绿。

### T3 应用层行走方切换

- 做什么（全部只读调用，行为零变化）：
  - `app/driver.py` `_body_address`（:165-166：前缀累计与计数）→ `row_count`；
    on-screen 检查（:588 `count = len(block.rows(...))`）→ `row_count`。相关 docstring
    里"reads rows"的措辞如失准，一并校正（改说的是门，不是语义）。
  - `app/find.py:286` `enumerate(block.rows(width))` → `enumerate(block.rows_view(width))`。
  - `core/selection.py:295` 同上 → `rows_view`。
  - `app/gesture.py:380` `rows = hit.block.rows(width)`（取一行）→ `rows_view`；
    `:616` 与 `:632` 的 `len(blocks[index].rows(width))` → `row_count`。
  - 切换后 `grep -n "\.rows(" src/motui` 应只剩 `block.py` 内定义/自用与 `viewport.py`
    不再出现 `block.rows(`（`rows_view`/`row_count` 除外）——把 grep 结果贴进报告。
- 只允许改：`src/motui/app/driver.py`、`src/motui/app/find.py`、`src/motui/app/gesture.py`、
  `src/motui/core/selection.py`。
- 验证：`uv run pytest tests/app -q` 全绿。

### T4 新增测试（≤ 4 条，落在 `tests/core/test_block.py`）

- 覆盖：`rows_view` 借用语义（两次调用同宽同 revision 返回同一对象 / 或内容相等——按
  实现写断言）；`row_count` 与 `len(rows())` 一致（命中与非 Revisioned 两态）；
  `blocks()` 未变时同一对象、add/remove 后是新 tuple 且旧 tuple 内容不变；
  `mutation` 单调递增。不加参数矩阵。
- 只允许改：`tests/core/test_block.py`。
- 验证：`uv run pytest tests/core/test_block.py -q` 全绿。

## 验收

1. 波次级全量门禁（贴真实输出）：
   - `uv run pytest -q` —— 893 + 新增数 passed，0 failed。
   - `uv run python tools/golden.py --check` —— 57 topics match。
   - `uv run python tools/framebench.py` —— `render-hash` 逐字 `a82f7968…`；
     `scroll-long` 相对基线（≈1.6 ms/notch）显著下降（≥ 20%）；`text-open` 不升；
     其余行不劣化超出噪声（±10%）。
2. 核心路径抽验：既有 `tests/core/test_viewport.py`、`tests/app/test_find.py`、
   `tests/app/test_gesture.py`、`tests/core/test_selection.py` 全绿且**零修改**。
3. `git diff main --stat` 只含写入范围文件。

## 禁触清单

`core/scroll.py`、`core/frame.py`、`core/painter.py`、`core/lines.py`、`core/screen.py`、
`widgets/**`、`tools/**`、`docs/**`、`tests/` 下除 `tests/core/test_block.py` 外的一切、
`pyproject.toml`、`CHANGELOG.md`。handoff 文件是唯一允许的写入范围外文件。

## 交接包

完成后在分支最后一个 commit 写 `handoff/W1-a.md`，按 SKILL「Handoff 协议」模板。
重点：A 节贴 framebench 三行前后对比；B 节写清 `rows_view`/`row_count` 的最终形态与
W2 直接可用的入口（W2 的索引将每帧调 `row_count`/`revision`）、以及任何与清单/工单的偏差。

## 最终报告

工单状态表 / commit 清单（hash + message）/ 自测真实结论 /
偏差与取舍（摘要，详情进 handoff B 节）/ 交接校验（本波无前置，写"无"）/
探索审计（写入范围与必读清单之外读了哪些文件、为什么）/ 未决问题。

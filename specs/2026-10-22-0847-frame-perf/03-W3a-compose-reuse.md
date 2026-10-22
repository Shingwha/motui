# W3a · compose 容器复用（M5）
> 分支 `fp-w3a-compose-reuse`；前置 W1/W2/W3b 已合并（main `a00e438`）；写入范围 `src/motui/core/frame.py`、`tests/core/test_frame.py`、`docs/DESIGN.md`

## 目标

`Frame.compose` 每次组合的 `plan`/`table` 两层列表分配（frame.py:1340-1341）在尺寸
不变时复用容器（逐行 clear 而非重建），D11 备忘录已防住的"重拼接"之外把"分配"也收掉；
如实现顺路，"整行单写"（无 chrome 覆写的行）可跳过拼接、直接消费 layout 行——以渲染
字节零变化为前提，不顺路则不做。**`compose` 输出契约、备忘录键语义、pass-through 路径
零变化；主战场是 `stream-split` 的 plan/table 分配。**

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W2-a.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：`uv run pytest -q`（905 passed）；
  `uv run python tools/framebench.py`（关注 `stream-split`、`render-hash` =
  `a82f7968…`；**隔离跑**——同一命令紧跟 pytest 会读到漂移值，W2 实测差 2-3 倍）。
- 上一波交付摘要（W2，`b89146a`）：viewport 布局已走 `_BodyIndex`（私有索引，键
  `(mutation, width)`），`layout` 每帧只物化可见窗口的行；`ScreenLayout` 构造对 tuple
  输入零再归一化（W1）。
- W2 handoff 给本波的现实（B 节）：
  - **别指望动 `idle-long`**（0.6–0.7 的主项是 sweep 每块 `revision()` 探测，viewport
    侧常数）；本波的证据行是 `stream-split`（基线 4.5–5.9 ms/frame，当日背景负载有
    漂移，降幅按同会话隔离对比记录）。
  - compose 对"单 pane 无 budgeted chrome"直通（pass-through，frame.py:1374-1385），
    直通帧 `layout` 只调一次——本波改动不触直通分支。
- 已知约束/坑：
  - 备忘录键 `(width, tuple(steps))` 是**值**键（frame.py:1393）：容器复用后每行仍要
    构造键 tuple，这是 D11 设计本身，不动。
  - `table` 的 `ordered = tuple(tuple(sorted(...)))`（frame.py:1370）每帧排序构建——
    除非顺路且零字节风险，本波不动它（worker 评估，动则单独 commit 且报告说明）。
  - `_row_memo` 每次 compose 整体替换（`fresh`），语义保持。
  - framebench 计时行对 CPU 竞态极敏感：验收数字必须隔离跑（W2 实测：紧跟 pytest 跑
    出 scroll-long 2.1 / 隔离复跑 0.7）。

## 工单（按序执行，每项一个 commit）

### T1 plan/table 容器复用

- 做什么：`plan`/`table` 提为 `Frame` 的实例状态（如 `self._plan_rows`/`self._table_rows`，
  命名随仓库风格）；compose 开头：height 相同 → 逐行 `row.clear()`；不同/首次 → 重建
  到新高度。后续写入逻辑不变（仍 append）。docstring 讲清生命周期（容器是帧间的缓冲，
  行内容每帧重建）。pass-through 分支行为不变。
- 只允许改：`src/motui/core/frame.py`。
- 验证：`uv run pytest -q` 全绿；`uv run python tools/golden.py --check` 57 topics；
  隔离跑 framebench：`stream-split` 下降（降幅如实记录），`render-hash` 逐字不变。

### T2 整行单写快路（顺路才做）

- 做什么：plan 中"恰一个写、且覆盖整行宽（x=0, take=width）"的行，其组合结果就是该
  `Line` 本身——跳过 `splice_row` 与备忘录进出，直接用该行。**前提**：以 render-hash
  与 golden 为逐字节裁判；若 splice 语义有任何不等价（如 Line 内部规范化差异），放弃
  本项并在报告记录原因（工单允许不做）。
- 只允许改：`src/motui/core/frame.py`。
- 验证：同 T1，另加 `tests/core/test_painter.py` 既有用例全绿。

### T3 新增测试（≤ 4 条，落在 `tests/core/test_frame.py`）

- 覆盖：同一 Frame 连续 compose 尺寸不变时结果逐行相等（容器复用不串帧）；尺寸变化
  后行数正确（无旧行残留）；多 pane + chrome 帧的 memo 仍命中（既有行为）；
  T2 若落地：单写整行与 splice 产物逐字节相等。
- 只允许改：`tests/core/test_frame.py`。
- 验证：`uv run pytest tests/core/test_frame.py -q` 全绿。

### T4 docs/DESIGN.md frame 段校正

- 按容器复用后的现实校正 compose 相关段落（讲清帧间缓冲与备忘录的分工）；只改 frame
  相关段落，不碰 viewport 段（W2 已改）。
- 只允许改：`docs/DESIGN.md`。

## 验收

1. 波次级全量门禁（贴真实输出，framebench 隔离跑）：`uv run pytest -q`
   （905 + 新增 passed）；`golden: 57 topics match`；`render-hash` 逐字
   `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`；
   `stream-split` 相对同会话基线下降；其余行漂移如实记录。
2. 核心路径抽验：`tests/core/test_frame.py`、`tests/core/test_painter.py`、
   `tests/app/test_scrollbar.py` 全绿。
3. `git diff main --stat` 只含写入范围文件。

## 禁触清单

`core/block.py`、`core/viewport.py`、`core/scroll.py`、`core/painter.py`、`core/lines.py`、
`core/screen.py`、`app/**`、`widgets/**`、`tools/**`、`tests/` 下除
`tests/core/test_frame.py` 外的一切、`pyproject.toml`、`CHANGELOG.md`。handoff 文件是
唯一允许的写入范围外文件。

## 交接包

完成后在分支最后一个 commit 写 `handoff/W3a-b.md`。

## 最终报告

工单状态表 / commit 清单（hash + message）/ 自测真实结论 /
偏差与取舍（摘要，详情进 handoff B 节）/ 交接校验（W2 handoff 中哪些被验证、哪些被推翻）/
探索审计（handoff 之外读了哪些文件、为什么）/ 未决问题。

## 依赖

W1+W2 已合并（M5 在 M1/M2 之后才是剩余大头）；`handoff/W1-a.md`、`handoff/W2-a.md`。

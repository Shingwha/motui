# Spec frame-perf · 每帧 O(总行数) 的结构根治：借用门、窗口索引、合成容器复用（W1–W3）
> 启动：2026-10-22 08:47（本地时间）；基线 main `58c5edb`（1.2.1）；分支 `fp-w1-borrow-gates`、`fp-w2-window-index`、`fp-w3a-compose-reuse`、`fp-w3b-value-cache`。

需求文档：`ref/perf-checklist.md`（用户提供的优化清单，M1–M6，权威）。本组把其中
M1+M3+M4（W1）、M2（W2）、M5（W3a）、M6（W3b）落成"底层重构式"改动：不加兼容
垫片、不留旧门面，缓存与索引的归属一次放对。

## 目标与非目标

最高约束（三条红线，全组逐波适用）：

1. **渲染字节零变化**：`framebench` 的 `render-hash` 必须逐字等于
   `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`
   （2026-10-22 实测当前 main 基线；工具 docstring 里的 `de48e747…` 是历史值，已被
   2026-10-18 之后的组合法移动，**不是**本组的红线）。`golden --check` 57 topics 绿，不重录。
2. **既有测试零修改**：893 passed 全绿；尤其 `tests/core/test_viewport.py` 的 render
   调用计数断言（render-cost D1 红线）不改一行。被新契约**直接逼着**改的用例须在报告中
   逐条列明并说明原因——本组的目标是零条。
3. **公开语义零变化**：`Block.rows()`（自有拷贝）、`Document.blocks()`（调用时刻快照）、
   `TextBuffer.value`、`Frame.compose` 对外行为不变；新增成员（`rows_view` / `row_count` /
   `Document.mutation`）是纯增项。不 bump 版本、不动 `pyproject.toml`。

**做**（清单 §五 的落地顺序，已拍板）：

- **W1 借用门与快照复用**（M1+M3+M4）：`Block` 增只读借用门 `rows_view` / 计数门
  `row_count`，全仓热路径切换；`ScreenLayout.__post_init__` 对已是 tuple 的输入跳过
  归一化；`Document` 增 mutation 计数，`blocks()` 未变时返回同一缓存 tuple。
- **W2 增量窗口索引**（M2，结构性根治）：`Viewport.layout` 从"每帧全块漫游"改为
  revision 等值比较 + 增量前缀和 + 窗口二分定位，只物化可见窗口的行；framebench 新增
  `idle-long` 行（只加不改）。
- **W3a compose 容器复用**（M5）：`Frame.compose` 的 plan/table 两层列表在尺寸不变时
  复用容器；单写整行跳过拼接。
- **W3b value 缓存**（M6）：`TextBuffer.value` 按 `version` 缓存 join 结果。

**不做**（清单 §四 遗留对账，维持挂起）：组件级真窗口化（Table/Tree/Radio 只渲可见行）、
`List` 前缀跳转索引、Select/Autocomplete description 列记忆、sealed 块 Spinner 冻结。
**不做**：版本号与发版（等用户指令）；`tests/` 结构重组；性能数值的"目标承诺"——只记录
实测（见下）。

## 拍板决策（照抄执行，不现场猜）

| # | 决策 | 取值 |
|---|---|---|
| P1 | `rows_view` 形态 | 返回缓存 list 本身，类型注解 `Sequence[Line]`，docstring 写明借用契约（只读、不得改动、Line 不可变可共享）。不做只读包装类——调用方全在 motui 内部，契约靠文档与测试钉住（与仓库 `Line` 不可变纪律同风格） |
| P2 | `row_count` 语义 | miss 时照常 render 并填充块自身缓存（首次布局仍渲染一次，与今天一致）；hit 时 `len(cache)`。非 Revisioned 组件每次 render 取 len（今天的语义） |
| P3 | `Document.mutation` | 公开只读属性，`add`/`remove` 各 +1；`blocks()` 以它为键缓存 tuple，调用时刻快照语义不变。W2 的索引失效同用此计数 |
| P4 | M3 实况 | `layout()` 现已传 tuple（CPython `tuple(元组)` 返回同一对象），故 M3 实测收益≈0；仍做显式 `type(x) is tuple` 跳过，把"归一化只为手构 layout 服务"写进 docstring。不夸大收益，报告如实记录 |
| P5 | W2 索引归属 | 索引是 `Viewport` 的私有状态（viewport.py 内私有类，不新建公共模块、不新增公共 API）。键 `(Document.mutation, width)`；revision 为 `None` 的块（无协议/记忆关闭）视为**永远脏**，每帧重渲重数——与今天语义一致 |
| P6 | W2 前缀和维护 | 朴素 suffix 重算（从最脏块起重算前缀和），不引入 Fenwick——追加为主的会话场景脏块几乎总在尾部；全量重建只在 mutation/width 变化时发生 |
| P7 | `idle-long` 行 | 3000 行文档（构造同 `scroll-long`：sealed Markdown + 2649 个单行 Text 块）、零变化、每帧 refresh+paint 的稳态耗时。只加不改既有行 |
| P8 | W3b 契约 | 已核实 motui 内部无对 `TextBuffer.lines` 的外部就地改动/整体赋值（`markdown/blocks.py` 的 `self.lines` 是另一类）。`value` 按 `version` 缓存；`lines` 公开可变是既有事实，docstring 补一行"直接改 `lines` 不 bump version，`value` 不跟"——不把 `lines` 改成 property（热路径属性，不为防御第三方付每次访问成本） |
| P9 | 测试预算 | 每波新增 ≤ 4 条（核心行为直测），不新建测试文件、不做参数矩阵；测试落在既有文件里 |
| P10 | 语言与 commit | 注释/docstring 英文（仓库现状），commit 英文一行祈使句（如 `viewport: borrow cached rows instead of copying per frame`） |

## 波次表

| 阶段 | 波 | 分支 | 写者 | 写入范围 | 前置 |
|---|---|---|---|---|---|
| 1 | **W1** 借用门与快照复用 | `fp-w1-borrow-gates` | A | `core/block.py`、`core/viewport.py`、`app/driver.py`、`app/find.py`、`app/gesture.py`、`core/selection.py`、`tests/core/test_block.py` | 无 |
| 2 | **W2** 增量窗口索引 | `fp-w2-window-index` | A（同一 agent 续做，保留上下文） | `core/viewport.py`、`core/block.py`（如索引需要）、`tools/framebench.py`、`tests/core/test_viewport.py`、`docs/DESIGN.md` | W1 合并 |
| 2 | **W3b** value 缓存 | `fp-w3b-value-cache` | C | `widgets/textbuf.py`、`tests/widgets/`（textbuf/field 所在既有文件） | W1 合并（与 W2 并行，文件级不相交） |
| 3 | **W3a** compose 容器复用 | `fp-w3a-compose-reuse` | B | `core/frame.py`、`tests/core/test_frame.py`、`docs/DESIGN.md` | W2 合并（M5 在 M1/M2 之后才是剩余大头） |

- 并行说明：W2 与 W3b 文件级不相交、无共享文件（W2 不碰 `tests/widgets/`，W3b 不碰
  `tools/framebench.py`）；计划合并顺序 W2 → W3b（W3a 在其后）。**实际**：W3b 先于 W2
  就绪合并（`a90a281`），W2 随后（`b89146a`）——文件不相交、无冲突，顺序互换无影响。
- `docs/DESIGN.md` 由 W2（viewport 节）与 W3a（frame 节）**先后**各改各的段落，不并发。

## 波次结果登记（lead 逐波门禁后回写）

| 波 | 合并 | 测试 | 关键行（lead/worker 同机实测） |
|---|---|---|---|
| W1 借用门与快照复用 | `789da41` | 897 passed | scroll-long 1.6→1.3（worker 树 1.9→1.3）；text-open 0.1 持平；hash 逐字 |
| W3b value 缓存 | `a90a281` | 901 passed | 不触渲染路径；hash 逐字；单测钉缓存命中 |
| W2 增量窗口索引 | `b89146a` | 905 passed | scroll-long 0.8（组基线 1.6，↓50%）；idle-long（新）0.6–0.7；hash 逐字（5 次） |

W2 诚实记录：`idle-long` 0.6–0.7 未达 `text-open` 0.1 的直通下限，主项是 sweep 每块
`revision()` 探测常数（~2650 块 × Text 快照构建 ≈0.4–0.5 ms）——P5 设计的固有常数，
"更廉 revision 形态"属新课题，不在本组清单（清单 M2 的验收以 scroll-long 大幅下降 +
hash 逐字不变 + 既有测试零修改为准，均已满足）。

## 度量尺（lead 2026-10-22 08:47 实测，我的机器；各波必须复现并贴真实输出）

基线（main `58c5edb`，全绿）：

| 门禁/行 | 基线值 |
|---|---|
| `uv run pytest -q` | **893 passed** in 4.03s |
| `uv run python tools/golden.py --check` | **golden: 57 topics match** |
| `stream-single` / `stream-split` | 0.8 / 4.8 ms/frame |
| `scroll` / `scroll-long` | 0.4 / 1.6 ms/notch |
| `text-open` / `table-open` / `stream-paragraph` | 0.1 / 0.1 / 0.7 ms/frame |
| `replay` | 347 ms total |
| `render-hash` | `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379` |

预期与诚实出口（不许为了数字好看改工作负载）：

- W1：`scroll-long` 应显著下降（≥ 20%）；`text-open` 已在 0.1 ms 的显示下限，**不升即可**，
  若无可见下降属预期（3000 指针的 list 拷贝本就 ~20µs 级），报告如实记录。
- W2：新行 `idle-long` 落地后应接近单 pane 直通的下限；`scroll-long` 在 W1 之上再降；
  其余行与 `render-hash` 不动。
- W3a：`stream-split` 下降；其余行与 `render-hash` 不动。
- W3b：不做 bench 行，以单测断言缓存命中（第二次读 `value` 不再 join）。
- 清单所写"1422 passed / golden 11 页 / apidoc 170 条"是历史口径；**当前**门禁以本表为准。

## 全局不变量

1. 渲染字节零变化（红线 1）；golden 不重录。
2. `Block.rows()` 返回自有拷贝的契约一行不改；`rows_view` 是新增的内部门。
3. 非 Revisioned / `revision() is None` 的块每帧重渲（现状语义），任何缓存不得冻结它们。
4. stick-to-bottom / clamp / reveal 的地址算术行为不变（`core/scroll.py` 本组**零改动**）。
5. worker 不 merge / push / tag / 不 checkout main、不碰主检出与其他 worktree；spec 归
   lead，worker 只写自己名下的 `handoff/` 文件。
6. 遇阻塞即停，写清阻塞点；宁可停下上报，不越界自救。

## Git / worktree 协议

见 spec-team SKILL「Git / worktree 协议」。worktree 在
`C:\Users\shifu\.worktrees\mocode-tui\<分支>`，lead 统一创建销毁；分支从派工时刻最新
main 创建。W2 复用 W1 的 worktree（agent 在其中 `git checkout -b fp-w2-window-index main`，
main 由 lead 合并后已前进）。

## 共享文件所有者

- `tools/framebench.py`：本组只有 W2 动（加 `idle-long` 一行 + docstring 基线段）。
- `docs/DESIGN.md`：W2 改 viewport 段，W3a 改 frame 段（先后，不并发）。
- `CHANGELOG.md`：lead 收尾时统一补一条未发布段（worker 不碰）。
- `core/block.py`：W1 主体；W2 如需微调（索引读 mutation），以 W1 合并后的现实为准。

## 接口索引

见 `ref/interfaces.md`（lead 每波合并后回写）。当前版本 = W1 派工前草案。

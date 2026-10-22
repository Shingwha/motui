# W2 交接包（增量窗口索引 · M2）
> 分支 `fp-w2-window-index` / 起点 main `cbca819` / 2026-10-22（W3b 已先并入 main：`a90a281`，与本波文件级不相交，合并应无冲突；分支 diff 基准取 `cbca819`）

## A. 自动事实

`git diff cbca819 --stat`：恰好 5 个写入范围文件（viewport +380±、test_viewport +104、
framebench +48、DESIGN +11、block docstring ±13）；禁触清单零 diff；`core/scroll.py` 零 diff。

新增/变更接口（全部私有或既有签名）：

- `Viewport` 私有状态 `_BodyIndex`（viewport.py 内私有类，无新公共 API）：键
  `(Document.mutation, width)`；条目 `(block, revision, count)` + 前缀和数组 `_cum`
  （`_cum[i]` = 第 i 条目的 body 起始行）+ body 总高 + pinned 引用 + `block_order`
  tuple（按 mutation 复用同一对象）。入口唯一：`ensure(width)`；窗口定位
  `window_spans(start, end)`（bisect_right）；取行 `entry_rows(block, width)`。
- `layout` / `natural_height` 换到索引上；`ScreenLayout` 输出契约逐字段不变。

基线命令当前真实结果：

| 门禁 | 结果 |
|---|---|
| `uv run pytest -q` | **901 passed**（897 + 4 新增），0 failed |
| `uv run python tools/golden.py --check` | **golden: 57 topics match** |
| `render-hash` | `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`（逐字，连续 5 次） |

framebench 前后对比（W1 树本机基线 → W2 两次隔离全跑）：

| 行 | W1 树 | W2 run1 | W2 run2 |
|---|---|---|---|
| `scroll-long` | 1.3–1.9 ms/notch | 0.9 | 0.8（隔离最优 0.7，**↓≈45–55%**） |
| `idle-long`（新） | — | **0.6** | **0.7** |
| `render-hash` | `a82f7968…` | 同 | 同 |
| `text-open` | 0.1 | 0.1 | 0.1 |

其余行（本机当日背景负载偏高，同批漂移方向一致）：stream-single 0.9–1.0、stream-split
5.1–5.9（基线 4.5–4.9）、scroll 0.5（基线 0.4）、replay 389–430 ms（基线 366–390）——
均为显示精度 0.1 上的整体漂移，无单行超出负载解释；render-hash 与 golden 不受计时影响。

**索引的关键不变量**（改它的人必须保持）：

1. 索引**不跨帧持有行**：`_frame_rows` 每帧 `ensure` 清空——它只服务"无快照块每帧
   render **一次**"（测量与窗口共用同一次 render；没有它，这类块每帧 render 两次，
   且计数与切片可能来自不同 render）。
2. 每帧 render 次数与 W1 前逐类相等：cacheable-干净 0、cacheable-脏 1、无快照 1。
   `tests/core/test_viewport.py` 的新增 4 条钉住了这条（含 `_Counting`/`_Open` 计数替身）。
3. `revision() is None` / 非 cacheable 的条目永远脏：sweep 每帧 `rows_view` 重测；
   cacheable-脏走 `row_count`（render 落进块自身缓存，窗口 `rows_view` 命中）。
4. 脏块只触发**从最脏条目起的 suffix 前缀和重算**（P6）；键变（mutation/width）才全量重建。
5. `block_order` tuple 只在 mutation 变化时重建；width 变化重建条目但复用 ids。

## B. 只存在于脑子里的东西

- **给 W3a 的 viewport 侧现实**：`layout` 每帧仍 O(可见窗口行) 物化 `body_rows`/
  `row_blocks`（list 构建 + `tuple()`，ScreenLayout 构造已被 W1 的 tuple 跳过减负），
  这是 viewport 自己的每帧下限；`idle-long` 0.6–0.7 的主项不是它，而是 **sweep 的每块
  `revision()` 探测**（`Text.revision()` 每次调用构建 4 元组快照，~2650 块 ≈ 0.4–0.5 ms）。
  所以 W3a 的 compose 容器复用**别指望动 `idle-long`**——它的战场是 `stream-split`
  的 plan/table 分配；若未来想把 `idle-long` 压向 text-open 的 0.1 下限，那是"sweep
  探测常数"的课题（比如快照构建更便宜的 revision 形态），属于新立项，不在本组清单内。
- **Frame 的 pane 直通**：compose 对单 pane 无 chrome 的直通路径意味着许多帧
  `layout` 只被调一次——索引的每帧成本就是"一次 ensure + 一次窗口物化"，无重复 sweep。
- **测试替身语义**：`Rows`（tests/testing）无 revision 协议 → 永远脏，适合测重渲；
  `_Counting`/`_Open`/`_WidthShaped`（test_viewport.py 内）带 render 计数，适合测
  "谁被重渲了"。
- **坑**：framebench 计时行对 CPU 竞态敏感（repo-map 已记），本波实测同一代码
  `--frames 20` 紧跟 pytest 跑出 scroll-long 2.1 / idle-long 1.7，隔离复跑立即回到
  0.7 / 0.7——**验收数字必须隔离跑**。
- 未决问题：无阻塞。（观察项，非本波义务：`rows_view` 的返回类型是 `Sequence[Line]`，
  实际总是 list；切片与 `len` 都安全。）

## C. 指针

- `viewport.py:35` 附近 `_BodyEntry` / `:60` 附近 `_BodyIndex`（ensure/几何/maintenance
  三段）/ `Viewport.__init__` 持 `self._index`；`layout` 的窗口循环与 `natural_height`
  是仅有的两个消费方。
- `block.py:378` 附近 `rows_view` docstring（T0 保真：miss 是**替换**缓存对象）。
- framebench：`idle_long_workload`（scroll_workload 与 text_open_workload 之间）+
  `main()` 的 `idle-long` 行 + docstring 末段 W2 基线记录。
- commit：`c841c6a`（T0 docstring）→ `6927511`（T1 索引类）→ `926bfd2`（T2 切换）→
  `850a885`（T3 idle-long）→ `1ca0f6d`（render-once 修复）→ `68c981d`（T4 测试）→
  `78514d7`（T5 docs）。
- W2 的 `docs/DESIGN.md` 段（"Between layouts the viewport keeps a private body
  index…"）归本波；frame 段未动，W3a 自改。
- 稳定区（本波已验证，W3a 不必重读）：`core/scroll.py`（零 diff）、`core/block.py`
  三个门（W1 现实 + T0 docstring）、`core/selection.py`、`app/**`（本波零 diff）。

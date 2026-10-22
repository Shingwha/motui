# W3a 交接包（compose 容器复用与整行单写快路 · M5）
> 分支 `fp-w3a-compose-reuse` / 起点 main `58210f1` / 2026-10-22（T1–T4 全做，T2 落地）

## A. 自动事实

`git diff main --numstat`：恰好 3 个写入范围文件——`docs/DESIGN.md` +16、
`src/motui/core/frame.py` +48/−4、`tests/core/test_frame.py` +82；禁触清单零 diff。

commit 清单：

- `8ad0ad1` frame: reuse the plan and table containers between compositions（T1）
- `73b0035` frame: skip the splice for a row its single write covers whole（T2）
- `81a8a74` frame: pin buffer reuse, resize rebuild, memo hit and full-row fast path（T3）
- `8325b60` docs: describe the compose row memo and the frame's plan buffers（T4）
- 最后一个 commit：本 handoff。

基线 → 波末（同会话同机）：

| 门禁/行 | 开工基线 | 波末（隔离，安静窗口） |
|---|---|---|
| `uv run pytest -q` | 905 passed | **909 passed**（4 新增，既有零修改） |
| `golden --check` | 57 topics match | **57 topics match** |
| `render-hash` | `a82f7968…` | **逐字同**（每次跑都核，全程无一例外） |
| `stream-split` | 5.5 ms/frame | **4.7–5.1**（4 次安静窗口；↓≈8–15%，最优 4.7） |
| `stream-single` / `scroll` | 1.1 / 0.5 | 0.8–0.9 / 0.4–0.5（持平于漂移带内） |
| `scroll-long` / `idle-long` | 0.9 / 0.6 | 0.7–0.9 / 0.6–0.7（持平；W2 的"别指望动 idle-long"应验） |
| `text-open` / `table-open` | 0.1 / 0.1 | 0.1 / 0.1 |
| `replay` | 471 ms | 385–581 ms（漂移带内） |

新增/变更内部形态（全部私有，无新公共 API）：

- `Frame._plan_rows` / `Frame._table_rows`（`__init__` 持空表，紧挨 `_row_memo`）：
  compose 的 plan/table 两层容器升为帧间缓冲。compose 开头：`len == height` → 逐行
  `clear()`；不同/首次 → 重建到新高度。后续填充逻辑零改动（仍 append）；
  `ordered` 的每帧排序构建、`_row_memo` 的整体替换（`fresh`）语义原样。
- compose 非直通分支的单写整行快路：`len(steps) == 1 and x == 0 and take == width`
  → `rows[index] = line`，跳过键构造与 memo 进出。条件逐字对应 `splice_row` 自身的
  `x == 0 and width == frame_width` 早退（frame.py:791-792 `return line`），故逐字节
  等价——这是 T2 以 render-hash/golden 为裁判通过的根本原因，不是巧合。
- pass-through 分支行为零变化（其输出仍是 pane 自己的 layout 对象；plan/table 的
  填充照旧发生，只是容器现在被复用）。

T2 的等价性论证（红线 1 的关键，写给改这段的人）：

1. `splice_row(空白行, line, 0, width, width)` 本就 `return line`（同一对象），
   快路只是不付这次函数调用的钱；
2. memo 路径对该形状原本能给出的也是同值行：键相等 ⟹ steps 里的 Line 值相等
   （`Line.__eq__/__hash__` 按 segments，lines.py:359-365），而 memoized 行由同形
   splice 产出——快路换的只是"落在格子里的行对象"，值不变；
3. 无步行（blank）与多写/部分宽行的路径一行未动。

## B. 只存在于脑子里面的东西

- **测量纪律（本波最重要的一课，下波直接用）**：本机有间歇性背景负载，framebench
  全行一致漂移 2–3 倍。本波坏窗口实测 stream-split 11.3–14.2、idle-long 1.4–1.7、
  replay 986——与 W2 记录的"紧跟 pytest 2.1/1.7"同型。T1 落地后在坏窗口读到
  stream-split 13.5，用 `git stash` 在**同一噪声窗口**复测改动前基线也是 13.5——
  漂移与代码无关，别被它吓住也别拿它邀功。安静窗口的判据：`idle-long ≤ 0.7`、
  `text-open == 0.1`。验收读数前 `sleep ≥ 10s`，读数仍坏就等一会再跑。
- **T1 的真实收益低于 0.1ms 显示精度**（5.5 → 5.5）：省的是 height×2 个小 list 的
  每帧分配，几十 µs 级。可见的降幅全部来自 T2（每行省键 tuple 构造 + 两次 dict
  操作；split 帧的整行大多是单写整行）。若有人问"容器复用怎么没降"，答案在这。
- **T2 改变了"谁持有行"的图景**：单写整行不再进 memo（也不查 memo），这些格子里
  的行对象直接是 pane 布局（`_pane_layouts` 里的 ScreenLayout）的行本体。下一帧
  这些行对象的生死跟着 pane 布局走（viewport 索引每帧清 `_frame_rows`，但
  ScreenLayout.rows 的 tuple 持有它们到下一次 layout 替换 `_pane_layouts` 为止）。
  对 painter 无影响（行是值）；只有做"行对象生命周期"推理时需要知道。
- **新增 4 测的语义**（`tests/core/test_frame.py`，紧跟 lone-pane 测之后）：
  同尺寸改内容（旧行不动、新行生效——容器复用不串帧）；变高重建（3→5→2，无残留
  行）；多 pane + chrome 帧的 memo 命中（连续两次 compose 行对象 `is` 相等——
  依赖 Line 的值相等使键跨帧命中）；T2 行 `is` pane 布局本体行 + 与 splice 产物
  `segments` 相等。
- **测试坑**：`Document.add` 会把组件包成 `Block` 适配器，`document.blocks()[0]`
  不是 `Rows` 本体——要原地改内容，得自己持有 Rows double 再 `doc.add` 它。
- `_marker_chrome` 只有 band 第 0 行画 mark，其余行是 `-`（写期望文本时踩过）。
- 未决问题：无阻塞。

## C. 指针

- `src/motui/core/frame.py`：`Frame.__init__` 的 `_plan_rows`/`_table_rows` 注释块；
  compose 开头的 clear/重建块（含缓冲生命周期注释）；非直通分支 `if len(steps) == 1:`
  快路；compose docstring 的两段新增（单写整行快路 + 缓冲与 memo 的分工）。
- `docs/DESIGN.md`：frame 节（"Frame composition and overlay layers"）compose 段
  之后新增一段，讲 plan 备忘录与帧间缓冲的分工；viewport 节未动（W2 的段落原样）。
- 隔离复测：`uv run python tools/framebench.py`（先 `sleep 10`，核对 idle-long）。
- 稳定区（本波零 diff，后来者不必重读）：`core/block.py`、`core/viewport.py`、
  `core/scroll.py`、`core/painter.py`、`core/lines.py`（只查了 `__eq__/__hash__`）、
  `core/screen.py`、`app/**`、`widgets/**`、`tools/**`。
- 对 lead 回写 interfaces.md 的建议条目：Frame 下【计划·W3a】改为现实——compose
  输出契约不变；`_plan_rows`/`_table_rows` 为帧间缓冲（height 变才重建）；单写整行
  行 = 写入 Line 本体（不进 memo）；memo 键语义与 pass-through 不变。

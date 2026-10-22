# W1 交接包（borrow gates · M1+M3+M4）
> 分支 `fp-w1-borrow-gates` / 起点 main `58c5edb`（组 opening commit `f1c0ca6`）/ 2026-10-22

## A. 自动事实

`git diff main --stat`：恰好 7 个写入范围文件（block 102±、viewport 69±、driver 20±、
gesture 19±、selection 11±、find 7±、test_block +47）；禁触清单零 diff。

新增公开接口（其余签名零变化）：

- `Block.rows_view(width) -> Sequence[Line]` —— cacheable：返回缓存 list **本体**（借用，
  只读，不得改动；Line 不可变可共享）；非 cacheable：返回 render 的原列表（调用方可拥有）。
- `Block.row_count(width) -> int` —— hit 取 `len(cache)`；miss render + 入缓存再取 len；
  非 cacheable 每次 render 取 len。恒等式 `row_count(w) == len(rows(w))`。
- `Document.mutation -> int`（只读属性）—— add/remove 各 +1，单调不复位。
- `Document.blocks()` —— 按 mutation 键缓存 tuple；未变返回**同一对象**，旧快照永不被改。

基线命令当前真实结果（本机，均有两次实跑）：

| 门禁 | 结果 |
|---|---|
| `uv run pytest -q` | **897 passed**（893 既有 + 4 新增），0 failed |
| `uv run python tools/golden.py --check` | **golden: 57 topics match** |
| `render-hash` | `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`（逐字） |

framebench 三行前后对比（基线实跑 → W1 后两次实跑）：

| 行 | 基线 | W1 run1 | W1 run2 |
|---|---|---|---|
| `scroll-long` | 1.9 ms/notch | 1.4 | **1.3**（↓ 26–32%） |
| `text-open` | 0.1 ms/frame | 0.1 | 0.1（不升，符合 overview 预期） |
| `render-hash` | `a82f7968…` | 同 | 同 |

其余行：stream-single 0.8、stream-split 4.5→4.6、scroll 0.4（一次 0.5 属噪声，复跑回 0.4）、
table-open 0.1、stream-paragraph 0.6、replay 352→323/311 ms——均在 ±10% 噪声内。
注意：本机 `scroll-long` 基线实测 1.9（overview 拍板表写 ≈1.6，lead 机器口径），降幅按本机同机对比。

## B. 只存在于脑子里的东西

- **W2 直接可用入口**（索引每帧要调的三样，全部已就位且零拷贝）：
  - `Block.row_count(width)`：每块行数，hit 不 render 不拷贝；
  - `Block.revision()`：值快照（None = 永远脏，与今天语义一致）；
  - `Document.mutation`：索引键 `(mutation, width)` 的新鲜度检查就是一次属性读 + 整数比较。
  - 另：`blocks()` 未变时返回同一 tuple，索引可放心把它当稳定数组持有。
- **`_refresh` 是唯一的 hit/miss 判定**（block.py:408）：三个门共用；它对 cacheable 返回
  缓存本体、对非 cacheable 返回 render 原列表。改 miss 逻辑只改这一处。
- **已知取舍**：非 cacheable 块的 `rows()` 路径从 1 次列表拷贝变 2 次（`_refresh` 拷一次、
  `rows` 再拷一次）——换来三份判定逻辑合一；该路径每次本来就付整次 render（全量重排版），
  一次浅拷贝在噪声以下，未在 framebench 任何行显形。
- **P4 实况确认**：`layout()` 本就传 tuple，M3 实测收益 ≈0；`__post_init__` 的显式
  `type(x) is tuple` 跳过已落（viewport.py:98），docstring 写明归一化只为手构 layout 服务。
- **grep 实况**：`grep -n "\.rows(" src/motui` 现在零命中（repo-map 记的 8 处已全部切换）；
  `block.py` 只剩 `def rows` 定义本身。W2 改动后请更新 repo-map 第 7 节计数。
- **下一波隐含约束**：`rows_view` 的借用契约靠 docstring + 测试钉住（P1，无只读包装类）——
  任何新调用方必须只读；若 W2 索引要持有 `rows_view` 结果跨帧，须重验（缓存列表会在
  下次 miss 被原地 refill）。
- 稳定区照工单未动：scroll/lines/painter/screen、widgets/**、framebench（本波禁改全遵守）。

## C. 指针

- `block.py:353` rows（契约原样）/ `:378` rows_view / `:395` row_count / `:408` _refresh /
  `:454` mutation 计数 / `:497` mutation 属性 / `:523` blocks 缓存。
- `viewport.py:98` __post_init__ tuple 跳过 / `:189` layout 借用 / `:268` natural_height 计数门。
- commit：`e75d880`（T1 门+缓存）→ `d9339eb`（T2 viewport）→ `1e907bb`（T3 行走方）→
  `3e354e0`（mutation 属性补函数体）→ `c8bab7c`（T4 测试 ×4）。
- tests/core/test_viewport.py、test_find、test_gesture、test_selection：零修改全绿
  （抽验 70 passed），render 计数断言未动。

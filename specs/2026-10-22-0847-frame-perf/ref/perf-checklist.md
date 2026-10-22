# motui 性能优化清单

> 日期：2026-10-22
> 基线：main `58c5edb`（1.2.1）——与 mocode 项目 `.venv` 内安装版内容一致（仅行尾差异），下文行号即仓库行号
> 依据：对 `src/motui/core/{viewport,block,frame}.py`、`app/driver.py`、`widgets/textbuf.py` 的逐行阅读，
> 以及 mocode（下游真实消费者）重构时对渲染热路径的实测诊断
> 关联：`specs/2026-10-17-render-cost/`（行缓存与 revision 协议的出身，D1–D13）；`tools/framebench.py`（度量尺）

---

## 一、每帧热路径现状（问题的共同背景）

paint 帧（脏标记 + 30ms 节流，`driver.py:236/1065-1099`）的链条：

```
_paint_at → frame.compose (frame.py:1345-1370)
  → 每 pane: viewport.layout(width, height) (viewport.py:121-237)
      → document.blocks()  ── O(n) tuple 快照           (block.py:457-459)
      → for block in 全部块:  block.rows(width)         (viewport.py:171-183)
            缓存命中 → return list(self._rows_cache)   ── 命中也整表拷贝 (block.py:388)
      → 窗口切片 + ScreenLayout(...)                     (viewport.py:201-237)
          → __post_init__ 把 rows/body_rows/row_blocks/block_order
            再整体 tuple() 一遍                          ── 第二次拷贝 (viewport.py:93-98)
  → 逐行 write plan（有备忘录，这层是好的） → painter.paint(diff)
```

**核心事实：即使画面完全没变、即使块在视口外几千行之外，每一帧也要为文档的每一行付一次
列表指针拷贝（外加第二次 tuple 化）。** 长会话（数万行）下这是 O(总行数)/帧 的固定成本，
是"越用越卡"的框架级根因。render-cost 组的 D1–D13 把"每块的常数"（组件记忆、尾块增量）
压下去了，但这个 O(总行数) 的结构还在——当时也明确把"真窗口化"挂进了遗留清单。

---

## 二、优化清单

### M1 · `Block.rows()` 缓存命中返回整表拷贝 —— 加只读借用门 【P0，低风险，收益最大】

**原因所在**：`block.py:375-393`。缓存命中路径 `return list(self._rows_cache)`——拷贝是
render-cost 组的有意设计（"returned list is a fresh copy the caller owns"），为了调用方可安全
改动返回值。但全部热路径调用方（viewport 布局/高度走、frame 组合、Find、gesture、Selection）
都是**只读**的：布局只 `len(rendered)` 和切片，从不改。于是每帧为"防改动"付全量拷贝。

**优化方向**：加两个内部门，公开契约不变：

```python
def rows_view(self, width: int) -> Sequence[Line]:   # 借用缓存列表，文档注明"不得改动"
def row_count(self, width: int) -> int:              # 只要行数：布局对视口外块、natural_height 用
def rows(self, width: int) -> list[Line]:            # 保持原样：自有拷贝，改值安全的门
```

`viewport.layout`（对视口外块走 `row_count`，窗口内块走 `rows_view`）、`natural_height`
（viewport.py:251，`sum(len(block.rows(w)))` → `sum(row_count)`）、`reveal`/search/gesture/
selection 的行走全部切换。`Sequence` 视图零拷贝；或直接返回缓存 list + docstring 约定。

**是否合理**：合理，且是全清单性价比最高的一项。风险低——只读调用方全在 motui 内部，
公开 `rows()` 语义一行不改；`tests/test_viewport.py:175-196` 的 render 调用计数断言（render-cost
D1 的红线）不受影响，因为 render 仍只在 miss 时调。收益直接体现在 framebench 的
`text-open`（稳态全走命中路径）与 `scroll-long`（3000 行文档的切片路径）两行。

**验证**：`text-open` / `scroll-long` / `render-hash` 三行——前两行应显著下降，第三行必须逐字不变。

---

### M2 · `Viewport.layout` 每帧全块漫游 —— 增量前缀和索引 【P1，中风险，结构性根治】

**原因所在**：`viewport.py:171-183`。每次布局无条件遍历**全部**块以累计总高和构建几何表。
配合 M1 之前，这是 O(全部块 × 各自行数) 的拷贝；M1 之后仍是 O(全部块) 的 revision 比较 +
计数读取 + body/block_order 列表构建——块数几千时每帧仍有可感成本。render-cost 组的遗留
清单里"真窗口化（需要块知道窗口的新协议）"指的就是这一族问题（那是组件级窗口化；
本项是**文档级**的，互补：即便组件记忆全命中，viewport 也要走完全部块）。

**优化方向**：布局记住每块上次的结果 `(revision 值, 行数)`，下一帧：

1. 遍历只做 **revision 等值比较**（值比较，极便宜——下游 mocode 已把全部块的 revision
   改成单调计数器/小元组，等于前提已就绪）；
2. 只有令牌变了的块重新 `rows()`；高度累积改为**增量维护**（Fenwick 树，或"最脏块之后
   重算前缀"的朴素法，追加为主的会话场景里脏块几乎总在尾部，朴素法就够）；
3. 窗口定位在累积高度上**二分**，只物化与 `[offset, offset+vh)` 重叠的块的行切片；
4. `Document` 的 add/remove 本来就过中心点（`block.py:421-455`），顺带维护一个文档
   mutation 计数，M4 的快照复用同享。

**是否合理**：合理，但这是结构性改动，需要单独立项。风险点集中在"同一套计数喂多处"：
scroll 钳制与 stick-to-bottom（`scroll.py`）、row_blocks 所有权表、`natural_height`、
`reveal` 的地址算术、Find/Selection 的行走——全部依赖"每块行数"与"前缀和"。建议照
render-cost 组的波次纪律做：先落 M1（M2 依赖它的 `row_count` 门），M2 的验收以
`scroll-long` 大幅下降 + `render-hash` 逐字不变 + 既有 viewport 测试零修改为门禁。
估计每帧成本从 O(全部块) 降到 O(变化块渲染 + log n 定位 + 可见窗口行)。

**验证**：framebench 建议新增一行 `idle-long`（3000 行 sealed 文档、零变化的稳态帧耗时）——
当前没有任何一行隔离"长文档不变帧"的成本，而它正是 M1+M2 的主战场；该行在本项落地后
应接近单 pane 直通的下限。

---

### M3 · `ScreenLayout.__post_init__` 二次元组化 【P0，极低风险，顺手】

**原因所在**：`viewport.py:93-98`。`layout()` 刚用 list 拼好 rows/body_rows/row_blocks/
block_order，`__post_init__` 又对四者各 `tuple()` 一遍——每帧对全屏行 + 全部块 id 的第二次
全量拷贝。归一化的存在是为了"手构 layout 可以传 list"，但 layout 自己是唯一高产调用方。

**优化方向**：`layout()` 直接构造 tuple 传入；`__post_init__` 里 `type(x) is tuple` 时跳过。
公开契约（"构造接受任意 iterable"）不变。

**是否合理**：合理，纯赢，五行的改动。与 M1 同一波做掉即可。

---

### M4 · `Document.blocks()` 每次调用返回 tuple 快照 【P1，低风险】

**原因所在**：`block.py:457-459`。`tuple(self._blocks)` 每次 O(n) 拷贝，`layout` 与
`natural_height` 每帧各调一次。防的是"遍历中文档被改"。

**优化方向**：`Document` 持 mutation 计数（add/remove 时 +1，与 M2 第 4 步同一机制），
未变时返回同一个缓存 tuple；变了才重建。快照语义对外完全不变。

**是否合理**：合理。单独看收益小（每帧两次 O(n) 的指针拷贝），但机制与 M2 共享，合并做。

---

### M5 · `frame.compose` 每次组合重建 plan/table 分配 【P2，低-中风险】

**原因所在**：`frame.py:1340-1341`。`plan`/`table` 是 `height` 个空 list 的两层列表，
每次组合全新分配——D11 的备忘录防住了**重拼接**（未变行直接拿回组合结果），防不住**分配**。
滚动一行的帧里绝大多数行的 plan 与上一帧相同。

**优化方向**：尺寸不变时复用上一帧的容器（逐行清空改逐行重建），或对"整行单写"的行
（无 chrome 覆写）跳过 plan 构建、painter 直接消费 layout 行。单 pane 直通路径（D11 已有）
推广。

**是否合理**：合理但优先级靠后——在 M1/M2 落地前，这层的分配成本相对小；落地后它会成为
剩余常数的大头，届时再做。`render-hash` 红线同样适用。

---

### M6 · `TextBuffer.value` 每次访问全文 join 【P2，低风险】

**原因所在**：`widgets/textbuf.py:198-199`（`"\n".join(self.lines)`）。O(全文)/次访问。
render-cost D6 已给 TextBuffer 加了单调 `version`，但没有用它缓存 `value`。

**优化方向**：`value` 按 `(version)` 缓存 join 结果，任何编辑置脏。或为"消费方只要增量"
的场景提供行迭代器协议。

**是否合理**：合理，但对 motui 自身 Widget（Editor/Field）收益有限——它们的 revision 已按
version 键走 D6 的 wrap 缓存。主要受益者是**下游每键读 `editor.text` 的宿主**（mocode 的
composer 曾因此每键 O(全文)，已在下游修掉；框架侧补上缓存可以防下一个宿主踩同一个坑）。

---

## 三、已经做对的（勿动）

| 机制 | 位置 | 说明 |
|---|---|---|
| 块级行缓存，键 `(width, revision)` | `block.py:353-393` | 归属正确（随 Block 生灭），命中/未命中语义清晰；唯一缺陷即 M1 的拷贝 |
| `Revisioned` 协议 + 值语义快照纪律 | `block.py:179-215` | 设计正确；"快照代价 ≤ render 的 5%"的约束写得很好——下游 mocode 的 W3b 把全部 revision 落实为计数器，正是这个纪律的回报 |
| compose 计划备忘录 + Line 不可变 | `frame.py:1315-1329` | 滚动帧的未变行直接复用，不重拼接 |
| 30ms 节流 + 脏标记 + pump 唤醒 | `driver.py:236,801-812,1148` | 多次 refresh 合并成一次 paint |
| Markdown 尾块增量（`_StreamCache`） | `widgets/markdown/component.py` | 流式追加只重渲尾块（render-cost D8） |
| `isinstance(Revisioned)` 构造时判一次 | `block.py:303-306` | 免掉每帧每块的协议检查 |

## 四、遗留清单对账（来自 render-cost 组"不做"节）

- **组件级真窗口化**（Table/Tree/Radio 只渲可见行）：与本清单 M2 互补不冲突——M2 是文档级
  （viewport 少走块），组件级是块内部少渲染行。M2 先做，组件级维持挂起。
- **List 前缀跳转索引**（100k 项 4.94 ms/键，P2）：不受本清单影响，维持挂起。
- **Select/Autocomplete description 列记忆、sealed 块 Spinner 冻结**：不变。

## 五、建议落地顺序

1. **第一波**：M1 + M3（+ M4 的 mutation 计数机制预埋）——小改动，把每帧常数砍一个量级，
   公开 API 零变化；验收 = `text-open`/`scroll-long` 显著下降、`render-hash` 逐字不变、
   既有 viewport 测试零修改。
2. **第二波**：M2（依赖 M1 的 `row_count` 门与 M4 的计数）——结构性根治，单独立项，
   波次纪律照 render-cost 组；`idle-long` 基准行随本波进 framebench（只加不改）。
3. **随后按需**：M5（M1/M2 之后它才成为剩余大头）、M6（顺手加固）。

## 六、下游视角的两个事实（供决策参考）

1. mocode 已把全部内容块的 `revision()` 改为单调计数器（快照纪律的模范实现），M2 的
   "revision 等值比较"在真实负载下就是整数比较——前提已铺好。
2. mocode 的 445 个测试用例（含 TUI 风暴/抽验）每天跑在 motui 之上，是 motui 改动的
   现成回归网；motui 自身 1422 passed + golden 11 页 + apidoc 170 条的门禁照旧。

# interfaces · frame-perf 组契约

> lead 维护；每波合并后回写为现实。W1 派工前草案（标注"计划"的尚未存在）。

## Block（core/block.py）

- `rows(width) -> list[Line]` —— 不变：自有拷贝，调用方可安全改动。
- 【计划·W1】`rows_view(width) -> Sequence[Line]` —— 借用缓存列表本身；docstring 契约：
  只读、不得改动（`Line` 不可变可共享）。miss 时 render + 入缓存后返回缓存本体；
  非 Revisioned 组件返回 render 的原列表（无缓存可护）。
- 【计划·W1】`row_count(width) -> int` —— 只要行数；miss 时 render + 入缓存；hit 时
  `len(cache)`。非 Revisioned 组件每次 render 取 len。
- `render(width)` / `revision()` / `pin` / `id` —— 不变。

## Document（core/block.py）

- 【计划·W1】`mutation -> int` —— 公开只读属性；构造为 0，`add`/`remove` 各 +1，
  单调不复位。
- `blocks() -> tuple[Block, ...]` —— 语义不变（调用时刻快照）；实现改为 mutation 键缓存：
  未变时返回同一 tuple 对象，变了才重建。
- `add` / `remove` / `get` / `__len__` —— 签名不变。

## Viewport / ScreenLayout（core/viewport.py）

- `layout(width, height) -> ScreenLayout` —— 输出契约不变（rows/body_rows/row_blocks/
  block_order/offset/total_rows/width/height/viewport_start 的语义与取值）。
- 【计划·W2】内部私有索引：键 `(Document.mutation, width)`；revision `None` 的块永远脏；
  前缀和朴素 suffix 重算；窗口二分定位；`block_order` tuple 按 mutation 复用同一对象。
- `natural_height(width) -> int` —— 语义不变（含 pinned 块的行数总和）。
- `ScreenLayout.__post_init__` —— 公开契约不变（构造接受任意 iterable、归一化为 tuple）；
  实现对已是 tuple 的输入跳过归一化（M3）。
- 滚动 API（scroll_up/down/to/by、scroll_to_bottom、scroll_state、offset、at_bottom）——
  零变化；`core/scroll.py` 本组零 diff。

## 每帧路径的行走方（app/*、core/selection.py）

- 【计划·W1】`driver.py` `_body_address`（:165-166）与 on-screen 检查（:588）→ `row_count`；
  `find.py:286`、`selection.py:295`、`gesture.py:380` → `rows_view`；
  `gesture.py:616/632` → `row_count`。全部只读，行为不变。

## Frame（core/frame.py）

- `compose(width, height) -> ScreenLayout` —— 输出契约不变；【计划·W3a】plan/table 容器
  尺寸不变时复用（逐行 clear 而非重建）；备忘录键语义不变。

## TextBuffer（widgets/textbuf.py）

- `value -> str` —— 语义不变；【计划·W3b】按 `version` 缓存 join 结果。
- `lines` —— 公开可变属性；docstring 增补：直接改 `lines` 不 bump `version`，`value`
  不跟随（P8）。`version` 及全部编辑方法不变。

## framebench（tools/framebench.py）

- 既有 9 行零改动；【计划·W2】新增 `idle-long`（3000 行、零变化、稳态帧耗时）+ docstring
  基线段。

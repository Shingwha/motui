# interfaces · frame-perf 组契约

> lead 维护；每波合并后回写为现实。W1 已合并（`789da41`），其条目为现实；标注"计划"的尚未存在。

## Block（core/block.py）——W1 现实

- `rows(width) -> list[Line]` —— 自有拷贝，调用方可安全改动（契约原样）。
- `rows_view(width) -> Sequence[Line]` —— 借用：cacheable 命中返回缓存 list 本体（只读、
  不得改动、不得跨帧依赖内容一致）；非 cacheable 返回 render 原列表。
- `row_count(width) -> int` —— hit `len(cache)`；miss render+入缓存；非 cacheable 每次
  render 取 len。恒等式 `row_count(w) == len(rows(w))`。
- `_refresh(width)`（私有，block.py:408 附近）—— 三门共用的唯一 hit/miss 判定；miss
  路径**替换**缓存对象（借出的旧列表内容不变，但契约不许跨帧依赖）。
- `render(width)` / `revision()` / `pin` / `id` —— 不变。

## Document（core/block.py）——W1 现实

- `mutation -> int` —— 公开只读属性；构造 0，`add`/`remove` 各 +1，单调不复位。
- `blocks() -> tuple[Block, ...]` —— 调用时刻快照语义不变；按 mutation 键缓存 tuple，
  未变返回同一对象，旧快照永不被改。
- `add` / `remove` / `get` / `__len__` —— 签名不变。

## Viewport / ScreenLayout（core/viewport.py）——W2 现实

- `layout(width, height) -> ScreenLayout` —— 输出契约逐字段不变；经私有 `_BodyIndex`
  （viewport.py 内私有类）工作：键 `(Document.mutation, width)`，条目
  `(block, revision, count)` + 前缀和 `_cum` + body 总高 + pinned 引用 +
  `block_order` tuple（按 mutation 复用同一对象）。入口唯一 `ensure(width)`；窗口定位
  `window_spans`（bisect）；帧级行持有 `_frame_rows`（每帧 `ensure` 清空，保证无快照块
  每帧恰 render 一次）。**关键不变量**：索引不跨帧持有行；每帧 render 次数 cacheable-
  干净 0 / cacheable-脏 1 / 无快照 1（新增 4 测钉住）；revision `None` 永远脏；脏块只
  触发 suffix 前缀和重算，键变才全量重建。
- `natural_height` —— 走同一索引（body 总高 + pinned 计数）。
- `ScreenLayout.__post_init__` —— 公开契约不变；`type(x) is tuple` 输入跳过归一化。
- 滚动 API 与 `core/scroll.py` —— 零变化（本组零 diff）。
- framebench 新增 `idle-long` 行（W2 落地；3000 行零变化稳态 ≈0.6–0.7 ms/frame，主项是
  sweep 每块 `revision()` 探测常数，非窗口物化——压向 0.1 下限属新课题，不在本组清单）。

## 每帧路径的行走方（app/*、core/selection.py）——W1 现实

- `driver.py` `_body_address` / on-screen 检查、`gesture.py` 的计数处 → `row_count`；
  `find.py`、`selection.py`、`gesture.py` 的行走处 → `rows_view`。
  `grep "\.rows(" src/motui` 零命中（只剩定义）。

## Frame（core/frame.py）

- `compose(width, height) -> ScreenLayout` —— 输出契约不变；【计划·W3a】plan/table 容器
  尺寸不变时复用（逐行 clear 而非重建）；备忘录键语义不变。

## TextBuffer（widgets/textbuf.py）——W3b 现实

- `value -> str` —— 语义不变（同样调用序列返回同样字符串）；按 `version` 缓存 join
  结果，两次读之间无写返回**同一 str 对象**；空串 `""` 可正常进缓存（命中判定
  `cached is not None`）。
- `lines` —— 公开可变属性（未改 property，P8）；`value` 与类 docstring 写明：直接改
  `lines` 不 bump `version`，`value` 不跟随。`version` 及全部编辑方法不变；
  `set_text` 无条件 bump、`clear` 有变化才 bump（既有语义）。

## framebench（tools/framebench.py）

- 既有 9 行零改动；【计划·W2】新增 `idle-long`（3000 行、零变化、稳态帧耗时）+ docstring
  基线段。

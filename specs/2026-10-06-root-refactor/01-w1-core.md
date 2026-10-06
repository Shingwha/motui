# Spec root-refactor · 内核整理（波次 W1）

> 分支 `rr/w1-core`；前置：无（与 W2 并行，写入范围不相交）。
> 深读：`specs/2026-10-06-root-refactor/00-overview.md`（总纲，必读）+
> `specs/2026-10-06-root-refactor/ref/audit-core-app.md`（本波权威事实清单）。

## 目标

**core/ 内核一次彻底整理：越权访问修复、隐式数据流显式化、死代码删除、循环依赖消除。
对外行为与渲染字节零变化**——这是最高约束，任何"顺手改进行为"的念头都越界。

写入范围（范围外零 diff）：
- `src/mocode_tui/core/**`（全部文件）
- `tests/test_frame.py`、`tests/test_viewport.py`、`tests/test_block.py`、`tests/test_painter.py`、
  `tests/test_core_text.py`、`tests/test_ansi.py`、`tests/test_style.py`、`tests/test_theme.py`、
  `tests/test_selection.py`、`tests/test_screen.py`

禁触：`src/mocode_tui/` 下 core 之外的一切（app.py/chrome.py/selection.py/widgets/chat/keys/
根 __init__.py）、README、docs、examples、tools。若上游调用点的签名必须保持——**保持**，
本波不改任何产品代码消费的 core 公开签名（`TUI._paint_at` 等调用的都按现状保留）。

## 工单（按序执行，每项一个 commit）

### T1 死代码删除
- 删（core 内）：`Block.set_component`（block.py:80-82）、`Viewport.row_blocks` 属性与
  `Viewport.total_rows`/`viewport_height` 属性（viewport.py:299-322）、`Frame.pane_layouts`
  （frame.py:1174-1182）、`split_rect`（frame.py:198-228，产品路径用 `Split.rects`）、
  `index_at_column`（text.py:187-204）、`Text.theme` 死字段（text.py:488,495-499）、
  `ansi.clear_line()`（保留 `CLEAR_LINE` 常量，删函数出口）。
- 对应测试改走公开路径（如 `Viewport` 的测试改读 `ScreenLayout`）或删除该断言；
  `test_painter.py:63,79` 对 set_component 的使用改为构造新 Block。
- `_ResolvedRange` 内部去重（core/selection.py:81 与 143 重复建 dict；holds 重复 row_range
  的判断；__init__ 裸索引）。纯内部重构，行为不变。

### T2 text ↔ lines 循环依赖消除
- 现状：lines.py:30 顶层 `from .text import ...`；text.py:502 延迟 `from .lines import Line`
  （自认补丁）。
- 动作：把 `Text` 组件（text.py:14 起的类）**迁入 lines.py**；text.py 变为纯测量模块
  （visible_width/wrap_text/wrap_spans/fit 族/index_bounds_at_columns）。
- 全库 grep `core.text import|core import.*Text|from .text import` 同步 import 路径
  （widgets/chat 里如有 `from ..core.text import Text` 之类——**这类上游 import 行不在你
  的写入范围内**：core/__init__.py 的 re-export 属于你，其他包的 import 行属于后续波次。
  因此迁移必须保持 `mocode_tui.core.text.Text` 可达？**不**：正确做法是 core/__init__.py
  的 `Text` 导出改为从 lines 来，并确认没有任何 core 之外的文件直接 `from ...core.text import Text`
  ——先 grep 再动手；若有上游直 import `core.text` 的，把该文件的这一行改动也纳入你的
  commit 并在报告中声明（这是唯一允许的越界行级改动，仅限 import 行）。

### T3 frame.py 内部整理
- **compose/overlay 显式数据流**：消除 `apply_overlays` 循环内反复改写 `self._layout` 的隐式
  协议（frame.py:1231-1235）与 `with_pane_rows` 的逐行 `is` 身份比较特判（1271-1275）。
  方向（可自行细化，行为不变即可）：compose 把产物与"是否 pass-through"作为显式结果记录；
  overlay 应用收敛为一次写回；`pane_layout`/`with_pane_rows` 读显式状态而非逐行比较。
- **chrome 协商缓存**：compose 已算 `_negotiate`（1120），让 `Pane.band()`（452-466）读缓存
  而非重跑 `_negotiate`。注意缓存失效时机与 `revision`（T5）联动。
- **切矩形算法合一**：删 `_spans`+`split_rect`（保留 `Split.rects` 的"余数补给最后一个"语义），
  `_spans` 若仍被内部使用则改为调 `Split.rects` 的算法。
- **越权收敛**：`Pane.close()`（605-610）与焦点读写（649-654）不再直接摸 `frame._panes`/
  `frame._focused_id`——给 Frame 加只读 `panes` 属性与公开 `focus(pane_or_id)`（已存在则复用），
  Pane 走公开面。`Pane.split` 里的 `_adopt` 调用**本波保留原样**（W4 用 revision 机制拆除）。
- 两套 clamp 语义二选一：FrameTable.resolve 的吸附 vs hit_test 的 clamp（audit S0-5）——
  hit_test 在 app.py（禁触），所以只把 FrameTable.resolve 的语义在 docstring 里写清楚，
  不改行为。

### T4 杂项清理
- `Style._prefix` 哨兵修复：`""` 改 `None` 表示"未计算"（style.py:134,142-145），
  使无样式（最常见路径）命中缓存而非每次重算 SGR。渲染字节必须不变。
- `Block._next_auto_id` 的 while 循环（block.py:110-115）改为显式的"候选集推导"，
  行为不变（auto id 永不与显式 id 冲突）。
- viewport 双重 staleness 防抖合一（viewport.py:129-133 与 245-250 二选一保留，
  注释互指消除）。
- tab 归一化单一入口：core 内 lines.py:290 与 text.py:463-464 两处 `replace("\t", " ")`
  收敛为一个共享 helper（core 内部函数，非公开 API）。
- `Line.pad_to`/`Line.filled` 语义文档写清（一个是"补到宽"、一个是"造满宽行"），
  不强行合并调用点（行为保持优先）。
- `Line.fit` 族 docstring 与实现核对（命名 charter：`Line.fit` 是公开面）。

### T5 Frame.revision 基础设施 + 历史注释清扫
- 给 `Frame` 加 `revision: int`（或等价 generation 计数）：任何影响合成结果的 mutation
  （add/remove_chrome、add/remove_overlay、set_band、以及 W4 将要接的 split/close）使
  `revision += 1`。本波只加机制+让 chrome/overlay 注册路径走它，**不改 app.py 的 _retile**
  （W4 的活）——但 `Pane.split` 内部 `_adopt` 的调用点保持工作。
  若 revision 在本波无消费者会导致"死机制"，则**本波不加**，把它完全留给 W4（工单 W4-T1
  已含此步骤）——二选一，报告里声明选了哪个。
- 清扫 core 全部历史包袱注释："since the frame wave"、"the W2 mechanism"、"used to live"、
  "not this wave"（frame.py:593,330）、"W11 palette upgrade"（style.py:165）、theme.py:74/103/127/131
  的旧工具叙述等——改为现在时的设计陈述或直接删除。
- core/__init__.py:37-42 的迁移史叙述删改。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` 零失败（基线 843 passed, 1 skipped；本波允许因删测试变少，禁止失败）。
2. `uv run python tools/framebench.py` 的 `render-hash` 逐字等于
   `5bcfdf164f89ca383194df2b1d3ac168137082220d690d708ba94c20423aba9a`。
3. `uv run python examples/pi_demo.py < /dev/null` 退出码 0。
4. `grep -rn "used to live\|since the .* wave\|not this wave\|W11" src/mocode_tui/core/` 零命中
   （历史叙述清零）。
5. `grep -rn "_adopt\|_focused_id\|frame\._panes" src/mocode_tui/core/frame.py` 中除 Pane.split
   的既有 `_adopt` 外无新增跨类私有访问。

## 禁触清单

core 之外的一切源文件与文档；`tests/` 中除 T1 列出的十个测试文件外的一切；
`tests/_doubles.py`、conftest；pyproject.toml、uv.lock。
唯一例外见 T2（上游文件的 import 行级改动，需报告声明）。

## 最终报告格式

工单状态表（T1–T5 完成/偏差）/ commit 清单（hash+message）/ 自测真实结论（四条命令输出摘要）/
偏差与取舍（含 T5 的 revision 二选一、T2 的越界行清单）/ 未决问题。
阻塞即停：报告阻塞点后停止，不越界自救。

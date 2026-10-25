# W2a 交接 · 渲染契约地基（Surface / Constraints / 裁剪）

> 分支 `2.0/w2a-surface`；起点 `649ea36`（main 与 W1 合并后）。前置：`ref/interfaces.md`、`handoff/W1-kernel.md`。
> 结论：T1–T7 全部完成；**1045 passed**；57 golden 逐字节不变；render-hash 不变；迁移组件全部 `render(c|int) -> Surface`。

## A. 交付面与门禁

### 新签名（实际）
- `kernel/cell.py:Surface`
  - 只读行序列：`__iter__ -> Iterator[Line]`、`__len__ -> height`、`__getitem__(int|slice)`（切片返回 tuple）；`rows` 仍是 tuple。
  - `Surface.of(rows, width, *, pad: bool = True)`：`pad=True` clip+pad（旧行为），`pad=False` 只 clip。
  - `Surface.clipped(rows, width)` = `of(..., pad=False)`，迁移组件的统一返回入口。
  - `__post_init__` 仍只校验 `width >= 0`，不强制 rows 合法（直接构造是内部/测试逃生口）。
- `kernel/layout.py:as_constraints(value: Constraints | int) -> Constraints`
  - `Constraints` 原样返回（同一对象）；`int` -> `Constraints(width=...)`；负数由 `Constraints` 抛 `ValueError`；其他类型 `TypeError`。
  - 只在 `layout.__all__` 公开，**未**加入 `motui.kernel` 根 facade（避免 W2 无谓扩公开面；W5 可上提）。
- `kernel/document.py:Component`：`def render(self, c: Constraints) -> Surface`。
- `Section`：`render/rows/rows_view/row_count/_refresh(width: Constraints | int)`。
  - 行缓存 key 变为 `(width, max_height, revision)`；`rows()` 仍返 `list[Line]`（调用方拥有副本）。
  - `Section.render(width)` 保留为 `rows()` 的便捷入口并返回 `list[Line]`，不进入 `Component` Protocol。
- `Viewport.layout(width, height)` 内部构造 `Constraints(width=width)`；`_BodyIndex` key 改为 `(mutation, Constraints)`；`ensure/entry_rows/_sweep/_rebuild` 全部收 Constraints；`natural_height(width)` 传 `Constraints(width=width)`。滚动算法、offset、行归属零改动。
- `terminal/paint.py:Painter.paint`：行数归一化后、diff/写字节前，`row.width > width` 的行一律 `cut_line(row, 0, width)`（硬裁、无省略号、宽字符不劈开）。
- 迁移组件（全部 `render(self, c: Constraints | int) -> Surface`，内部 `as_constraints` + `Surface.clipped`）：
  - `widgets/text.py:Text`：`max_height` 截断后写入 `_rows`；hover 变换仍作用在副本上。
  - `widgets/layout.py:Row/Column/Spacer/Padding`：子组件仍收 `int`；memo 键仍是 width（不乘 max_height）；`child_at` 几何表不变。
  - `widgets/decor.py:Divider/Panel`：同上；Panel memo/revision/child_at 不变。

### Section 临时适配器（W2c 删除）
- `_render_takes_constraints(component)`：`inspect.signature(type(component).render)`，第二个参数名为 `c`/`constraints`，或注解字符串含 `Constraints` -> 新式；否则旧式。按**类**缓存于 `_TAKES_CONSTRAINTS`。
- 新式：`component.render(c)`；结果 `Surface` 直接用，rows 容错包 `Surface.clipped`。
- 旧式：`component.render(c.width)`，rows 包 `Surface.clipped(rows, c.width)`（只裁不补，字节不变）。
- 两式都强制 `c.max_height` 截断（旧组件看不到该参数；新组件可能超预算）。
- `document.py` 与 `layout.py` 互相 import：`_as_constraints` 用函数内 import 打破循环。

### 门禁实测（2026-10-25，本 worktree）
- `pytest -q -p no:cacheprovider`：**1045 passed**（1019 → +26：T1 6+1 / T2 4+1 / T3 3 / T4 2+1 / T5 4 / T6 2 / T7 2，含 1 处 Spacer 断言改为 list）。
- `tools/golden.py --check`：`57 topics match`；`framebench`：`render-hash a82f7968…` 不变。
- `python -m motui < /dev/null` exit 0 / 70 行；`--pages` exit 0 / 4059 行。
- `grep -rn "def render(self, width" src/motui/widgets/{text,layout,decor}.py` 为空（exit 1）；7 处 render 全部返回 Surface。
- 20 列回归：`tests/kernel/test_render_contract.py` 2 passed；`tui.rows()` 每行 ≤20，Emulator 第 0/1 行无自动换行错位。
- `ruff check .` All checks passed；`pyright` 0 errors；`lint-imports` 4 kept / 0 broken。
- `tools/api.py --check`：`179 names match`（无公开名/构造签名变化，快照零 diff）。
- `tools/growth.py --quick`：pass / pass / OK。

## B. 偏差、取舍与坑

1. **只裁不补**：迁移组件一律 `Surface.clipped`，不做 `Surface.of` 的默认 pad。57 golden 与 hash 因此逐字节不变；pad 的调用留给 W2c。
2. **`Surface.of(pad=True)` 默认保留**：契约仍是“恰好 width”；只有迁移组件显式走 `clipped`。
3. **`Section.render` 返 list**：它是 1.x 便捷入口，不是 Protocol；Protocol 已收窄为 Surface。W2c 收口时一并删除或改型。
4. **适配器按类缓存**：签名由类型固定；用实例会每帧 inspect。测试替身仍写 `render(self, width: int)`，走旧式分支。
5. **`as_constraints` 的位置**：在 `kernel/layout.py`（工单要求），因此不能进 kernel 根 `__all__` 之外的自动导出；`tests/kernel/test_scroll_values.py` 只校验模块导出。
6. **Painter 裁剪时机**：归一化之后、diff 之前，所以 `painter.rows` 也保证 ≤width；非 live 屏同样生效。width=0 时每行裁成 `Line()`。
7. **Surface 不是 list**：依赖 `+`/`append`/`== []` 的调用点会露馅。本波全仓检查过：`demo/shell.py` 只索引/bool，`demo/stage.py` 的 Echo 走 Section 旧式桥；`tests/widgets/test_containers.py` 的 `Spacer.render(...) == []` 已改为 `list(...) == []`。
8. **未迁移清单**（仍 `render(width) -> list[Line]`）：W1 handoff 第 12 条减去本波 7 个类；其中 `Input`、`Markdown`、`Diff`、`List`、`Tree`、`Table` 等由 W2b 迁移，其余容器在 W2c 收口。
9. **`max_height` 的作用域**：只改行数，不参与 memo 键；因此同一容器先大预算后小预算不会互相污染。Panel/Padding 的 `_child_rows` 仍按未截断的 child rows 记录（可见区外不参与命中）。
10. **已知未决**：`Line.clip` 仍是整数硬裁（W2.5）；`ScrollAxis` sticky 前值（W2.6）；`Section.render` 与 `Component.render` 的双形态（W2c）。

## C. 位置与 commit

- `src/motui/kernel/cell.py:625` Surface（`of/clipped/__iter__/__len__/__getitem__`）；`kernel/layout.py:68` as_constraints；`kernel/document.py:39` Component、`:289` Section、`:272` `_render_component` 桥；`kernel/layout.py` `_BodyIndex.ensure`/`Viewport.layout`；`terminal/paint.py:138` paint 裁剪。
- `widgets/text.py:142`；`widgets/layout.py:113/237/307/403`；`widgets/decor.py:148/276`。
- 测试：`tests/kernel/test_render_contract.py`（新增）、`test_surface.py`、`test_scroll_values.py`、`test_document.py`、`test_layout.py`、`tests/terminal/test_painter.py`、`tests/widgets/test_containers.py`、`test_rows.py`、`tests/test_invariants.py`。
- commit：
  - `c0b5f32` kernel: read a surface as a row sequence and normalize render constraints
  - `930d81e` kernel: give sections and the viewport a constraints-aware render seam
  - `47155ab` terminal: clip over-wide rows before the painter writes bytes
  - `d53d57b` widgets: render text into a clipped surface under constraints
  - `7ba908f` widgets: lay out row, column, spacer and padding into surfaces
  - `93b605d` widgets: render divider and panel into surfaces
  - `15cf4a1` test: pin the narrow-screen no-wrap render contract
  - 本文件（最后一个 commit）

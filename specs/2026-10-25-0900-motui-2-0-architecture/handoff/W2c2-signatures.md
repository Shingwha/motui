# W2c2a 交接 · 渲染签名收口（只收 Constraints）

> 分支 `2.0/w2c2-signatures`；起点 `1abf487`（W2c1 合并 `25cb08c` 之后）。前置：`ref/interfaces.md`、`handoff/W2a-surface.md`、`W2b1-views.md`、`W2b2-content.md`、`W2c1-canvas.md`。
> 结论：T1–T5 全部完成；**1113 passed**；57 golden 逐字节不变；render-hash 不变；demo 70/4059 行。

## A. 交付面与门禁

### 最终签名（实际）
- 所有组件：`render(self, c: Constraints) -> Surface`。`Constraints | int`、`as_constraints`、
  `Section._render_takes_constraints/_render_component/_as_constraints` 全部删除；`kernel.layout.__all__`
  不再含 `as_constraints`。
- `Section.render/rows/rows_view/row_count/_refresh` 只收 `c: Constraints`；`render` 仍返回 `list[Line]`
  （工单允许保留的 1.x 便捷入口），`rows` 返回调用方拥有的副本，`rows_view` 借用缓存。
- `Section._render` 是唯一渲染门：`component.render(c)` -> rows，按 `c.max_height` 截断，仅当存在
  超宽行时 `Surface.clipped(rows, c.width)`；正常组件不付第二次裁剪。
- `widgets/base.py:Widget.render(c: Constraints) -> Surface`；`CommandPalette.render(c) -> Surface`，
  `_CommandPalettePanel.render(c) -> Surface`（子组件收 `Constraints(width=c.width)`，合并后按预算截断并 clip）。
- `demo/shell.py:Header.render(c)`、`demo/stage.py:Echo.render(c)`、`examples/snake.py:Snake.render(c)` 均为
  Constraints -> Surface；返回值语义、行内容不变。
- `kernel/layout.py:ScreenLayout.surface -> Surface`：`Surface.clipped(self.rows, self.width)`。
- `terminal/paint.py:Painter.paint(self, target: ScreenLayout | Surface)`：Surface 路径取
  `list(target.rows)` 且按 `target.width` 裁剪；ScreenLayout 路径按屏幕宽度裁剪；行数归一化、diff、
  sync、anchor 全不变。`full` 判定与 `_width/_height` 仍以屏幕尺寸为键，重复 Surface 帧是零字节。
- `app/driver.py` 的 paint 出口改为 `self.painter.paint(layout.surface)`（真实 Surface 路径）。

### 门禁实测（2026-10-25，本 worktree）
- `uv run pytest -q -p no:cacheprovider`：**1113 passed**（基线 1115；删除 3 个 `as_constraints` 用例，
  新增 1 个 `Painter.paint(Surface)` 用例）。
- `tools/golden.py --check`：`57 topics match`；`framebench`：`render-hash a82f7968…` 不变。
- `python -m motui < /dev/null`：exit 0 / **70 行**；`--pages`：exit 0 / **4059 行**。
- `examples/snake.py --headless`：exit 0，`score 0, steps 19, alive False`。
- grep：`def render(self, width` / `Constraints | int` / `as_constraints` /
  `_render_takes_constraints` / `_render_component` / `.render([0-9]` / `.render(width)` 均无命中。
  仅剩 `render(width)` 字面量在 demo 的 `api_line`（3 处）与 `tests/golden/topics/*.txt`（3 处），
  都是金标钉住的展示串，留给 W5 重录。
- `ruff check .` All checks passed；`pyright` 0 errors；`lint-imports` 4 kept / 0 broken。
- `tools/api.py --update`：181 names 写入，**内容无 diff**（该快照只记公开名/构造签名，不记方法签名）；
  `api.py --check` 181 names match。`growth.py --quick`：pass / pass / OK。

## B. 偏差、取舍与坑

1. **codemod 是一次性 AST 脚本**（临时目录，跑完删除，不入库）。只处理属性名恰为
   `render/rows/rows_view/row_count`、单一定位参数、无关键字的调用；跳过 `Constraints(...)` 与
   名为 `c`/`constraints` 的变量；markdown 规则的三参 `render(lines, width, ctx)` 因参数数不符自动跳过。
   为每个改动文件补 `Constraints` import（src 用相对深度、tests/examples 用绝对路径），随后 ruff 排序。
2. **相对 import 深度**：首版脚本按 `len(parts)-1` 生成点数，嵌套两层（`widgets/markdown/`、
   `demo/topics/`）会少一层；已全部手工修正为 `...kernel.layout`。这是 codemod 唯一的系统性错误。
3. **手工修复点**：`autocomplete` 的 `super().render(c.width)` 直接改传 `c`（截断幂等）；
   `CommandPalette` 面板复用同一个 `inner = Constraints(width=...)`；`Section` 的门手工重写。
4. **测试替身的分工保持 1.x**：`tests/testing/doubles.Rows` 与 `test_modal.Panel` 返回**未裁剪**的
   `Surface(width=c.width, rows=...)`，宽度 fitting 仍由宿主做——否则 Panel 的 `fit` 省略号与
   ScrollPanel 的窗口几何会变。`_Oversized` 也故意返回超宽 raw Surface，以继续证明 Section/Painter 守卫。
5. **Surface 断言**：只有真正要求 list 的旧断言改成 `list(surface)`（CommandPalette 空值/切片、
   `Padding`/`Panel` 的容器用例）；其余迭代/索引/len 均无需改。
6. **删除的用例**：`test_as_constraints_normalizes_both_spellings`、
   `test_as_constraints_rejects_negative_width_and_other_types`、`test_layout_exports_as_constraints`
   随 helper 一起删除，因此总数 1115 -> 1113（+1 painter 用例）。
7. **`Painter` 的宽度语义**：Surface 按自身 `width` 裁，ScreenLayout 仍按屏幕宽裁；行数始终归一到屏幕高。
   `_width/_height` 记屏幕尺寸，避免 Surface 宽度与屏幕不同导致每帧全量重绘。
8. **`Section` 仍裁剪/截断**：即使所有组件自己遵守契约，Section 仍是最后守卫（W2a 测试固定该行为）；
   裁剪只在检测到超宽行时运行，golden 路径零额外字节。
9. **未动算法**：渲染、滚动、游标、编辑、markdown、高亮、焦点、demo 页面均未改；只改签名/调用/包装。
10. **未决**：`Section.render -> list[Line]` 的便捷形态与 `Component.render -> Surface` 的双形态可在 W4
    收口；demo 的 `api_line` 旧串与 57 个 `.txt` golden 在 W5 重录时统一。

## C. 位置与 commit

- 源码：`kernel/document.py`（Section 门/缓存）、`kernel/layout.py:surface`、`kernel/selection.py`、
  `terminal/paint.py:paint`、`app/driver.py`、`app/{find,gesture,modal,overlays}.py`、
  `app/command_palette.py`、`widgets/base.py`、`widgets/*.py`、`widgets/markdown/{blocks,tables}.py`、
  `demo/{shell,stage}.py`、`demo/topics/styling.py`、`testing/__init__.py`、`examples/snake.py`。
- 测试：`tests/kernel/*`、`tests/app/*`、`tests/widgets/*`、`tests/terminal/test_painter.py`、
  `tests/test_invariants.py`、`tests/testing/{doubles,layout}.py`。
- commit：
  - `7ba1766` kernel: take constraints as the one render argument
  - `3bb6353` app: pass render constraints through the driver and its overlays
  - `04cf8f9` test: call every render door with constraints
  - `e73801f` terminal: paint a surface as the primary frame target
  - `a3dc8a3` api: close out the constraints-only render contract
  - 本文件（最后一个 commit）

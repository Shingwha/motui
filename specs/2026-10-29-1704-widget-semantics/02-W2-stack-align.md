# W2 · Stack / Align composition

> 分支 `w2.1.2-w1-overlay`（与 W1 同一 worktree；W1 完成后继续）。
> 写入范围：`src/motui/widgets/layout.py`、`src/motui/widgets/__init__.py`、
> `tests/widgets/test_containers.py`。
> 前置：W1 已在本分支合并。最高约束：现有 `Row`/`Column`/`Padding` 行为零变化。

## 目标

补上组合层缺的两件：`Stack`（z 轴合成，交互优先命中）和 `Align`（二维对齐）。
splash 的“文字浮在像素画上”和 components 的 modal 合成在 W6 使用它们。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` §8.1/§8.2 →
  `handoff/W1-<agent>.md` → 本工单。
- 基线命令：

```bash
uv run pytest -q tests/widgets/test_containers.py tests/kernel/test_cell.py
uv run python tools/semantic.py --check
```

- 稳定区（勿重读）：`widgets/decor.py`、`widgets/scroll.py` 的 `child_at`
  实现可参考，但本波不改。
- 已知约束：`Container` 在 `widgets/base.py`；`child_at` 返回
  `(component, row, col)`；命中链由 `motui.kernel.document.descend_chain`
  递归消费；`Widget.children` 赋值会设置 child.parent。

## 工单（按序执行，每项一个 commit）

### T1 `Stack`

- `class Stack(Container)`，构造 `Stack(children, *, theme=None, styles=None)`；
  `children` 顺序是 bottom → top。
- `render(c)`：每个 child 用同一 `Constraints(width=c.width,
  max_height=c.max_height)` 渲染；从底到顶 `top.overlay(bottom)`；最终裁剪到
  `c.width` 和 `c.max_height`（若给）。空 children 返回 `Surface.blank(Size(c.width,
  max_height or 0))`。
- `child_at(row, col)`：从顶层到底层，返回第一个“该点上有可交互节点”的层；
  都没有则返回最顶层包含该点的层；点不在任何层内返回 None。
  - 可交互判定：`clickable`/`focusable`/`hoverable` 任一为 True，或容器在该
    点通过 `child_at` 能找到可交互后代。
  - `Canvas` 这类非交互层不是点击目标；`Padding` 包着 Button 时，命中
    Padding 层（其 child_at 继续下沉到 Button）。
- 只改 `src/motui/widgets/layout.py`。
- 验证：`uv run pytest -q tests/widgets/test_containers.py -k stack`。

### T2 `Align`

- `class Align(Widget)`，构造 `Align(child, *, horizontal="center",
  vertical="middle", theme=None, styles=None)`。
- `horizontal ∈ {"left","center","right"}`，`vertical ∈ {"top","middle","bottom"}`；
  非法值 `ValueError`。
- `render(c)`：child 按完整 constraints 渲染；取实际 `Surface` 的
  `width`/`height`；空白 frame 尺寸 `c.width × (c.max_height or child.height)`；
  按锚点嵌入；超出裁剪。child 撑满时自然看不出对齐，这是 child 的选择。
- `child_at(row, col)`：点落在 child 的实际矩形内才转发，坐标减偏移。
- 只改 `src/motui/widgets/layout.py`。

### T3 导出与测试

- `src/motui/widgets/__init__.py` 导出 `Stack`、`Align`（加 `__all__`）。
- `tests/widgets/test_containers.py` 增加：
  - Stack 的 z 序：顶层字覆盖底层字；空白顶层透明；底层样式透传。
  - Stack 的命中：Button over Canvas → Button；Canvas over Button 但 Canvas
    非交互 → Button；Padding(Button) → Button；都非交互 → 顶层。
  - Stack 的 `max_height=0` 与空 children。
  - Align 的 9 种锚点至少覆盖 left/center/right × top/middle/bottom 的
    代表值、非法值、超出裁剪、`child_at` 偏移。
- 只改上述三个文件。
- 验证：

```bash
uv run pytest -q tests/widgets/test_containers.py
uv run ruff check src/motui/widgets/layout.py src/motui/widgets/__init__.py tests/widgets/test_containers.py --config "exclude=[]"
```

## 验收

1. 全量 `pytest` 全绿（贴用例数/失败项）。
2. `ruff`（含单文件 no-exclude）、`pyright`、`lint-imports` 全绿。
3. `semantic.py --check` 全绿；`framebench.py` 的 `render-hash` 不变。
4. `api.py --check` 会因新增 `Stack`/`Align` 两名而失败——这是预期的；
   不要改 `tools/api-2.1.txt`，在报告里贴出差异，lead 合并后统一更新。

## 禁触清单

`widgets/base.py`、`widgets/decor.py`、`widgets/scroll.py`、`kernel/cell.py`
（W1 已改）、`app/`、`demo/`、`docs/`、`tools/`、`pyproject.toml`。
`handoff/W2-<agent>.md` 是唯一例外。

## 交接包

写 `handoff/W2-<agent>.md`，重点：Stack 命中策略的实现方式、Align 的尺寸
语义、`api.py --check` 的预期差异、给 W6 的使用示例。

## 最终报告

同 W1 模板。

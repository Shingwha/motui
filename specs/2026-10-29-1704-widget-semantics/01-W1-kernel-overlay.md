# W1 · Kernel overlay composition

> 分支 `w2.1.2-w1-overlay`（W2 继续同一分支）；起点 main @ `ca3e53c`。
> 写入范围：`src/motui/kernel/cell.py`、`tests/kernel/test_cell.py`。
> 前置：W0 已提交。最高约束：**只新增公开方法，不改变任何现有渲染字节**。

## 目标

给 `Line` 和 `Surface` 增加按 cell 的叠加组合：透明 cell 保留底层，非透明
cell 以 `base.merge(top)` 覆盖。这是 W2 `Stack` 的渲染基础，也是 splash 文字
浮在像素画上的基础。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` §8.1 → 本工单。
- 基线命令（开工先跑，贴真实输出）：

```bash
uv run pytest -q tests/kernel/test_cell.py tests/kernel/test_surface.py
uv run python tools/semantic.py --check
```

- 稳定区（勿重读）：`src/motui/app/`、`src/motui/widgets/`（本波不改）。
- 已知约束：`Line`/`Surface` 是 frozen 值；`Segment` 是唯一 cell 内容门；
  宽字符在 `Line` 里占一个 glyph + 一个 continuation cell（`char == ""`）；
  `Style()` / `NONE` 是默认样式；`Style.merge(other)` 的 `other` 在顶层。

## 工单（按序执行，每项一个 commit）

### T1 `Line.overlay(base: Line) -> Line`

- 在 `Line` 上新增公开方法，`self` 是顶层，`base` 是底层。
- 透明 cell 定义：`char == " "` 且 `style == Style()` 且 `link is None` 且
  `action is None`。透明 cell 保留底层对应列。
- 非透明 cell：字符、样式、`link`、`action` 都取顶层；样式
  `base_style.merge(top_style)`（底层在前）。
- 结果宽度 `max(self.width, base.width)`；短的一侧按空白补齐。
- 空顶层（`Line()` 或全部透明）返回与 `base` 等值的行。
- 宽字符：顶层覆盖双宽 glyph 的 lead 时整体替换底层 glyph；顶层透明时保留
  整个底层 glyph；绝不产生半个宽字符或悬空 continuation。
- 只改 `src/motui/kernel/cell.py`。
- 验证：

```bash
uv run pytest -q tests/kernel/test_cell.py -k overlay
uv run ruff check src/motui/kernel/cell.py --config "exclude=[]"
uv run pyright src/motui/kernel/cell.py
```

### T2 `Surface.overlay(base: Surface) -> Surface`

- 在 `Surface` 上新增公开方法，`self` 是顶层。
- 结果 `width = max(self.width, base.width)`，`height = max(self.height,
  base.height)`；逐行调用 `Line.overlay`；缺行按空白。
- 结果必须是 `Surface` 值（行宽不超过 `width`），不修改输入。
- 只改 `src/motui/kernel/cell.py`。
- 验证：同 T1 加 `tests/kernel/test_surface.py`。

### T3 测试

在 `tests/kernel/test_cell.py` 增加 overlay 分组（不要新建文件）：

- 底层可见、顶层空白透明：结果 == base。
- 顶层 glyph 覆盖底层 glyph，底层样式字段透传、顶层字段覆盖。
- 顶层只有样式（styled space）也覆盖：底层 glyph 消失、底层 bg 保留。
- `link` / `action` 只在顶层非透明 cell 上覆盖；透明 cell 保留底层 payload。
- 宽度/高度取 max；短行补齐；空顶层 identity。
- 宽字符：覆盖 lead、覆盖 continuation、透明保留整字，三种都不产生半个字。
- `Surface.overlay` 的行数/宽度/逐行行为。
- 只改 `tests/kernel/test_cell.py`。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴用例数/失败项）。
2. `uv run ruff check .`、`uv run pyright`、`uv run lint-imports` 全绿。
3. `uv run python tools/semantic.py --check` 全绿（本波不改渲染路径）。
4. `uv run python tools/api.py --check` 全绿（没有新增 facade 名）。
5. `uv run python tools/framebench.py` 的 `render-hash` 不变（贴数值）。

## 禁触清单

`src/motui/kernel/frame.py`、`src/motui/kernel/layout.py`、`src/motui/widgets/`、
`src/motui/app/`、`src/motui/demo/`、`docs/`、`tools/`、`pyproject.toml`。
`handoff/W1-<agent>.md` 是唯一例外。

## 交接包

完成后在分支最后一个 commit 写 `handoff/W1-<agent>.md`，按 SKILL 的
Handoff 协议：A 节自动事实（diff stat、签名、基线结果）、B 节只存在于脑子里
的东西（偏差、坑、下一波约束）、C 节指针（文件:行号、commit）。

## 最终报告

工单状态表 / commit 清单（hash + message）/ 自测真实结论 /
偏差与取舍 / 交接校验 / 探索审计 / 未决问题。

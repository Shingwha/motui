# W0a · 值类型（不改变行为）

> 分支 `2.0/w0a-values`；前置：main @ `400773b`；写入范围：`src/motui/kernel/**`、`tests/kernel/**`
> 权威：`ref/source/10-waves/W0-harness.md` §3–4.3、`ref/source/02-core-contracts.md` §1–6

## 目标

在**不改变任何生产行为**的前提下，把 2.0 的地基值类型作为独立、被测试锁死的纯值引入：
`Size` / `Pos` / `Rect` / `Axis`（几何）、`Cell` / `Line` / `Surface`（行与帧）、
`WrapMode`（换行策略）、`Constraints` / `ScrollAxis` / `Scroll`（布局与滚动）。

**本波结束：921 个旧用例全绿；57 golden 逐字节不变；`render-hash` 不变；新值类型未被生产代码使用。**

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：
  ```bash
  uv sync --locked
  uv run pytest -q -p no:cacheprovider
  uv run python tools/golden.py --check
  uv run python tools/framebench.py
  ```
- 稳定区（已验收，勿改）：`src/motui/core/**`、`src/motui/widgets/**`、`src/motui/app/**`、`src/motui/demo/**`、`tests/**`（除新增 `tests/kernel/`）、`tools/golden.py`、`tools/framebench.py`。
- 已知坑：
  - `src/motui/{kernel,interaction,keys}/__pycache__` 是旧尝试的未跟踪缓存；建 `kernel/` 前删除这些目录。
  - `core/lines.py:Segment` 的构造是内容门（C0/DEL/C1 删除、tab→空格），新 `Cell` 必须沿用同一规则；不要 import `core`（kernel 不能依赖 1.x core）。
  - `core/frame.py:Rect` 是非 kw_only、无默认值的 dataclass；新 `Rect` 按 2.0 契约是 `frozen/slots/kw_only` 且全默认。
  - `ScrollState` 是可变对象；新 `Scroll`/`ScrollAxis` 是冻结值，操作返回新值。
  - `Line.styled()` 需要构造 SGR/OSC8 字节；kernel 不得构造 terminal 字节。本波**不实现 styled**，只保留 `segments` 视图；W1/W2 在 `terminal/ansi.py` 与 `kernel/paint.py` 的边界上解决（见本工单 T2 的说明）。

## 工单（按序执行，每项一个 commit）

### T1 几何 `kernel/geom.py`

- 新建 `src/motui/kernel/__init__.py`（本波只导出新值；不得 import core/widgets/app/terminal）。
- 新建 `src/motui/kernel/geom.py`：
  - `Size(width=0, height=0)`、`Pos(x=0, y=0)`、`Rect(x=0,y=0,width=0,height=0)`，均 `@dataclass(frozen=True, slots=True, kw_only=True)`。
  - `Rect` 校验：`width/height >= 0`，负数抛 `ValueError`；`right`/`bottom`/`area` 属性。
  - `contains(pos: Pos) -> bool`（右/下开区间）。
  - `intersect(other: Rect) -> Rect`：无交集返回 `Rect()`（全 0），结果恒在两者内。
  - `split(axis: Axis, weights: Sequence[float], min_size: int = 0) -> tuple[Rect, ...]`：
    语义与 `core/frame.py:Split.rects` 一致（按权重 floor 分配、最后一个吃余数、`min_size` 抬升、越界裁剪、children 相接不留缝）。
    `Axis.X` 切宽度（左右），`Axis.Y` 切高度（上下）。
  - `class Axis(Enum): X="x"; Y="y"`。`weights` 为空/全 0/负数抛 `ValueError`。
- 只允许改：`src/motui/kernel/__init__.py`、`src/motui/kernel/geom.py`、`tests/kernel/__init__.py`、`tests/kernel/test_geom.py`。
- 验证：`uv run pytest -q tests/kernel/test_geom.py`；随机化不变量至少覆盖：
  - `intersect` 交换律 + 结果包含于两者；
  - `contains` 的边界（右/下不含）；
  - `split` 面积守恒、相邻相接、每个矩形 `>= min_size`（除非 span 不足）、总和不超出原矩形。
  - 固定用例：`Rect(0,0,10,5).split(Axis.X,(2,1))` 与 `core.frame.Split("vertical",(2,1)).rects(...)` 结果一致。

### T2 行与帧 `kernel/cell.py`

- 新建 `src/motui/kernel/cell.py`：
  - `Cell(char=" ", style=Style(), link=None, action=None)`，`frozen/slots`；构造时过内容门：删除 C0/DEL/C1、tab→空格（与 `core/lines.py:_cells_only` 同一正则语义）；`link` 也过门。
  - `Segment`：从 `core/lines.py` 复制的**独立**实现（不要 import core）；同样的内容门、`width`、`with_style`；`link`/`action` 随行保留。允许先复制，W1 再合并。
  - `Line`：包 `tuple[Segment, ...]`，不可变；提供 `text`/`width`/`segments`/`__eq__`/`__hash__`/`__repr__`/`from_text`。**不实现 `styled()`**（见前置上下文）。
  - `Surface(width=0, rows=())`，`frozen/slots/kw_only`；`height` 属性；
    `Surface.of(rows, width)`：每行 `clip`/补齐到 `width`（短行用空格补齐，超宽行截断），保证 `len(row) <= width`；`Surface.blank(size)`：`height` 行空行。
  - 本波 `Line.clip` 可先实现为最小 `clip(mode_or_width)`：为测试与 Surface.of 服务；W2.5 再统一为 `reflow` 词表。**不要**改 core 的 `Line.fit`。
- 只允许改：`src/motui/kernel/cell.py`、`src/motui/kernel/__init__.py`、`tests/kernel/test_surface.py`。
- 验证：宽度 0/1/2/emoji/CJK；超宽裁剪；短行补齐；控制字符（`\x00`、`\x1b`、`\x7f`、`\x9b`）被删除；tab→一个空格；等值/哈希；`Segment` 的 `link/action` 不参与宽度但被保留。

### T3 文本策略值 `kernel/text.py`

- 新建 `src/motui/kernel/text.py`：只加 `WrapMode` 5 值（`WORD/CHAR/ELLIPSIS/CLIP/OVERFLOW`）与 `str` 值。
- 本波不实现 `reflow`/`_wrap_chars`（W2.5）；不迁移 `core/text.py`。
- 只允许改：`src/motui/kernel/text.py`、`src/motui/kernel/__init__.py`、`tests/kernel/test_wrapmode_values.py`。
- 验证：5 个值的 `value` 稳定；未知值抛 `ValueError`；`WrapMode("word") is WrapMode.WORD`。

### T4 布局与滚动值 `kernel/layout.py`

- 新建 `src/motui/kernel/layout.py`：
  - `Constraints(width=0, max_height=None)`，`frozen/slots/kw_only`；`width >= 0`、`max_height is None or >= 0`，否则 `ValueError`。
  - `ScrollAxis(offset=0, content=0, viewport=0, sticky=False)`，`frozen/slots/kw_only`；纯函数：
    - `max_offset` 属性 = `max(0, content - viewport)`；
    - `clamp()` -> 新值，`offset` 夹到 `[0, max_offset]`；`sticky` 时若旧 `offset >= 旧 max` 则贴底（需要保留“旧 extent”才能完全复刻 `ScrollState.clamp`；本波用 `max_offset` 作为旧 extent 的等价判断，并在测试中固定 1.x 行为）；
    - `reveal(row)` -> 新值（最小移动；内容/视口为 0 时不动）；
    - `thumb(track, min_length=1) -> tuple[int,int] | None`，公式**逐字**复刻 `core/scroll.py:ScrollState.thumb`（含 builtin round 的半偶规则）。
  - `Scroll(x=ScrollAxis(), y=ScrollAxis(sticky=True))`，`frozen/slots/kw_only`；提供 `with_x/with_y` 或 `replace` 用法。
  - 命名：**不要**叫 `Axis`（与 `geom.Axis` 冲突）；用 `ScrollAxis`。在 `kernel/__init__.py` 同时导出 `Axis`（几何）与 `ScrollAxis`。
- 只允许改：`src/motui/kernel/layout.py`、`src/motui/kernel/__init__.py`、`tests/kernel/test_scroll_values.py`。
- 验证：
  - 两轴独立 clamp；
  - `sticky` 只影响 y 的默认值；
  - `thumb` 与 `core.scroll.ScrollState` 在 1.x 测试数据上逐值一致（直接用 1.x 的 `ScrollState` 做对照，不改它）；
  - `reveal` 的上/下/已可见/空内容/空视口 5 种路径。

### T5 包导出与测试收口

- `src/motui/kernel/__init__.py` 只导出：`Axis, Size, Pos, Rect, Cell, Segment, Line, Surface, WrapMode, Constraints, ScrollAxis, Scroll`。
- `tests/kernel/test_kernel_imports.py`：断言 `import motui.kernel` 后 `sys.modules` 中没有 `motui.core`/`motui.widgets`/`motui.app`/`motui.terminal`。
- 只允许改：`src/motui/kernel/__init__.py`、`tests/kernel/test_kernel_imports.py`。
- 验证：`uv run pytest -q tests/kernel`。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（旧 921 + 新 kernel 用例；贴真实数字）。
2. `uv run python tools/golden.py --check` → `57 topics match`。
3. `uv run python tools/framebench.py` → render-hash 仍为 `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`。
4. `uv run python -m motui < /dev/null` exit 0；`--pages` exit 0。
5. `grep -rn "motui.kernel\|from .kernel\|from ..kernel" src/motui --include=*.py | grep -v "^src/motui/kernel/"` 为空（新值未被生产代码使用）。
6. `git diff --stat` 只含写入范围内的文件。

## 禁触清单

`src/motui/core/**`、`src/motui/widgets/**`、`src/motui/app/**`、`src/motui/demo/**`、`src/motui/__init__.py`、`src/motui/testing.py`、`tests/core/**`、`tests/widgets/**`、`tests/app/**`、`tests/golden/**`、`tools/golden.py`、`tools/framebench.py`、`pyproject.toml`、`uv.lock`、`README.md`、`docs/**`、`CHANGELOG.md`。

## 交接包

完成后在分支最后一个 commit 写 `specs/2026-10-25-0900-motui-2-0-architecture/handoff/W0a-values.md`，按「Handoff 协议」模板：A 节给 `git diff --stat` + 新公开签名 + 基线命令真实结果；B 节写偏差（尤其 `Line.styled` 的推迟）、`ScrollAxis` 命名、撞到的语义坑；C 节给关键文件行号与 commit。

## 最终报告

工单状态表 / commit 清单（hash + message）/ 自测真实结论（用例数、失败项）/
偏差与取舍 / 交接校验（无前置 handoff）/ 探索审计（写入范围外读过的文件及原因）/ 未决问题。

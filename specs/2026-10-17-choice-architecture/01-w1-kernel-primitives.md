# Spec choice-architecture · W1 kernel 原语（波次 W1）

> 分支 `arch1-kernel`；前置：无（从合并时刻最新 main 切出）；深读：`00-overview.md`（红线、D1、D6）。
> **最高约束：只加「无策略的纯算术与纯值」——不碰任何组件、不改任何可见输出、不动门禁基线。**
> 目标是把「光标 + 窗口」与「多选标记」两件事在 kernel 层立住，W2 的 `Select`/`List` 与
> `Table`/`List` 多选才好接线。

## 目标

1. `kernel/cursor.py`：`CursorWindow` —— 菜单窗口（`Select._visible_range` 的现行语义）
   与列表窗口（`List` 的居中语义）共用的纯算术。
2. `kernel/mark.py`：`MarkSet`（可变的标记索引集合）+ `mark_prefix`（行首 `[x]`/`[ ]` 渲染）。
3. `kernel/__init__.py` 导出两个名字；对应测试 `tests/test_cursor.py`（新）与
   `tests/test_mark.py`（新），**按行为断言、别按方法凑数**。

## 背景（锚点，全部已核实）

| 事实 | 位置 |
|---|---|
| 菜单窗口语义：光标在前 `cap` 行时窗口挂顶，之后一行一行滚、光标始终是最后一行 | `src/motui/widgets/choice.py` `Select._visible_range`（`cap is None or count <= cap` → `(0, count)`；`cap <= 0` → `(0, 0)`） |
| 列表窗口语义：至多 `window` 行、以光标为**中点**（`index - window // 2` 起，两端钳制） | `src/motui/widgets/list.py`（`_visible` 前的窗口计算） |
| 光标换行/钳制语义：菜单 `wrap=True` 环绕、`False` 钳制；数据视图恒钳制 | `Select.move` / `List.move` |
| kernel 门面与测试分工 | `src/motui/kernel/__init__.py`；`CONTRIBUTING.md` 的 one-module-one-test |
| `visible_width` 量宽助手 | `src/motui/kernel/text.py` |

## 工单（按序执行，每项一个 commit）

### T1 `kernel/cursor.py`：`CursorWindow`

冻结的 dataclass，只有纯函数与纯算术；**不 import 任何 kernel 以外的模块，不 import 组件**：

```python
"""CursorWindow: the pure arithmetic of a cursor and its render window.

One component family -- the menus, the data views -- walks a cursor over a
sequence and renders a window of it.  The two window policies live here
so ``Select`` and ``List`` share one implementation of the arithmetic and
no policy of their own beyond the numbers they pass in.

``cap`` is the window's row budget (``None`` renders every row).  ``center``
picks the policy: the default top-stick window hangs at the top while the
cursor sits inside the first ``cap`` rows, then scrolls one row per step
with the cursor as its last row; a centring window keeps the cursor at
``index - cap // 2`` (clamped at both ends).  Either policy keeps the
cursor row on screen whenever the sequence has one.

The dataclass is a value: every method returns new positions or ranges and
mutates nothing, so a caller can hold one and a component can fold it into
its own state (the components do: ``Select.top`` / ``List``'s arithmetic
that used to be inlined here).
"""

from dataclasses import dataclass

__all__ = ["CursorWindow"]


@dataclass(frozen=True)
class CursorWindow:
    index: int = 0          # the cursor, expected already clamped by the caller-visible setter
    count: int = 0          # the rows the cursor walks
    cap: int | None = None  # the window's row budget; None renders everything
    center: bool = False    # False: the top-stick menu window; True: the centring view window

    def clamp(self, index: int) -> int:
        """The nearest legal cursor for ``index`` (``0`` for an empty set)."""

    def range(self) -> tuple[int, int]:
        """The ``[start, stop)`` slice of rows to render (``(0, 0)`` when empty)."""

    def move(self, delta: int, wrap: bool = True) -> int:
        """The cursor after stepping ``delta``; wrapping or clamping at the ends."""
```

**必须钉死的边界**（写进 docstring 并在测试里各断言一次）：

- `count == 0`：`clamp → 0`、`range → (0, 0)`、`move → 0`（原地）。
- `cap is None or count <= cap`：`range → (0, count)`（无论 center）。
- `cap <= 0`：`range → (0, 0)`。
- 顶挂策略（center=False，与现行 `Select._visible_range` 逐字节等价）：
  `index < cap` → `(0, cap)`；否则 `(index - cap + 1, index + 1)`。
- 居中策略（center=True，与现行 List 窗口等价）：`start = min(max(index - cap // 2, 0), count - cap)`、
  `stop = start + cap`；`count <= cap` 时仍走「全量」分支。
- `cap` 大于 `count`、等于 1、`index` 超出 `[0, count)`（防御：先 `clamp` 再算）。

`move(delta, wrap)`：`wrap=True` → `(index + delta) % count`；`False` → 钳制；均返回新值，空集返回 0。

### T2 `kernel/mark.py`：`MarkSet` + `mark_prefix`

```python
"""MarkSet: the multiple-selection marking of a data view's rows.

A marked view (``Table`` / ``List`` / the multi-select choice family) holds
raw row indices -- the view's own data-row numbering, never rendered rows --
and the mark survives re-sorting or re-filtering because the host owns the
reorder and can re-map the set.  Two glyphs carry the mark: ``[x]`` marked,
``[ ]`` unmarked -- the checkbox pair, three columns wide, which the views
prefix to the row's own text through ``mark_prefix``.
"""

__all__ = ["MarkSet", "mark_prefix"]

#: The two marked-row prefixes (the checkbox glyph pair, three columns).
MARKED = "[x]"
UNMARKED = "[ ]"


class MarkSet:
    """A mutable set of raw row indices; ``toggle`` is the one gesture."""

    __slots__ = ("_index",)

    def __init__(self, marked: Iterable[int] = ()) -> None: ...
    def __contains__(self, index: int) -> bool: ...
    def __iter__(self) -> Iterator[int]: ...   # docstring 写明：迭代按升序的副本
    def __len__(self) -> int: ...              # determinism: sorted copy + int
    def toggle(self, index: int) -> bool:
        """Flip ``index``'s mark; answer the new state (``True`` = now marked)."""
    def clear(self) -> bool:
        """Drop every mark; answer whether anything was dropped."""
    def __repr__(self) -> str: ...


def mark_prefix(marked: bool) -> str:
    """The three-column row prefix: ``"[x] "`` / ``"[ ] "``."""
```

**钉死的语义**：`toggle` 返回**新状态**（`True` = 现在被标记）；`clear` 返回**是否有变化**；
迭代按**升序副本**（渲染确定性）；重复项、负索引不校验（视图自己钳制）。

### T3 门面与测试

- `kernel/__init__.py`：在「the primitives」组里加 `CursorWindow`、`MarkSet`、`mark_prefix`
  （段注释一句话说明），`__all__` 加三名（检查该文件的 `__all__` 列法）。
- `tests/test_cursor.py`（新）：一个文件覆盖 `CursorWindow`。
  - 行为断言：空集三分支；全量分支（cap None / cap ≥ count）；`cap <= 0`；顶挂策略的
    三个位置（`index=0`、`index=cap-1`、`index>=cap`，用 `count=20, cap=6` 走一遍
    `move` 序列并断言窗口逐步移动）；居中策略同参数下 `index=0/2/10/19` 的 `(start, stop)`；
    `index` 越界先钳制；`move` 的 wrap/clamp 两态与空集。
  - 不写「构造默认值」这类填充用例。
- `tests/test_mark.py`（新）：`MarkSet` 的 toggle 返回新状态、clear 返回值、迭代升序、
  `in`/`len`；`mark_prefix(True/False)` 的字符串与 `visible_width == 3`。

## 验收（完成前自测，报告给真实结论）

1. `uv run pytest -q` 全绿（贴真实输出：passed/skipped 数字；基线 1422/1 + 新增用例数）
2. `uv run python tools/golden.py --check` → `golden: 11 pages match`（本波不该动一字节）
3. `uv run python tools/apidoc.py --check` → `apidoc: API.md matches the facades`（kernel 门面
   加了名字，`API.md` 需 `--write` 重生成；**同 commit 完成**）
4. `uv run python tools/framebench.py`：render-hash 与基线逐字符一致
   `de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122`
5. `git status` 干净、`git log --oneline` 三个 commit（或按你实际粒度）

## 禁触清单

`src/motui/widgets/**`、`src/motui/interaction/**`、`src/motui/demo/**`、`src/motui/app.py`、
`src/motui/chrome.py`、`tests/**`（除 `tests/test_api_root.py` 里 kernel 门面名单的同步改动、
新建的两个测试文件）、`docs/**`（除 `docs/API.md` 的 `--write` 产物）、`tools/**`、`pyproject.toml`。

## 最终报告格式

工单状态表 / commit 清单（hash + message）/ 自测真实结论（逐条命令与输出）/
偏差与取舍 / 未决问题。阻塞即停，不越界自救。

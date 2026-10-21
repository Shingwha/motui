# W2 · Label strips

> 分支 `cleanup/w2-label-strips`；起点 `main`（W1a/W1b 已合并）；写入范围见下。

## 目标

把 `Tabs` 与 `MenuBar` 中逐行相同的状态、光标动词、命中表与渲染骨架收敛到新的私有
模块 `src/motui/widgets/strip.py`；`NavList` 复用其中的钳制光标动词。

最高约束：**渲染字节、公开构造签名、`revision()` 快照零变化**。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W1b-widget-rows.md`
  → 本工单。
- 基线命令（开工先跑，贴真实输出）：

```bash
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  -m pytest -q -p no:cacheprovider
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  tools/golden.py --check
```

- 上一波交付摘要：`BandedRows` 已在 `widgets/bands.py`；`NavList` 已继承
  `(BandedRows, Themed)` 并删除 `_band`/`_rest`；`choice.py` 已有 `_FormGroup`。
- 稳定区（勿重读）：`app.py`、`kernel/`、`interaction/`、`demo/`、`tests/`、
  `widgets/{bands,choice,list,tree,table}.py`。
- 已知约束：worktree 必须用上面的 `PYTHONPATH`；Windows 下 `--pages | head`
  会因管道提前关闭报 `Errno 22`，验收请重定向到文件。

## 工单（按序执行，每项一个 commit）

### T1 `ClampedCursor`

- 新增 `src/motui/widgets/strip.py`：
  - `class ClampedCursor`，`__slots__ = ()`；
  - 声明 `_index: int`、`_disabled_items: frozenset[int]`、`disabled: bool`；
  - `index` 只读属性；
  - `select(index)`：disabled/空序列拒绝；钳制到 `0..len-1`；目标 disabled 拒绝；
    返回是否改变。
  - `move(delta)`：disabled/空/`delta == 0` 返回 `False`；按方向逐步跳过
    `_disabled_items`，边界钳制不循环；返回 `self.select(target)`。
  - `_entries` 为子类必须实现的只读属性（返回标签序列）。
- 只允许改：`src/motui/widgets/strip.py`。
- 验证：`python -c "import motui.widgets.strip"`。

### T2 `LabelStrip`

- 同文件新增 `class LabelStrip(ClampedCursor, Themed)`，`__slots__` 持有：
  `_disabled_items`、`_hover_index`、`_index`、`_last_width`、`_spans`、
  `disabled`、`divider`、`focused`、`hover`、`theme`。
- 从 Tabs/MenuBar 原样搬入（行为逐字节一致）：
  - `click(row, col)`；
  - `hover_at(row, col)`（`row < 0` 清除标记）；
  - `_hit(row, col)`（只有 row 0 命中）；
  - `_label_at(col)`（首次命中前用 `_last_width` 建一次 span 表并缓存）；
  - `_spans_of(line)`（按 `_entries` 的标签文本走 segment）；
  - `render(width)`（记录 `_last_width`，调用 `self._layout(width)`，记录 `_spans`，
    返回 `[line]`）；
  - 抽象 `_layout(width) -> tuple[Line, tuple[tuple[int, int, int], ...]]`。
- `__all__ = []` 或只导出 `ClampedCursor`/`LabelStrip` 中的私有名？本模块是内部模块，
  不加入 `motui.widgets.__all__`；模块内 `__all__` 可写两个类名。
- 只允许改：`src/motui/widgets/strip.py`。
- 验证：`pytest tests/widgets/test_navigation.py -q -p no:cacheprovider`
  （此时尚未接线，应保持 824 基线）。

### T3 Tabs 与 MenuBar 接线

- `src/motui/widgets/tabs.py`：
  - `class Tabs(LabelStrip)`；
  - `__slots__` 只留 `_active_style`、`_disabled_style`、`_divider_style`、
    `_hover_style`、`_inactive_style`、`_indicator_style`、`tabs`；
  - 构造函数仍设置全部公共属性与私有状态（可直接保留现有赋值，删除与基类重复的
    方法）；
  - `_entries` 返回 `self.tabs`；
  - 保留 `_layout`、`revision`、`__repr__`、`UNDERLINE`。
- `src/motui/widgets/menubar.py`：
  - `class MenuBar(LabelStrip)`；
  - `__slots__` 只留 `_active_style`、`_disabled_style`、`_divider_style`、
    `_hover_style`、`_inactive_style`、`_pending`、`items`；
  - `_entries` 返回 `self.items`；
  - 保留 `_style_of`、`_layout`、`activate`、`take_result`、`revision`、`__repr__`；
  - 新增 `move` 覆盖：调用 `super().move(delta)`，仅当返回 `True` 时
    `self._pending = None`，然后返回原值。
- 只允许改：`widgets/tabs.py`、`widgets/menubar.py`。
- 验证：

```bash
pytest tests/widgets/test_navigation.py tests/widgets/test_menubar.py \
  -q -p no:cacheprovider
```

### T4 NavList 复用光标动词

- `src/motui/widgets/navlist.py`：
  - `class NavList(BandedRows, ClampedCursor, Themed)`（MRO 必须让 `BandedRows`
    的 `_band` 仍可用；`ClampedCursor` 只提供 `index`/`select`/`move`）；
  - `_entries` 返回 `self.items`；
  - 删除 `index`、`select`、`move` 三个副本；
  - 保留 `click`、`hover_at`、`_plan`、`_rest` 调用、分组行逻辑、`revision`。
- 只允许改：`src/motui/widgets/navlist.py`。
- 验证：`pytest tests/widgets/test_navigation.py -q -p no:cacheprovider`。

## 验收

1. 全量门禁：

```bash
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  -m pytest -q -p no:cacheprovider
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  tools/golden.py --check
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  tools/framebench.py
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  -m motui --pages > /tmp/pages.txt
```

2. `824 passed`、`58 topics match`、`render-hash` 等于
   `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`。
3. 抽验：`test_navigation.py`、`test_menubar.py` 全绿；`Tabs.revision()` 与
   `MenuBar.revision()` 的元组顺序、值一字未变。

## 禁触清单

- `tests/`、`tests/golden/`、`pyproject.toml`、`uv.lock`、`app.py`、`kernel/`、
  `interaction/`、`demo/`、`widgets/{bands,choice,list,tree,table}.py`。
- 不得运行 `tools/golden.py --update`。
- 不得 merge / push / tag / checkout main。
- 不新增兼容 shim、别名或转发模块；`strip.py` 不加入 `motui.widgets.__all__`。

## 交接包

最后一个 commit 写 `handoff/W2-label-strips.md`，按 A/B/C 模板。重点写：
`LabelStrip` 的契约、Tabs/MenuBar 的 slot 变化、`MenuBar.move` 的 pending 规则、
NavList 的 MRO 顺序、`revision()` 未动证据。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验 / 探索审计 / 未决问题。

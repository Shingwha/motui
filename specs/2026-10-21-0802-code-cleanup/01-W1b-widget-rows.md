# W1b · Row bands and form groups

> 分支 `cleanup/w1b-widget-rows`；起点 `main`；写入范围见下。

## 目标

把 `List` / `Tree` / `NavList` / `Select` 各自复制的 `_band` / `_rest` 收敛到
`widgets/bands.py` 的一个 mixin；把 `RadioGroup` / `CheckboxGroup` 的重复表单规则
收敛到 `choice.py` 的一个私有基类；删除 `Table._rest` 包装。

最高约束：**所有组件的渲染字节与 `revision()` 快照不变**。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → 本工单。
- 基线命令：

```bash
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  -m pytest -q -p no:cacheprovider
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  tools/golden.py --check
```

- 稳定区（不要重读）：`interaction/`、`app.py`、`demo/`。
- 当前重复点（main，行号仅供定位）：
  - `widgets/list.py:490` `_band`、`:506` `_rest`
  - `widgets/tree.py:462` `_band`、`:479` `_rest`
  - `widgets/navlist.py:443` `_band`、`:453` `_rest`
  - `widgets/choice.py:631` `Select._band`、`:648` `_rest`
  - `widgets/choice.py:916` `RadioGroup._band`、`:1075` `CheckboxGroup._band`
  - `widgets/table.py:860` `_row_band`、`:879` `_rest`

## 工单（按序执行，每项一个 commit）

### T1 `BandedRows` mixin

- `src/motui/widgets/bands.py`：
  - 新增 `BandedRows`，`__slots__ = ()`，类型注解 `bands: RowBands`、`focused: bool`；
  - `_band(current, hovered, disabled=False)` 只调用 `resolve_band(...)`；
  - `_rest(line, width, current=False, hovered=False, disabled=False)` 只调用
    `rest(line, width, self._band(...))`；
  - 在模块 docstring 里加两句说明：这是行视图的唯一渲染半实现；
  - `__all__` 加 `"BandedRows"`。
- 只允许改：`src/motui/widgets/bands.py`。
- 验证：`pytest tests/widgets/test_bands.py -q -p no:cacheprovider`（若该文件不存在，
  用 `tests/widgets` 全量）。

### T2 四个行视图继承 mixin

- `List(Themed)` → `List(BandedRows, Themed)`，删除 `_band` / `_rest` 两个方法及
  只被它们使用的 import（保留仍被 `_row` 等使用的 `Style` / `rest` 判断：
  删除后若 `resolve_band` / `rest` 不再被本文件引用，一并从 import 行删掉）。
- `Tree` 同上。
- `NavList` 同上；其 `_band` 原本传 `disabled=False`，mixin 默认值等价，直接删除。
- `Select` 同上；`_row` 里对 `self._band(...)` 的调用保持原样。
- 只允许改：`widgets/list.py`、`widgets/tree.py`、`widgets/navlist.py`、
  `widgets/choice.py`。
- 验证：

```bash
pytest tests/widgets/test_navigation.py tests/widgets/test_rows.py \
  tests/widgets/test_choice.py -q -p no:cacheprovider
```

### T3 `_FormGroup` 私有基类

- `src/motui/widgets/choice.py`：
  - 新增 `_FormGroup(Select)`（`__slots__ = ()`），承载：
    - `labels` 属性；
    - 表单 band 规则：`hover` > (`current and focused` → `active`) > `ground`；
    - `_apply_form_bands(hover_style, active_style)`：把两个显式参数覆盖到
      `self.bands`（用 `replace`），供两个子类构造期调用。
  - `RadioGroup` / `CheckboxGroup` 改为继承 `_FormGroup`，删除各自的 `labels` 与
    `_band`，构造期的 overrides 字典改为调用 `_apply_form_bands`。
  - 两个子类仍保留各自的 `_row`、`_revision`、`__repr__`、`click`（Checkbox）。
- 只允许改：`src/motui/widgets/choice.py`。
- 验证：`pytest tests/widgets/test_choice.py -q -p no:cacheprovider`。

### T4 删除 `Table._rest` 包装

- `src/motui/widgets/table.py`：删除 `_rest(line, width, band)`；`render` 中
  `self._rest(line, width, band)` 改为 `rest(line, width, band)`。
- 保留 `_row_band`（它负责 disabled 判定，和 mixin 的通用规则不同）。
- 只允许改：`src/motui/widgets/table.py`。
- 验证：`pytest tests/widgets/test_data.py -q -p no:cacheprovider`。

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
  -m motui --pages
```

2. `824 passed`、`58 topics match`、`render-hash` 不变。
3. 抽验：`tests/widgets/test_navigation.py`、`test_choice.py`、`test_data.py`、`test_rows.py`。

## 禁触清单

- `tests/`、`tests/golden/`、`pyproject.toml`、`uv.lock`、`app.py`、`kernel/`、
  `interaction/`、`demo/`、`widgets/{tabs,menubar,strip}.py`。
- 不得运行 `tools/golden.py --update`。
- 不得 merge / push / tag / checkout main。

## 交接包

最后一个 commit 写 `handoff/W1b-widget-rows.md`，按 A/B/C 模板。重点写：
`BandedRows` 的签名、哪些 import 被删、`_FormGroup` 的 band 规则与 `revision()` 是否
一字未动、Table 的调用点替换。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验 / 探索审计 / 未决问题。

# W1b handoff · row bands、form groups 与 Table 行带调用点

## A · 交付

分支 `cleanup/w1b-widget-rows`，起点 `main`（`fee2a9b`）。最终 commit 为
`specs: hand off the W1b widget-row cleanup`；此前四个实现 commit（按序）：

| commit | 内容 |
|---|---|
| `394255e` | `widgets: add the shared BandedRows mixin` |
| `b565aaf` | `widgets: inherit the shared row-band mixin in the row views` |
| `2ef8bb2` | `widgets: share the form-group labels and band rule` |
| `768afda` | `widgets: call the shared row helper directly in table` |

`git diff --stat fee2a9b...HEAD`（handoff 前）：6 files changed, 93 insertions(+),
216 deletions(-)，全部在允许的 6 个文件内；禁触清单零 diff。

新增/变更：

```python
widgets.bands: class BandedRows          # mixin, __slots__ = ()
  bands: RowBands; focused: bool
  _band(current, hovered, disabled=False) -> Style    # 只调 resolve_band
  _rest(line, width, current=False, hovered=False, disabled=False) -> Line
                                                      # 只调 rest(..., self._band(...))
```

- `bands.__all__` 加 `"BandedRows"`，模块 docstring 增补两句“唯一行视图渲染半实现”；
  `motui.widgets.__all__` 与根 `__all__` 未动。
- `List` / `Tree` / `NavList` / `Select` 改为 `(BandedRows, Themed)`，删除各自
  `_band` / `_rest`；调用点 `self._rest(...)` 原样保留。四个文件只删
  `resolve_band`、`rest` 两个 import（`RowBands`、`Style` 仍被签名/注解使用）。
- `choice.py` 新增 `_FormGroup(Select)`（`__slots__ = ()`）：`labels` 属性、
  表单 band 规则 `hover > (current and focused → active) > ground`、
  `_apply_form_bands(hover_style, active_style)`（`replace` 覆盖 `self.bands`）。
  `RadioGroup` / `CheckboxGroup` 改为继承并删除各自 `labels`/`_band`，构造期调用
  `_apply_form_bands`；各自的 `_row`、`_revision`、`__repr__`、Checkbox 的 `click` 保留。
- `Table` 删除 `_rest` 包装，`render` 与 `header_line` 两处改为直接
  `rest(line, width, band)`；`_row_band` 原样保留，三个 band import 全保留。

`revision()` 一字未动：`_revision`/`revision` 无 diff；两个表单组仍以
`(*super()._revision(), self.empty, self.filled)` 结尾；`_apply_form_bands` 在构造期、
任何 render 之前改写 `self.bands`，快照值与旧 overrides 结果相同。

真实验收（最终 commit 前）：

- `pytest -q -p no:cacheprovider`：**824 passed**（基线 824，零增减）。
- `tools/golden.py --check`：**golden: 58 topics match**。
- `tools/framebench.py`：`render-hash f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`，
  与 `fee2a9b` 基线逐字节相同（基线由 `git archive fee2a9b` 导出到 `/tmp` 后跑同一
  framebench 得到，未触碰主检出/其他 worktree）。
- `python -m motui --pages </dev/null`：exit 0，4130 行输出。
- 抽验：`test_navigation.py`+`test_rows.py`+`test_choice.py` 72 passed；
  `test_choice.py` 41 passed；`test_data.py` 45 passed；`test_bands.py` 8 passed。

## B · 偏差、踩坑与约束

- **T2 中间态签名**：`Select` 继承 mixin 后，继承的 `_rest` 向 `_band` 传 `disabled`，
  而两个表单组当时仍覆写两参 `_band`。为保证 T2 单独成 commit 时全绿，T2 临时加
  `disabled=False`（忽略）；T3 删除覆写后临时参数消失，不是遗留 shim。
- **T4 有两处调用点**：工单只点名 `render`，但 `header_line` 也调用 `self._rest`
  （pinned header 与表格逐字节一致的原因），故两处都替换；`_row_band` 不动。
- **framebench docstring 的旧基线已过期**：文件内最后记录的 `de48e747…` 与 `fee2a9b`
  实测不符；以起点 commit 实测为准，HEAD 与起点同为 `f872187a…`。
- `NavList._band` 旧实现固定传 `disabled=False`，mixin 默认值等价，调用点零改动。
- 未新增兼容 shim、别名或转发模块；`_FormGroup` 是 choice.py 内部私有基类，不进 `__all__`。
- 未运行 `tools/golden.py --update`，未 merge / push / tag / checkout main。

## C · 关键位置与稳定区

- `bands.py:47`（`__all__`）、`:130`（`BandedRows`）、`:144`（`_band`）、`:148`（`_rest`）。
- `list.py:106`/`:118`、`tree.py:66`/`:104`、`navlist.py:100`/`:105`（import/class）。
- `choice.py:88`、`:137`（Select）、`:780`（`_FormGroup`）、`:799`（`_apply_form_bands`）、
  `:820`/`:948`（RadioGroup/CheckboxGroup）、`:890`/`:1015`（构造期调用）。
- `table.py:110`（import 未变）、`:691`（header_line）、`:857`（render）、`:860`（`_row_band`）。
- 稳定区（未触碰）：`kernel/**`、`app.py`、`keys/**`、`interaction/**`、`demo/**`、
  `tests/**`、`tests/golden/**`、`docs/**`、`pyproject.toml`、`uv.lock`、其余 widgets。

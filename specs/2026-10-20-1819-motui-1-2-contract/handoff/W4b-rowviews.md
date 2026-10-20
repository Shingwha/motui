# W4b handoff · row views、共享行带与 rows/decor revision

## A · 交付

分支 `w4b-rowviews`；最终 commit 为 `widgets: the row band attenuation is dim -- focus stays the theme's focus band`；
此前的实现 commit（按提交顺序）：

| commit | 内容 |
|---|---|
| `2179a94` | `widgets: the row views share one band and one result door -- RowBands, take_result, disabled and CursorWindow` |
| `e2ba2a2` | `widgets: revisioned decor, rows and layout -- sealed blocks follow mutable inputs` |
| `d38ea6f` | `demo: the row views feed take_result -- docs and protocol tests follow` |

`git diff --stat main...HEAD`（handoff 前）：29 files changed, 1795 insertions(+), 697 deletions(-)；无 golden、`docs/CONTRACT.md`、`kernel/**`、`app.py`、`keys/**`、`pyproject.toml`、`uv.lock` 改动。

新增/变更公开签名（本波范围）：

```python
widgets.bands: RowBands(ground, active, hover, dim, text, disabled)   # frozen, slots
  RowBands.from_theme(theme, **overrides); .band(*, current, hovered, focused, disabled)
  rest(row, width, band); resolve_band(bands, current, hovered, focused, disabled)
widgets facade: RowBands
Select/RadioGroup/CheckboxGroup: bands=; Select 的行带改由 RowBands 解析
List: take_result() -> str | None; disabled/disabled_items/disabled_style/bands
Table: take_result() -> int | None; selected_style -> active_style;
       disabled/disabled_items/disabled_style/bands
Tree: 无 take_result; TreeNode.disabled; Tree.disabled/disabled_style/bands;
      cursor_style -> active_style; filter 清 _hover_index
Tabs: active -> index (只读 property); active= -> index=;
      disabled= -> disabled_items=; 新增 disabled: bool; hit 读 render 的 span 表
NavList: active -> index (只读); active= -> index=; disabled= -> disabled_items=;
      新增 disabled: bool; bar_space 改为只读 property; bands
Divider/Panel/Notice/StatusLine/ShortcutBar: revision()
StatusLine/ShortcutBar: left/right/items 构造时复制为 tuple
Row/Column/Padding/Spacer: revision(); Delegate.child_at 拒绝负坐标
```

基线真实结果（Windows，HEAD 待提交 handoff）：

- `uv run pytest -q -p no:cacheprovider`：**1811 passed, 2 skipped**（基线 1777 + 34 新增）。
- `uv run python tools/golden.py --check`：`golden: 11 pages match`。
- `uv run python tools/framebench.py`：render-hash `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`（未变）。
- demo：`python -m motui < /dev/null` exit 0 / 70 行；`--pages` exit 0 / 792 行。
- P0 grep（5 个 row-view 源文件）：零命中。

## B · 偏差、踩坑与约束

- **`RowBands.dim` 的语义**：它是“未聚焦时叠加到 active 带上的衰减 token”，`from_theme` 取
  `theme.dim`；`disabled` token 取 `theme.dim`。这样默认优先级 disabled → hover → current&focused
  active → current 未聚焦 active+dim（active 有 bg 时跳过 dim）→ ground，与旧 `_band` 逐字节一致。
  该字段原名 `focus`，合并前按 lead 要求改名：`Theme.focus` 保持“聚焦控件的 band”，
  `RowBands.dim` 专指行带衰减，两者不再同名。
  `text` 作为宿主 token 保留，但共享 helper 不施加（各家族保留自己的 label style）。
- `Select`/`NavList` 的 disabled 仍是**文字样式**（W4a 既有行为），`_band` 传 `disabled=False`；
  `List`/`Table`/`Tree` 的新 disabled 状态同时绘制 disabled 文字与 disabled 带。
- P0 grep 的字面量 `disabled=` 也被新增的 `band(disabled=...)` 调用命中，故 bands.py 提供位置参数
  helper `resolve_band`；`RowBands.band` 仍保持工单规定的 keyword-only 签名。
- demo 的 `_take_pick` 删除通用 `getattr(component, "chosen")` 回退，但对 interaction 的
  `Modal`/`Palette` 增加**显式 isinstance 分支**读它们的公开 `chosen`（W4a handoff 明确把这两者留给
  W6）；否则 palette 的 pick 不再进 demo 的 echo。`session._read_picks` 的无 resolver 回退同样处理。
- `Tabs._tab_at` 首次 render 前仍会调用私有 `_layout(_last_width)` 一次性建表（不调用 `render`）；
  之后完全读 span 表。P0 测试用 monkeypatch 把 `render` 置为抛错来证明。
- `Table.move` 无 cursor 时仍落在行走方向的第一个 enabled 边（不是 `delta` 步）；`List.home/end`
  也跳过 disabled 行（工单只写了 move，扩展为同一 cursor 规则）。
- W5 必须遵守：`RowBands` 是唯一行带入口；`take_result()` 是唯一结果门；`Tabs/NavList.index`
  只读，移动只经 `select/move`；`disabled_items` 整体替换（内部 frozenset）；demo 的 notes/
  registry/views/shell 文案里的旧名是**渲染内容**，W7 统一，W5 不得改。
- 未决：`Modal`/`Palette.chosen` 仍公开（W6）；docs/COMPONENTS 只改了与本波冲突的条目，整篇归 W7。

## C · 关键位置与稳定区

- `src/motui/widgets/bands.py:44`（RowBands）、`:98`（resolve_band）、`:112`（rest）。
- `src/motui/widgets/list.py:321`（take_result）、`:452`（CursorWindow 窗口）。
- `src/motui/widgets/table.py:526`（take_result）、`:834`（_row_band）。
- `src/motui/widgets/tree.py:300`（filter 清 hover）、`:71`（TreeNode.disabled）。
- `src/motui/widgets/tabs.py:268`（_tab_at 读 span 表）；`src/motui/widgets/navlist.py:262`（bar_space）。
- `src/motui/widgets/decor.py:117/235`、`rows.py:116/177/225`、`layout.py:79/197/267/341`（revision）。
- 稳定区（未触碰）：`kernel/**`（含 cursor.py）、`app.py`、`keys/**`、`kernel/events.py`、
  `tests/golden/**`、`docs/CONTRACT.md`、`pyproject.toml`、`uv.lock`、`widgets/markdown/**`、
  `widgets/{action,autocomplete,combobox,textfield,textbuf,dialog,collapsible,indicators}.py`。

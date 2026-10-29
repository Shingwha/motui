# W5 交接包

> 分支 `w2.1.2-w5-styles` / 起点 main @ `c63cc7c`（W4 全部合并）/ 2026-10-29

## A. 自动事实（命令与代码生成）

`git log --oneline main..HEAD`（7 个 commit）：

```
c7d85df w5: tidy the text field imports and editing test order
deb3e98 w5: re-record the semantic goldens for the control overlays
f2d81ea w5: put the strips, slider and fold section on control overlays
a01a3eb w5: lay every text field row on the control floor
b175a8b w5: carry dialog button roles as ButtonKind
a861afe w5: give buttons a kind floor and one action_band
efba5e0 w5: add the control surface tokens and shrink ControlStyles to overlays
```

`git diff --stat main...HEAD`：24 files changed, 714 insertions(+), 273 deletions(-)（不含本 handoff）。
禁触清单零 diff（`kernel/theme.py` 是工单例外，43+/19-）。

门禁（真实输出）：起点 `257 passed` / `semantic: 9 scenes match`；终点
`pytest -q -p no:cacheprovider` **1834 passed, 2 failed**，唯一失败是
`tests/testing/test_api_tool.py` 的两个用例（读 `api-2.1.txt`，快照由 lead 在 W8 更新）；
`ruff check .` 全绿；20 个改动 py 文件 `--config "exclude=[]"` 全绿；`pyright`
0 errors；`lint-imports` 5 kept；`semantic: 9 scenes match`；`framebench`
render-hash **未变** `e7ca544b...`（原因见 B9）。

Goldens：重录前保存旧副本，逐行比较 `\t` 前文本（31 行/场景）：SGR 变化
components 2 / gallery 1 / layout 1 / themes 3 / 其余 0；**9/9 场景文本不变**。

`api.py --check` 6 行差异（未改快照）：`motui:Button`、`motui.widgets:Button`
shape changed；`motui.widgets:ButtonSpec` shape changed；`motui:DEFAULT_THEME` 与
`motui.kernel:DEFAULT_THEME` shape changed；`+ motui.widgets:ButtonKind`。

## B. 只存在于脑子里的东西

1. **新 token 默认**：`SurfaceStyles.control=surface_raised`、
   `accent=Style(bg=Color("#53c8f0", ansi="bright_cyan"))`、
   `danger=Style(bg=Color("#f2708a", ansi="bright_red"))`、`inactive=surface_inactive`；
   `from_palette` 用 `Style(bg=palette.accent.fg)` / `Style(bg=palette.danger.fg)`
   派生，light 主题不落回 dark 值。
2. **overlay 优先级**：`disabled > pressed > focused > hovered > NONE`；返回可 merge
   的 overlay，不是整条 band。`ControlStyles.base`/`band()` 已删除，无源码消费者。
3. **ButtonKind 映射**：NEUTRAL=`surfaces.control+text.base`；PRIMARY=`surfaces.accent+text.inverse`；
   GHOST=`content.accent`（无底板）；DANGER=`surfaces.danger+text.inverse`；disabled 先
   `text.faint` 再 overlay。`Button.kind` 用 `ButtonKind(kind)`；只导出 `motui.widgets`。
4. **styles 与 action_band**：`action_band` 只收一个 Theme；`Button._resolved_theme()`
   用 `dataclasses.replace` 折入 text/surfaces/controls/content 四个覆盖组，否则
   `styles=` 会被绕过。
5. **Dialog surfaces.raised 未落地**：T3 是条件句，Dialog 内部行现状不着色（fill 为
   NONE），故只改按钮 kind、未新增背景 SGR。W6 若要 raised，在 `_interior_row` 的
   fill/tail 加 `self.group("surfaces").raised`（会改 golden SGR，不改文字）。
6. **字段底板**：`_TextField._field_floor()` 每次 render 算一次；`_on_floor` 把 floor
   放在 segment 之下（`floor.merge(seg.style)`），prompt/caret/selection/placeholder
   的语义色与 reverse 优先级不变；read_only 压倒 hover；focus 不改底板；floor 为
   NONE（flat）时返回原 Line，保持 identity。
7. **Tabs 语义变化**：unfocused 不再把 indicator 从 accent 降为 muted（spec §6）；
   focus overlay 默认含 reverse，focused strip 的 active 是 accent+underline+bold+reverse。
   MenuBar active 现在有 underline，focused 时加 focus overlay；disabled 加 overlay(dim)。
8. **Slider**：括号/后缀也吃 overlay；disabled 先 faint 再 overlay；hover 不再用
   `surfaces.hover`，改用 `controls.overlay(hovered=True)`。
9. **framebench hash 未变**：`hash_workload` 会话只有 Markdown+Scrollbar，不经过本次
   改动的控件；这是预期结果。视觉证据看 semantic 4 个场景的 SGR 变化。
10. **偏差（必读）**：范围外唯一源码无关改动是 `tests/widgets/test_contracts.py`
    删掉 `controls=replace(...base=mark)` 一行（`base` 删除后 TypeError；测试意图仍由
    text/content/rows 覆盖）；`test_contract_text_form.py`/`test_containers.py` 是
    T3/T5 点名。`textfield.py` 顺带修了 3 个既有 lint（F821 `Pos`、E501、I001），零行为变化。

## C. 指针

- Token：`kernel/theme.py:156` SurfaceStyles；`:186` ControlStyles；`:194` overlay；
  `:399` flat；`:467` from_palette。
- Action：`widgets/action.py:56` ButtonKind；`:65` action_band；`:100` Button；
  `:163` Button.render；Checkbox `:253`；Link `:330`。
- Dialog：`widgets/dialog.py:52` ButtonSpec；`:236` _new_button；`:248` _default_index。
- 字段：`widgets/textfield.py:582` _field_floor；`:601` _on_floor；三处 `_rows_for` 均调用。
- 其他：`tabs.py:173` _layout；`menubar.py:164` _style_of / `:181` _layout；
  `indicators.py:403` Slider.render；`collapsible.py:189` render。
- W6：不要再写 `controls.base`/`band()`/`ButtonSpec.danger`；状态一律
  `theme.controls.overlay(...)`；`RowStyles.band` 未动。
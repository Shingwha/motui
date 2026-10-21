# W3 · Widget API 收敛（Widget 基类 / Styles / 构造器瘦身）

> 占位；W2 合并后由 lead 补全「前置上下文」再派工。
> 分支建议 `refactor/1.2-widgets`。

## 目标

新增 `Widget` 基类与 `Styles` 组覆盖；删除 9 个 capability protocol 的公共导出；把每个控件的 4-6 个 `*_style` 参数收进 `styles=`；主题改为 render 时解析，换主题不重建控件；`Select` 的 `multi/marked` 拆分。构造器除 `TUI`/`App` 外不超过 10 参数。

## 范围

- `core/widget.py`（新）、`core/theme.py`、`widgets/**`、`demo/topics/**`、`demo/shell.py`、`tests/**` 中的控件构造。
- 保留所有主题组旋钮；不得删掉某个视觉能力，只是换入口。
- 视觉红线：除 `Select` 拆分导致的显式行为差异外，golden 帧逐字节不变。

## 依赖

W2 已合并。

## 验收

- 全量 pytest、golden、framebench、两个 demo 入口全绿。
- `rg "hover_style|focus_style|disabled_style|ground_style|label_style|cursor_text_style|description_style|title_style|active_style|inactive_style|bar_style|filled_style|empty_style|done_style|todo_style|guide_style|header_style|first_column_style|border_style" src/motui/widgets` 只剩内部字段，不再出现在公共构造器签名。
- 所有控件继承 `Widget` 或显式实现同一 surface；`Component` 仍可独立使用。
- 主题切换后不重建控件即可重绘（headless 抽验）。

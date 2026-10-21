# W2c · Data and content

> 分支 `motui-2/w2c-data`；起点 `main`（W1 已合并）；写入范围见下。

## 目标

把 Table/Decor/Diff/Indicators/Syntax/Markdown 迁移到 role groups。**零视觉变化**：
使用 legacy 值与旧字段等价的 group；不改字形参数（W3 做）。

## 前置上下文

- 必读：`ref/interfaces.md` §3.1/§3.4/§5 → `handoff/W1-core.md`。
- 基线：`uv sync --locked`；896 passed。

## 写入范围

源码：
`widgets/table.py`、`widgets/decor.py`、`widgets/diff.py`、`widgets/indicators.py`、
`widgets/syntax.py`、`widgets/markdown/blocks.py`、`widgets/markdown/nested.py`、
`widgets/markdown/inline.py`、`widgets/markdown/context.py`、`widgets/markdown/component.py`

测试：`tests/widgets/test_data.py`、`test_diff.py`、`test_indicators.py`、
`test_syntax.py`、`test_markdown.py`、`test_containers.py`（如涉及 Panel/Divider）。

## 工单

1. Table：
   - 行带用 `theme.rows.band(...)`；legacy `rows.inactive=DIM` 复现旧 dim。
   - `table_border` -> `theme.borders.grid`；`first_column` -> `theme.text.base`；
     header 默认保持 `theme.text.base`（legacy NONE），**不得**在 W2 改成 muted。
2. Decor：`border` -> `borders.base`；Divider label 用 `text.muted`（旧 `theme.muted`）。
3. Diff：`error` -> `status.danger`；`success` -> `status.success`；`muted` -> `text.muted`。
4. Indicators：`success` -> `status.success`；`dim` -> `text.faint`；
   `hover` -> `surfaces.hover`；`focus` -> `controls.focus`。
5. Syntax：`muted` -> `text.muted`；`accent.fg` -> `content.accent.fg`；
   `success` -> `status.success`；`warning` -> `status.warning`；`code` -> `content.code`。
6. Markdown：
   - headings -> `content.headings`；link -> `content.link`；inline_code -> `content.inline_code`；
   - list_marker -> `content.marker`；quote -> `content.quote`；
   - strong/emphasis/strike -> `content.strong/emphasis/strike`；
   - 其余 muted/dim 按上表。
7. 不改构造签名、不引入 `glyphs=`；Markdown task 仍用旧字形（W3 切换）。

## 验收

```bash
uv run pytest -q -p no:cacheprovider          # 896 (824 baseline + 72 contracts)
uv run python tools/golden.py --check         # 58
uv run python tools/framebench.py             # hash 不变
```

## 禁触清单

其他 widget 文件、`kernel/`、`interaction/`、`app.py`、`tests/golden/`、`tools/`、`docs/`。
不 merge/push/tag；不 `golden --update`。

## 交接包

`handoff/W2c-data.md`：Table band/边框映射、Syntax/Markdown token 映射、门禁输出。

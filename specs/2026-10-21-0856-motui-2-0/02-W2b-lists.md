# W2b · Lists and navigation

> 分支 `motui-2/w2b-lists`；起点 `main`（W1 已合并）；写入范围见下。

## 目标

把列表/导航/行组件迁移到 role groups。**零视觉变化**：legacy 默认值下与旧字段等价。
不改字形参数（W3 做）。

## 前置上下文

- 必读：`ref/interfaces.md` §3.1/§3.4/§5 → `handoff/W1-core.md`。
- 基线：`uv sync --locked`；824 passed。

## 写入范围

源码：
`widgets/list.py`、`widgets/tree.py`、`widgets/navlist.py`、`widgets/tabs.py`、
`widgets/menubar.py`、`widgets/strip.py`、`widgets/rows.py`、`widgets/scroll.py`、
`widgets/collapsible.py`

测试：`tests/widgets/test_navigation.py`、`test_menubar.py`、`test_rows.py`、
`test_scroll.py`、`test_containers.py`（如涉及 Collapsible）。

## 工单

1. 行带迁移：
   - List/Tree：`theme.rows.band(active=..., hovered=..., focused=..., disabled=...)`，
     legacy `rows.inactive=DIM` 复现旧 `active.merge(dim)`。
   - NavList：旧的 unfocused active **不 dim**；直接使用 `theme.rows.active` /
     `theme.rows.hover` / `theme.rows.base`，不要走 `band()` 的 inactive。
   - Tabs/MenuBar：保留各自 band 逻辑，只替换 token。
2. 旧字段映射：
   - `theme.accent` -> `theme.content.accent`
   - `theme.muted` -> `theme.text.muted`
   - `theme.dim` -> `theme.text.faint`
   - `theme.hover` -> `theme.surfaces.hover`
   - `theme.focus` -> `theme.controls.focus`
   - `theme.border` -> `theme.borders.base`
   - `theme.ground` -> `theme.surfaces.base`
   - `theme.ground_active` -> `theme.rows.active`
3. `Notice` 在 W2 保留 `theme.notice_levels` 兼容属性（W3 再切 glyph）；其余组件正常迁移。
4. 不改构造签名、不引入 `glyphs=`。

## 验收

```bash
uv run pytest -q -p no:cacheprovider          # 824
uv run python tools/golden.py --check         # 58
uv run python tools/framebench.py             # hash 不变
```

## 禁触清单

其他 widget 文件、`kernel/`、`interaction/`、`app.py`、`tests/golden/`、`tools/`、`docs/`。
不 merge/push/tag；不 `golden --update`。

## 交接包

`handoff/W2b-lists.md`：行带迁移细节（尤其 NavList 不 dim）、token 映射、门禁输出。

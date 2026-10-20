# W5b handoff · 菜单层（MenuBar / ContextMenu）

## A · 交付

分支 `w5b-menus`；实现 commit 按提交顺序：

| commit | 内容 |
|---|---|
| `150b39b` | widgets: 新增 `MenuBar` / `ContextMenu`，facade 与 API pin 同步 |
| `6db3f1e` | tests: `tests/test_widgets_menubar.py`（16 个用例） |
| `6c02c36` | docs: COMPONENTS 两行 catalogue + README 组件列表 |
| 本文件所在 commit | specs: W5b handoff |

新增公开 API（`motui.widgets.__all__` 增加两个名字；根 34 名未变）：

```python
MenuBar(items, *, index=0, active_style=None, inactive_style=None,
        hover_style=None, disabled_style=None, divider=" │ ", divider_style=None,
        disabled_items=(), disabled=False, focused=True, theme=None)
  index (只读) / select / move / click / hover_at / activate / take_result / render / revision
ContextMenu(options=(), *, title="", max_rows=8, marker=glyphs.MENU_CURSOR, **kwargs)
```

基线真实结果（Windows，HEAD 待提交 handoff）：

- `pytest -q -p no:cacheprovider`：**1942 passed, 2 skipped**（基线 1926 + 16 新增）。
- `golden.py --check`：`golden: 11 pages match`。
- `framebench.py`：exit 0；render-hash `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`（未变）。
- demo：`< /dev/null` exit 0 / 70 行；`--pages` exit 0 / 792 行。
- 验收 5 import exit 0：`MenuBar.__module__ == ContextMenu.__module__ == "motui.widgets.menubar"`。
- 写范围：2 个新文件（menubar.py、test_widgets_menubar.py）+ 4 个修改
  （widgets/__init__.py、test_api_root.py、docs/COMPONENTS.md、README.md）；
  `main...HEAD` 无 golden、demo 页面或红线文件。

测试清单：render 单行/默认样式/空条/截断、样式注入、index clamp/select 返回值、
move 跳过 disabled、click span 表（padding/divider/row≠0/越界）、disabled 可见但拒绝、
hover 标记与清除（含 disabled 保持 disabled 样式）、activate/take_result/move 清 pending、
revision 覆盖 items/index/disabled/disabled_items/hover/focused/divider/styles/theme；
ContextMenu 的 Select 预设默认、activate/take_result、title/disabled，以及
HeadlessTUI + `Modal(anchor=(y, x))` 的挂载、点击路由、关闭 smoke。

## B · 偏差、取舍与约束

- **未改 demo / golden**：按工单，exhibits 与重录归 W7；`golden.py --check` 11 页不变。
- 默认色板沿用 `Tabs` 的语义：active → `theme.accent`（**不画 underline**），
  inactive → `theme.dim`，hover → `theme.hover`，disabled → `theme.dim`，
  divider → `theme.muted`；全部在构造期 resolve（explicit > theme > DEFAULT_THEME）。
- disabled label **不叠加 hover**（更严格的状态优先），与 `Tabs` 的“disabled 也 merge hover”
  不同；`hover_at` 仍会记录 disabled 的标记并返回 changed，只是 render 保持 disabled 样式。
- 构造期保留显式传入的 disabled index（`Tabs` 约定：构造器不改写显式请求）；所有动词拒绝它，
  `activate` 对 disabled 当前项返回 False。
- `move` 移动成功后清除 pending；`select` / `click` 不主动清除（沿用 `Select` 的规则）。
  `click` 命中已 active 的 label 返回 True，`select` 同值返回 False（`Tabs` 约定）。
- `focused` 只是 `Focusable` 的 flag，不改变 MenuBar 的渲染（工单只要求 revision 覆盖），
  并计入 `revision()`；`hover` 整体 flag 不参与渲染，故不入 snapshot。
- `ContextMenu` 的三个预设值经 `kwargs.setdefault` 设置，仍可被调用方覆盖；
  其余参数原样转发 `Select`。它没有 `handle`（`Select` 也没有）：Modal 打开时键盘
  `enter` 的落点由 host 调 `activate()`，与 docstring 的挂载配方一致。
- `ContextMenu.activate()` 沿用 `Select` 的 `-> bool`（契约的 Activable 动词）；pending
  值是 `Option`，由 `take_result()` 读取；工单“返回 pending Option”按此理解。
- 空 MenuBar 渲染一行空行（`[Line()]`），与 `Tabs([])` 一致；`render(0)` 同样一行空行。
- 截断后的 label 在 span 表中无条目，点击按 miss 处理；点击先读过 render 后不再重渲染。
- `revision()` 排除 `_last_width` / `_spans`（render 输出）与整体 `hover` flag；
  其余工单点名的输入全部在内，items 以 tuple 复制。

## C · 关键位置与稳定区

- `src/motui/widgets/menubar.py:60`（MenuBar）、`:165`（select）、`:180`（move）、
  `:207`（click）、`:226`（hover_at）、`:241`（activate）、`:255`（take_result）、
  `:329`（render）、`:343`（revision）、`:374`（ContextMenu）。
- `tests/test_widgets_menubar.py:32` 起 16 个用例；Modal smoke 在 `:240`。
- `docs/COMPONENTS.md:200`（ContextMenu）、`:216`（MenuBar）；README 组件列表 `:131`。
- 稳定区（未触碰）：`demo/**`、`tests/golden/**`、`kernel/**`、`app.py`、`keys/**`、
  `interaction/**`、其余 `widgets/*.py`、`widgets/markdown/**`、`pyproject.toml`、
  `uv.lock`、`docs/CONTRACT.md`；无 merge / push / tag。

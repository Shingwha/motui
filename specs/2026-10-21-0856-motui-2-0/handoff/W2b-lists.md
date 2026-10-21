# W2b 交接包（lists and navigation）

> 分支 `motui-2/w2b` / 起点 `eb9e835`（W1 已合并）/ 代码提交 `7a9831b` / 2026-10-21

## A. 自动事实

### 用例数

`uv run pytest -q -p no:cacheprovider`：**896 passed**，与 W1 基线相同。
本波**没有修改任何测试文件**，没有改断言。

### 终验命令与真实输出

```text
uv run pytest -q -p no:cacheprovider
896 passed in 10.78s

uv run python tools/golden.py --check
golden: 58 topics match

uv run python tools/framebench.py
stream-single:     1.7 ms/frame
stream-split :    12.3 ms/frame
scroll       :     1.1 ms/notch
scroll-long  :     4.6 ms/notch
text-open    :     0.2 ms/frame
table-open   :     0.2 ms/frame
stream-paragraph:     1.2 ms/frame
replay       :     520 ms total
render-hash  : f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1

uv run python -m motui < /dev/null
exit 0，70 行，与基线逐字节相同

uv run python -m motui --pages > /tmp/pages.txt
exit 0，4130 行，与基线逐字节相同
```

`tests/golden/` 未改动，未运行 `golden.py --update`。

### Commit 清单

| commit | 内容 |
|---|---|
| `7a9831b` | `widgets: migrate the list and navigation families to theme groups` |
| 本文件所在 commit | `specs: hand off the W2b list and navigation migration` |

### 变更范围 / 禁触审计

`git diff --name-only eb9e835..HEAD` 共 8 个源文件，全部在工单写入范围内：

- `src/motui/widgets/{list,tree,navlist,tabs,menubar,rows,scroll,collapsible}.py`

零 diff：`src/motui/widgets/strip.py`（本波无 theme 字段读取，无需改）、
`src/motui/widgets/bands.py`（共享文件所有者表写明 W4 前不修改）、
其他 widget、`kernel/`、`interaction/`、`app.py`、`tests/`、`tests/golden/`、
`tools/`、`docs/`、`pyproject.toml`、`uv.lock`。未 merge/push/tag。

## B. 只有存在于脑子里的东西

### 行带迁移（List / Tree）

List 与 Tree 的 `_band` 现在分两条路：

1. **主题路径（`bands is None`，默认）**：按 `interfaces.md` §3.3 的
   `RowStyles.band` 语义解析。
   - 光标行：focused -> `theme.rows.active`；unfocused -> `theme.rows.inactive`。
     legacy `rows.inactive = DIM`，在默认主题下逐字节复现旧的
     `active.merge(dim)`。
   - 指针行：`theme.surfaces.hover`。
   - 静止行：`theme.surfaces.base`。
   - disabled 行：`theme.text.faint`（显式 `disabled_style` 优先）。
   - 显式 `ground_style` / Tree 的 `active_style` / `disabled_style`
     在主题路径里仍然压过对应 token（构造签名未变）。
2. **显式 `bands=` 路径**：继续走 `RowBands`（`resolve_band(self.bands, ...)`），
   优先级、`dim` 合并、背景带不 dim 的旧规则完全保留。注意用的是构造后的
   `self.bands`，因此 `bands=` 与显式 `ground_style`/`active_style`/
   `disabled_style` 同时给出时，后者仍像旧代码一样覆盖前者。

**为什么 hover 是 `surfaces.hover` 而不是 `rows.hover`**：1.x 的扁平
`theme.hover` 在 W1 映射到 `surfaces.hover`（`interfaces.md` §3.4），
`tests/widgets/test_action.py` 的跨组件 hover 用例也只覆盖
`surfaces.hover`。W3 的两个 shipped palette 把 `rows.hover` 与
`surfaces.hover` 设为同一个 `palette.surface_hover`，届时两者重合。
本波保持 `surfaces.hover`，现有测试与自定义主题行为不变。

**为什么 disabled 是 `text.faint` 而不是 `rows.disabled`**：旧组件读的是
`theme.dim`，映射表明确写 `theme.dim -> theme.text.faint`。用
`rows.disabled` 会让“只覆盖 `text.faint`”的旧自定义主题失去 disabled 行
的视觉。默认主题下 `rows.disabled == text.faint == DIM`，两者等价。

### 行带迁移（NavList）

NavList **不走 `band()` 的 inactive 分支**，也不受 `focused` 影响：

```text
disabled -> disabled_style (默认 text.faint)
hovered  -> surfaces.hover
current  -> rows.active          # 永远不 dim，D3
rest     -> surfaces.base
```

旧的 `dim=NONE` seed 由“直接读 `rows.active`”取代；显式 `bands=` 仍走
`RowBands` 且 seed 保留 `dim=NONE`。

### token 映射（精确）

| 组件 | 旧读取 | 新读取 |
|---|---|---|
| List 计数行 | `theme.dim` | `theme.text.faint` |
| List/Tree 光标带 | `theme.ground_active` | `theme.rows.active` |
| List/Tree unfocused 光标带 | `active.merge(theme.dim)` | `theme.rows.inactive` |
| List/Tree/NavList 指针带 | `theme.hover` | `theme.surfaces.hover` |
| List/Tree/NavList 静止带 | `theme.ground` | `theme.surfaces.base` |
| List/Tree/NavList disabled | `theme.dim` | `theme.text.faint` |
| Tree guide / `_dim` | `theme.dim` | `theme.text.faint` |
| NavList active 标签 / bar active / indicator | `theme.accent` | `theme.content.accent` |
| NavList inactive / disabled | `theme.dim` | `theme.text.faint` |
| NavList bar / group / unfocused bar merge | `theme.muted` | `theme.text.muted` |
| Tabs active / indicator | `theme.accent` | `theme.content.accent` |
| Tabs/MenuBar inactive / disabled | `theme.dim` | `theme.text.faint` |
| Tabs/MenuBar hover | `theme.hover` | `theme.surfaces.hover` |
| Tabs/MenuBar divider | `theme.muted` | `theme.text.muted` |
| Tabs unfocused indicator | `theme.muted` | `theme.text.muted` |
| StatusLine default/gap | `theme.dim` | `theme.text.faint` |
| ShortcutBar key / label | `theme.accent` / `theme.dim` | `theme.content.accent` / `theme.text.faint` |
| ScrollView track / thumb | `theme.scrollbar` / `theme.scrollbar_thumb` | `theme.chrome.scrollbar` / `theme.chrome.scrollbar_thumb` |
| Collapsible title / hover / focus / disabled | `accent` / `hover` / `focus` / `dim` | `content.accent` / `surfaces.hover` / `controls.focus` / `text.faint` |

`Notice` 按工单保留 `theme.notice_levels`（W3 再切 `notice_*` glyph），本波
未改。`strip.py` 没有任何 theme 字段读取，保持零 diff。

### 探索审计（基线 vs 当前，逐字节）

在临时目录用 `git archive eb9e835` 解出基线源码，与当前源码各跑同一个渲染
矩阵：10 个组件族 × 默认/自定义主题 × focused/unfocused × hover/disabled/
marked/filtered × 显式 styles/bands，共 **77 个 case**，比较每行的 `text`、
宽度与每个 segment 的 SGR。结果：

- **73/77 case 逐字节相同**；`DEFAULT_THEME` 下全部相同。
- 4 个 case 不同，全部是 List/Tree 的 **unfocused 光标带**在自定义主题下：
  - `list active-bg focused=False`
  - `list custom (text.faint=italic) focused=False`
  - `tree active-bg focused=False hovered`
  - `tree custom (text.faint=italic) focused=False hovered`

原因与工单要求一致：旧 `RowBands` 在 `active` 带背景时保留 active 带，
否则 merge `theme.dim`；新 `RowStyles.band` 的 unfocused 分支统一读
`rows.inactive`（legacy `DIM`）。默认主题下两者逐字节相等。

`python -m motui` 与 `--pages` 的完整 stdout 均与基线逐字节相同。

### 偏差、取舍与已知风险

1. **自定义主题的 unfocused 光标带**（上面 4 个 case）：这是从
   `RowBands` 切到 `RowStyles.band` 的必然语义变化，工单明确要求
   `rows.inactive=DIM` 复现旧行为。demo 的 `THEMES` 只覆盖
   `rows.active`（背景带）而没有覆盖 `rows.inactive`，所以 demo 的
   List（默认 `focused=False`）在运行时会把光标行画成 legacy DIM，而不是
   原来的蓝底。golden 只比较纯文本、render-hash 不经过 List，因此门禁全绿，
   但这是真实的视觉差异。`demo/assets.py` 属 W1 写入范围，本波不能改；
   建议 W3 在 demo 主题里补 `rows.inactive`（例如设为与 active 同色的
   `surface_inactive`），或接受这里的角色切换。
2. **`rows.hover` 在本族暂未使用**：见上文，hover 走 `surfaces.hover`
   以保持 1.x 映射与既有测试。W3 shipped palette 两者相等，视觉一致。
3. **`rows.disabled` 在本族暂未使用**：disabled 走 `text.faint`，保持旧
   `theme.dim` 语义；W3 的 `rows.disabled=NONE` 若被期望用于“去掉 disabled
   带”，需要 W3 再评估。默认主题下等价。
4. **`interfaces.md` §5 与 1.x 实际 token 的出入**：§5 写 Tabs inactive
   `text.muted`、divider `chrome.divider`，NavList inactive `text.muted`；
   1.x 实际是 inactive=`dim`、divider=`muted`、NavList inactive=`dim`。
   本波按工单的“零视觉变化 + §3.4 映射表”执行（`dim -> text.faint`、
   `muted -> text.muted`），未按 §5 改写。若 §5 是 W3 的目标观感，需要
   W3 显式切换并重录 golden。
5. **List/Tree 的 `rows.selected` / `rows.marked` 未使用**：1.x 没有这两个
   行带，List 的 mark 是文本前缀而不是 band；本波不改渲染逻辑。
6. **`bands.py` 未修改**：`RowBands.from_theme` 仍服务 W2a/W2c 的
   `choice.py`/`table.py`，W4 删除。
7. **显式 `bands=` + 显式 style 覆盖**：主题路径与 `bands=` 路径都保持
   旧优先级。审计里显式 `bands`、显式 styles、`bands`+styles 组合均逐字节
   一致。
8. **`strip.py`**：无 theme 读取，保持零 diff，不是遗漏。

## C. 指针

- 工单：`specs/2026-10-21-0856-motui-2-0/02-W2b-lists.md`
- 接口：`specs/2026-10-21-0856-motui-2-0/ref/interfaces.md` §3.1/§3.3/§3.4/§5
- 源：
  - `src/motui/widgets/list.py` / `tree.py`（`_band` + seed）
  - `src/motui/widgets/navlist.py`（`_band`、token 映射）
  - `src/motui/widgets/tabs.py` / `menubar.py`（只换 token）
  - `src/motui/widgets/rows.py`（StatusLine/ShortcutBar；Notice 未动）
  - `src/motui/widgets/scroll.py`（chrome）、`collapsible.py`
- 行带底层：`src/motui/widgets/bands.py`（W4 删除）、
  `src/motui/kernel/theme.py` 的 `RowStyles.band`
- 门禁：`uv run pytest -q -p no:cacheprovider`、`uv run python tools/golden.py --check`、
  `uv run python tools/framebench.py`
- 基线：起点 `eb9e835`；render-hash
  `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`

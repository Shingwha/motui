# W2d 交接包（interaction / app / chrome 迁移）

> 分支 `motui-2/w2d` / 起点 `eb9e835`（main，W1 已合并）/ 2026-10-21

## A. 自动事实

### 门禁真实输出

```text
uv run pytest -q -p no:cacheprovider
896 passed in 10.92s

uv run python tools/golden.py --check
golden: 58 topics match

uv run python tools/framebench.py
stream-single:     2.1 ms/frame
stream-split :    14.2 ms/frame
scroll       :     1.1 ms/notch
scroll-long  :     4.3 ms/notch
text-open    :     0.2 ms/frame
table-open   :     0.2 ms/frame
stream-paragraph:     1.5 ms/frame
replay       :    692 ms total
render-hash  : f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1
```

基线（开工前同一 worktree 实测）：896 passed、golden 58、hash
`f872187a...d6e1`，与迁移后逐字节一致。

### Commit 清单

| commit | 内容 |
|---|---|
| `44f1977` | `interaction: read the role groups in find, modal, overlays and scrollbar` |
| `25bd191` | `chrome: resolve the separator from the content and border groups` |
| `9ffeb9e` | `app: read the selection band from text.selection` |
| 交接包提交 | `specs: hand off the W2d interaction migration`（本文件） |

### 变更范围 / 禁触审计

`git diff --name-only eb9e835..HEAD` 共 6 个源文件：

- `src/motui/interaction/find.py`
- `src/motui/interaction/modal.py`
- `src/motui/interaction/overlays.py`
- `src/motui/interaction/scrollbar.py`
- `src/motui/kernel/chrome.py`
- `src/motui/app.py`

零 diff：`src/motui/widgets/`、`src/motui/kernel/` 其余模块、`src/motui/keys/`、
`src/motui/demo/`、`tests/`（含 `tests/golden/`）、`tools/`、`docs/`、
`pyproject.toml`、`uv.lock`。未运行 `golden.py --update`，未 merge/push/tag。

`interaction/palette.py` 在写入范围内但无需改动（见 B）。

## B. 只有存在于脑子里的东西

### 精确映射

| 位置 | 旧读取 | 新读取 |
|---|---|---|
| `Find._marked_rows` | `theme.selection` | `theme.text.selection` |
| `Find._marked_rows`（当前命中） | `theme.hover` | `theme.surfaces.hover` |
| `Find._with_query_row`（计数器） | `theme.dim` | `theme.text.faint` |
| `Find._with_query_row`（底栏） | `theme.toast` | `theme.overlays.toast` |
| `Modal.__init__`（scrim 缺省） | `theme.dim` | `theme.overlays.scrim` |
| `Toasts._resolve_band` | `theme.toast` | `theme.overlays.toast` |
| `Tooltip.paint` | `theme.toast` | `theme.overlays.toast` |
| `Stats.paint` | `theme.toast` | `theme.overlays.toast` |
| `Scrollbar._resolve_track` | `theme.scrollbar` | `theme.chrome.scrollbar` |
| `Scrollbar._resolve_thumb` | `theme.scrollbar_thumb` | `theme.chrome.scrollbar_thumb` |
| `Separator._resolve`（聚焦） | `theme.accent` | `theme.content.accent` |
| `Separator._resolve`（其余） | `theme.border` | `theme.borders.base` |
| `_SelectionOverlay.paint`（app） | `theme.selection` | `theme.text.selection` |

零视觉变化的依据：legacy 默认值下这些 group 字段与 W1 兼容属性逐值相等
（`text.selection = Style(reverse=True)`、`surfaces.hover = NONE`、
`text.faint = DIM`、`overlays.toast = Style(reverse=True, dim=True)`、
`overlays.scrim = DIM`、`chrome.scrollbar = DIM`、
`chrome.scrollbar_thumb = NONE`、`content.accent = ACCENT`、
`borders.base = NONE`），golden 58 + 同一 render-hash 已证实。

### 实现细节

- **Modal** 的 scrim 仍是**构造期**解析：显式 `scrim_style` > `theme.overlays.scrim`
  > `DEFAULT_THEME.overlays.scrim`。没有 `set_theme`，语义未变。
- **Palette** 无需改动：它只把 `theme` 转交 `host.make_input` /
  `host.make_autocomplete`；`Modal(tui, self._panel, anchor=_BOTTOM, focus=focus)`
  本来就不接收 theme，scrim 一直取 `DEFAULT_THEME`。保留这一既有行为，未借迁移
  顺手改变（否则自定义主题会突然重染 scrim，属于 W3/W4 的行为决策）。
- **app.py** 只有一处 theme 读取（`_SelectionOverlay.paint`）；`TUI.theme` 的
  赋值与 `Separator` 的 host-theme 读取路径未动。因加长换行，`highlight(...)`
  调用改成多行，参数与求值顺序不变。
- **Scrollbar** 的 strip 缓存 key 不包含 group 路径，只包含解析后的 `Style`；
  `Style` 可哈希且相等性不变，所以缓存命中行为与旧实现一致。
- **Separator** 仍是每次 paint 现读 `host.theme`，焦点切换/换主题照旧重建 strip。
- 文档同步：`find.py`、`modal.py`、`overlays.py`、`scrollbar.py`、
  `kernel/chrome.py` 的 docstring 改为 group 路径；未改任何公开签名、未引入
  `glyphs=`、未改渲染逻辑。

### 测试

`tests/` 零改动。W1 已完成旧 `Theme(...)` 构造的机械迁移；本次源码迁移后
896 全绿，不存在“因旧 Theme 构造而必须改测试”的点，也没有改任何断言。

### 已知遗留（不在本工单范围）

- `tests/app/test_selection_overlay.py:47` 仍读兼容属性 `DEFAULT_THEME.selection`
  （不是构造点，断言仍有效）；W4 删除兼容属性时需同步。
- `demo/`、`widgets/` 内的旧属性读取按禁触清单保留给 W3/W4。
- `kernel/selection.py` 的 docstring 仍写 `theme.selection`；该文件不在写入范围。

## C. 指针

- spec：`specs/2026-10-21-0856-motui-2-0/02-W2d-interaction.md`
- 接口：`specs/2026-10-21-0856-motui-2-0/ref/interfaces.md` §3.1、§3.4、§5
- 源：`src/motui/interaction/{find,modal,overlays,scrollbar}.py`、
  `src/motui/kernel/chrome.py`、`src/motui/app.py`（`_SelectionOverlay`）
- 兼容属性映射：`src/motui/kernel/theme.py`（W1 临时属性，W4 删除）
- 视觉门禁：`uv run python tools/golden.py --check`、
  `uv run python tools/framebench.py`
- 基线：起点 `eb9e835`；render-hash
  `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`

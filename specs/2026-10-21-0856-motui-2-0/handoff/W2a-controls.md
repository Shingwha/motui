# W2a 交接包（controls and forms）

> 分支 `motui-2/w2a` / 起点 `eb9e835`（W1 合并 + W2 工单）/ 2026-10-21
> 源码 commit `d8ffee3`；本文件为最后一个 commit。

## A. 自动事实

### 门禁真实输出

```text
uv run pytest -q -p no:cacheprovider
896 passed in 11.05s

uv run python tools/golden.py --check
golden: 58 topics match

uv run python tools/framebench.py
stream-single:     1.8 ms/frame
stream-split :    11.0 ms/frame
scroll       :     1.0 ms/notch
scroll-long  :     5.1 ms/notch
text-open    :     0.2 ms/frame
table-open   :     0.2 ms/frame
stream-paragraph:     1.6 ms/frame
replay       :     786 ms total
render-hash  : f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1
```

render-hash 与 W1 基线 `f872187a…d6e1` 逐字符相同；58 个 golden topic 未变。

### Commit 清单

| commit | 内容 |
|---|---|
| `d8ffee3` | `widgets: read the 2.0 role groups in the controls and forms` |
| 本文件所在 commit | `specs: hand off the W2a controls migration` |

### 变更范围 / 禁触审计

`git diff --name-only a80b4c4..HEAD`（a80b4c4 = W1 merge）只新增：

```text
src/motui/widgets/action.py
src/motui/widgets/choice.py
src/motui/widgets/dialog.py
src/motui/widgets/form.py
src/motui/widgets/textfield.py
```

（另有 `eb9e835` 的 W2 工单文本，属起点、非本波改动。）

- `autocomplete.py`、`combobox.py` 在写入范围内但**没有任何直接 theme token 读取**
  （只把 `theme=` 透传给 `Select` / `Input`），因此零 diff。
- `tests/` 零 diff：W1 的机械迁移已经把这些测试里的构造更新到 group 形式
  （`test_editing.py` 用 `text`/`surfaces`，`test_action.py` 用 `content`/`surfaces`），
  W2a 不需要再动；所有断言逐字未改。
- 零 diff：`kernel/`、`interaction/`、`app.py`、`keys/`、其他 widget 文件、
  `tests/golden/`、`tools/`、`docs/`、`pyproject.toml`、`uv.lock`。
  未运行 `golden --update`，未 merge/push/tag。

## B. 只有存在于脑子里的东西

### 旧字段 -> group 的精确映射（本波落地值）

| 文件 / 组件 | 旧读取 | 新读取 |
|---|---|---|
| `action.Button` | `accent` | `controls.base` |
| | `hover` | `surfaces.hover` |
| | `focus` | `controls.focus` |
| | `dim` | `text.faint` |
| `action.Checkbox` | 同上四项 | 同上四项（基准也是 `controls.base`） |
| `action.Link` | `link` | `content.link` |
| | `hover` / `focus` / `dim` | `surfaces.hover` / `controls.focus` / `text.faint` |
| `choice.Select` | `accent`（cursor text） | `content.accent` |
| | `dim`（description） | `text.faint` |
| | `dim`（disabled row） | `text.faint` |
| `textfield._TextField` | `caret` | `text.caret` |
| | `dim`（placeholder） | `text.faint` |
| | `hover` | `surfaces.hover` |
| | `selection` | `text.selection` |
| `textfield.Input` | `accent`（prompt） | `content.accent` |
| `form.Form` | `accent`（label） | `content.accent` |
| | `error`（error row） | `status.danger` |
| `dialog.Dialog` | `border` | `borders.base` |
| | `error`（`danger=True` 的边框） | `status.danger` |
| | `heading`（title） | `content.headings[1]` |
| | `error`（danger 按钮的默认 style） | `status.danger` |

实现形式统一为 `self.pick(explicit, <resolved token>)`；无显式参数的读取
（`Form` 的 label/error、`Dialog` 的 border/heading）直接取 group 字段。

### 三个需要后来者知道的判断

1. **Button/Checkbox 的基准用 `controls.base`**，不是 `content.accent`。
   工单的括号注“控件基准用 `theme.controls.base`”按字面落地。legacy 下
   `controls.base == content.accent == ACCENT`；W3 下两者同为 `palette.accent`，
   所以视觉与调色板派生都不会分叉。
2. **Select 的 description 用 `text.faint`，不是 §5 写的 `text.muted`**。
   旧代码读 `theme.dim`（legacy = `DIM` = `Style(dim=True)`），而
   `text.muted` 是 `#8b949e`；只有 `text.faint` 能保持逐字节不变。
   §5 的 `text.muted` 是 W3 切默认主题后的目标，本波不能用。
3. **Dialog 的边框 token 先求值再 `pick`**：`danger` 选择
   `status.danger`/`borders.base` 后传给 `self.pick(border_style, token)`，
   保持“显式 > theme”的旧优先级。

### 未迁移、但相关的东西

- `widgets/bands.py::RowBands.from_theme` 仍读兼容属性
  （`theme.ground` / `ground_active` / `hover` / `dim`）。它不在 W2a 写入范围，
  `Select`/表单组的行带因此仍经由兼容 shim 解析。**W4 删除兼容属性前必须有人
  迁移 bands.py**；W2a–d 的工单都没有把它列进写入范围（见未决问题）。
- 源文件 docstring 仍用角色词描述旧字段（“the theme's accent/hover/dim”），
  没有改成 group 路径。这是有意的最小 diff；语义仍成立，W3/W4 可随文档刷新。
- `Checkbox` 目前仍用**一个** base style 画 mark+label（未按 §5 拆
  `content.accent`/`text.base`）。拆分会改变渲染，属 W3/W4，不在本波。

## C. 指针

- 工单：`specs/2026-10-21-0856-motui-2-0/02-W2a-controls.md`
- 接口：`specs/2026-10-21-0856-motui-2-0/ref/interfaces.md` §3.1/§3.4/§5
- 源：`src/motui/widgets/{action,choice,textfield,form,dialog}.py`
- 基线：起点 `eb9e835`；源码 commit `d8ffee3`；render-hash
  `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`

## 未决问题

1. **`bands.py` 归属**：`RowBands.from_theme` 的旧属性读取没有任何 W2 工单覆盖；
   W4 删除兼容属性前会变成硬错误。建议在 W3 或 W4 增补一行写入范围。
2. `interfaces.md` §5 与 W2 机械映射的差异（Checkbox 的 mark/label 拆分、
   Select description 的 `text.muted`）需要在 W3 视觉切换时一并落地，
   否则 §5 与实现会继续不一致。

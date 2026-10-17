# ref · motui demo 设计契约（权威）

> W3（文档）与 W5（demo 重构）都必须按本文件的口径写。本文件由 lead 拍板，worker 不复议。

## 1. 交付形态：demo 随包发布

- demo 从 `examples/gallery/` **搬进包里**：`src/motui/demo/`，随 wheel 一起发布。
  `examples/` 目录整体消失（fixture 一并搬入）。
- **唯一入口：`python -m motui`**（`src/motui/__main__.py` → `motui.demo` 的 `main()`）。
  与生态惯例一致：rich 的 `python -m rich`、textual 的 `python -m textual`（两者的 demo
  都随包发布、都用 module 入口）。**不**加 `[project.scripts]`——一个只用来放 demo 的控制台
  脚本会让人误以为 `motui` 是个 CLI 工具；将来真有了 CLI，再在 `pyproject` 里加一行也不迟。
- 三个运行档（沿用现有能力，改名按此）：
  - 真终端：交互会话（alt screen、hover 1003、focus events 1004）；
  - 管道（stdout 非 tty，`< /dev/null` 计）：headless 脚本重放 + 纯文本 dump，exit 0；
  - `--pages`：逐页纯文本 dump（无需终端），exit 0。
- **不在仓里另留 `examples/`**：README 的 Quickstart 已覆盖「最小应用」，`docs/COMPONENTS.md`
  覆盖组件契约；再放一份 examples 只是第三个真相源。（textual 仓里两者都有，但它的 examples
  是独立可跑的多平台示例集，本库不需要这一层。）
- demo **只许用公开面**：根 31 名 + 各层命名空间（`motui.widgets` / `motui.kernel` / `motui.interaction` /
  `motui.chrome` / `motui.keys` / `motui.testing`）。例外：`motui.kernel.frame` 的 `splice_row`
  这类「文档化的深缝」按现状保留（它在公共模块路径上）。**不许**从别的模块 import 私有名。

## 2. 版面：左轨 + 右内容（顶部 tab 条取消）

```
┌────────────────────────────────────────────────────────────────────┐
│ motui · <page title>                        <right: fps/status>    │  头部 band（1 行）
├──────────────┬─────────────────────────────────────────────────────┤
│   Content    │                                                     │
│ ▸ Data       │      页面内容（自己的视口，独立滚动）                │
│   Input      │                                                     │
│   …          │                                                     │
│              │                                                     │
├──────────────┴─────────────────────────────────────────────────────┤
│ c-n/c-p pages · tab focus · c-o pane · c-f find · c-g stats · q     │  提示行（1 行）
└────────────────────────────────────────────────────────────────────┘
```

- **左轨 = 一个真 pane**（`TUI.split("vertical", ratios=(1, 4))`）：左 pane 的文档挂一条
  竖直的页签组件，右 pane 装页面内容。理由：这是本库自己的机制（pane 有独立视口/焦点/命中测试），
  左轨因此天然「不随内容滚动、标签超高时自己滚」，且不用在 demo 里手搓矩形路由。
- 左轨宽度随终端按比例（这是 `ratios` 的语义）；若终端很宽导致轨道过宽，允许 demo 在 resize 时
  用 `ratios=(max(16, w//6), ...)` 之类的**整数重算**保持视觉合理——实现方式写进报告。
- **竖直页签 = `Tabs` 新增 `orientation="vertical"`**（lead 决定，见 §4）：
  一行一个标签、点击/悬停按**行**解析索引。横向行为必须字节不变（现有 Tabs 测试与 golden 里
  任何横向用法都不得变化）。
- 诚实出口（agent 若发现左轨 pane 路线与既有 `/split` 展品或滚轮路由打架）：可以退回到
  「shell 自己把固定宽度的左轨列 splice 进内容行 + demo 自己做矩形内命中路由」，但必须在报告里
  写清冲突证据、代价与最终选择。**不许**为此新增核心层机制。

## 3. 页面分类（14 页 → 11 页，合并而非扩充）

| # | 页名 | 装什么（组件） | 来源 |
|---|---|---|---|
| 1 | `overview` | 这是什么、demo 怎么组织、可点的索引 | 原 overview |
| 2 | `content` | `Text`、`Markdown`（GFM 表格/代码围栏/行内规则）、`Diff` | 原 content + markdown + diff |
| 3 | `data` | `Table`、`List`、`Tree`（行光标、拾取、悬停行） | 原 data + navigation 的 Tree |
| 4 | `input` | `Input`、`Editor`、`Autocomplete`（点格落光标） | 原 input + choice 的 Autocomplete |
| 5 | `choice` | `Select`、`Confirm`、`Radio`、`Checkbox` | 原 choice + action 的 Checkbox |
| 6 | `action` | `Button`、`Link`、`Slider` | 原 action + forms 的 Slider |
| 7 | `layout` | `Panel`、`Row`、`Column`、`Padding`、`Spacer`、`Divider`、`Collapsible`、`Notice` | 原 structure + feedback 的 Collapsible/Notice |
| 8 | `feedback` | `ProgressBar`、`Spinner`、`StatusLine`、`Toasts`、`Tooltip` | 原 feedback |
| 9 | `chrome` | split panes、`Scrollbar`、`Stats`、`Tooltip`、`Palette`（作展品）、选区复制、命中测试探针 | 原 features + devtools + 旧壳的 Palette |
| 10 | `styles` | 主题选择器、颜色与属性（选了整壳换肤） | 原 styles |
| 11 | `streaming` | fixture 的流式 Markdown | 原 streaming |

- **每页只讲一件事**：标题 + 一句说明 + 展品本身 + 一行「你刚做了什么」的 echo（现有 idiom 保留）。
- 页数上限 11（左轨能装下；终端再矮左轨自己滚）。

## 4. `Tabs(orientation=...)` 的最小契约（W5 实现 + 测试）

- 新增关键字参数 `orientation: str = "horizontal"`，取值 `"horizontal"` / `"vertical"`；其它值
  `ValueError`。
- `"horizontal"`：**现状字节不变**（一行、` │ ` 分隔、两端各一个空格、`fit` 截断）。
- `"vertical"`：一行一个标签（行内左对齐、行尾不留分隔符）；`active`/`focused`/hover 的样式规则与
  横向完全一致（`active_style`、`theme.dim` 合并、hover 合并）。
- `click(row, col)` / `hover_at(row, col)`：横向按**列**解析，纵向按**行**解析；越界返回 `False`／`None`。
- `move`/`select` 语义不变（clamp、不环绕）。
- 文档字符串要讲清两个轴向（沿用仓库文体）。
- 测试：横向既有用例逐字保留；纵向新增**少量**用例（渲染行数/标签位置、click 按行、hover 按行、越界）。

## 5. 必须保留的 demo 能力（不许在重构中丢失）

- **左轨导航**：点击标签切页、`c-n`/`c-p` 翻页（首尾环绕）、`q`/`Ctrl-C` 退出。
- **取消 `/` 命令面板这套壳级导航**（lead 决定，理由见 §5.1），但 `Palette` 组件本身
  仍要作为**展品**出现在页面上（`chrome` 页：点开/按键打开，演示它自己的查询行、过滤与拾取 echo）。
- 焦点环（`tab` 循环、`enter` 激活、点击即聚焦）与页内按键路由。
- 悬停 + tooltip 提示带（叶子自己的 `hint`）；`c-g` 挂/摘 `Stats`；`c-f` 打开 `Find` 搜索层；
  `c-o` 切 pane 焦点（含左轨 pane）；拖选 + `on_end` 复制；滚轮按指针位置路由。
- 头部 band 的 window title（每页标题）与光标形状请求。
- 页面的 echo 行（拾取结果回显）+ toast 回显。
- headless 重放脚本：覆盖每一页与关键交互，dump 稳定（dump 里不留临时 overlay）。

### 5.1 为什么壳里不再有 `/` 命令面板

`Palette` 在旧壳里的职责是**导航**（页面 + `split`/`theme`/`fps`/`quit` 动作）——那是
mocode agent 宿主留下的形态。装了左轨之后，导航由轨道承担（一屏全见、可点、可键进），
面板变成**第二套导航**：多一个模态层、多一套 `/` 前缀解析、多一份命令表，却不再有不可替代的
职责；`split`/`theme`/`fps`/`quit` 都有直接按键（`c-o` / styles 页的选择器 / `c-g` / `q`）。
所以：**壳不再有 `/`**，`Palette` 降级为一个可玩的展品（组件一个不少，壳少一层模态）。

## 6. 代码体量与结构目标（“简洁清晰”的量化口径）

- `src/motui/demo/` 总行数 **≤ 2000**（现状 examples/ 全量 3649）。允许的拆分：
  `__init__.py`（导出 `main`）、`__main__.py`、`pages/`（每页一个 builder）、`shell.py`（头部/提示行/状态/
  左轨/palette overlay）、`session.py`（宿主循环与 dispatch）、`registry.py`（页表）、`script.py`（重放脚本）、
  `fixture.md`（原 `examples/Markdown-Rendering-Test.md`）。
- 不许有「为了兼容旧 demo」的 shim；旧文件直接搬/改/删。

## 7. 与门禁的关系

- golden 帧：`tests/golden/pages/` 变为 **11** 个文件（页名同上）。重录后逐帧 diff 审查，
  允许的变化 = 版面（左轨/头部/提示行）+ 页面拆分带来的内容移动；**不允许**出现组件渲染本身的退化
  （例如某组件在新页里被裁掉半行这类非预期差异要逐个解释）。
- `tests/test_gallery_protocol.py` → `tests/test_demo_protocol.py`：按新壳重写，保留原有几条
  宿主接线断言（title/cursor shape、tooltip、search c-f、stats c-g、页切换关闭 find）。
- CI 与 README 里的 demo 命令统一为 `python -m motui`（`examples/demo.py` 一律消失）。

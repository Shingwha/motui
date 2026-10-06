# ref · 能力清单（本次要"展示到位"的东西，与它在新展台上的落点）

> 依据 `docs/COMPONENTS.md` / `README.md` 的现状面 + interaction-model 组刚落地的能力。
> 每一行都是"必须能在新展台上被看到/被玩到"，不是"库里存在"。

## 1. 交互模型（本组的第一主角，interaction-model 刚定稿）

| 能力 | 新展台上的落点 | 观众怎么看到 |
|---|---|---|
| `click(row, col)`（命中带列） | 顶部导航 Tabs 条（列 → tab）、Table 行、Tree 行、菜单行 | 点条上任意一个 tab 名 → 直接切页；点分隔符无反应 |
| `activate()` + `chosen`（读一次清一次） | 每个可激活展品的宿主回声：toast + 页内 last-action 行 | `enter`/二点 → toast 报出 chosen 的值 |
| `FocusRing`（tab 循环、箭头驱动、enter 激活、点一次聚焦/二点激活） | `interaction` 展品（三件套）+ 各页已有的 ring | 失焦控件的选中行**变暗**；`tab` 换人 |
| `focused` 失焦渲染（`merge(theme.dim)`） | 所有列表族展品 | 焦点换位时，前任光标行肉眼变暗 |
| 字段落点 `place` | `fields` 展品（Input/Editor）+ `interaction` | 点文本任意一格 → 块光标落在那儿 |
| bracketed paste（一个 Paste、永不提交） | `keys`/`fields` 展品的说明 + piped 回放 | 真机粘 3 行：填满、不提交；回车才发一次 |

## 2. 组件族（每族至少一个"可玩"的展品）

| 族 | 组件 | 玩法 |
|---|---|---|
| 文本与数据 | Text, Markdown, Table, Divider | Table 行光标（`↑↓`/点击/`enter`→chosen）；Markdown 见第 3 节 |
| 结构与布局 | Panel, Row, Column, Padding, Spacer, Tabs, Tree | Tabs 点击选页签；Tree `enter`/点击折叠展开 |
| 输入与选择 | Input, Editor, Select, Confirm, Autocomplete | Select 的窗口+计数、Confirm 危险/普通、Autocomplete 过滤；chosen 回声 |
| 数据与进度 | ProgressBar, Spinner, Notice, Toasts | 活的 bar/spinner；**按需 toast**（一个可激活的展品触发） |
| 聊天层 | Composer, Transcript, Message, ToolBlock, EditBlock, StatusLine | 现有 chat 展品 + 活回合 |
| 壳与层 | Frame/Pane/split, Scrollbar, SelectionGesture, Toasts | `/split` 预览 + 选择复制 + 滚动条 |

## 3. Markdown 与流式（本组的第二主角）

- **流式是特性，不是过场**：长文档按"块"流入（heading / paragraph / fence / table / quote 各算一块），观众能看见结构在长。
- **可把玩**：控制条提供 `play / pause / step / replay / 速度`，用**单项 `Select` + `activate()` + `chosen`** 实现（D6 配方 —— 顺带把"不做 Button"的替代写法演示出来）。
- **内容**：`examples/Markdown-Rendering-Test.md`（346 行、每种构造）就是被流的那份文档 —— 一份内容，两个卖点（渲染覆盖面 + 流式）。
- **可回看**：`replay` 重头再流；`step` 一块一块走（便于逐块讲解）。
- **dump-safe**：`--pages` 与非交互路径下，展品**构造即完整**（不靠 tick/异步长出来），dump 必须显示完整 fixture。

## 4. 壳与工程性（"这个库怎么用"的故事）

| 能力 | 落点 | 怎么看到 |
|---|---|---|
| 可见导航 | 顶部 Tabs 条 + `c-n`/`c-p` 前后展品 | 点 tab 名 / 按 `c-n` 切页 |
| 面板 palette | `/` 打开 | 与导航并存（两条路都能切页） |
| 主题 | `styles` 展品的主题选择器（chosen → 换肤） | 点一个主题名 → 整个壳换肤 |
| keymap | `keys` 展品（三张表 + 重绑故事） | 表 + 一行可复制的重绑/解绑示例 |
| 分屏 | `/split` + `c-o` | 第二窗格独立滚动 |
| 滚动 / 选择 / 剪贴板 | 每个展品 | 滚轮、拖动、OSC 52 toast |
| 无终端可用 | `features` 展品的验证命令表 | `--pages` / piped / headless 三行命令 |
| 帧率 / 性能 | 状态行 fps + `/fps` | 右下角读数 |

## 5. 展品语法（每页必须给观众的三样东西）

1. **这是什么** —— `header(title, blurb)`：一句定位。
2. **你该做什么** —— `try_line("…")`：可执行的指令（点哪、按什么、看什么）。
3. **它是什么 API** —— `api_note("…")`：一行可复制的调用/契约（`select.chosen`、`click(row, col)`、`ring.handle(event)`…）。

> 这三样是"更清晰更直观"的落点：观众不需要读源码就能知道**这是什么、怎么玩、对应哪行 API**。

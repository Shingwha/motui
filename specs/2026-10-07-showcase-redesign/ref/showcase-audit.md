# ref · 展示台现状审计（本次重构的现状底稿）

> 采集日 2026-10-07，仓库 `mocode-tui` @ `b397633`（interaction-model 六波全部合并后）。
> 行号为采集值，动手前按符号确认。本文件是本次重构的"改前"依据。

## 1. 现状规模

| 文件 | 行数 | 职责 |
|---|---|---|
| `examples/demo.py` | 84 | 入口：交互 / piped 回放 / `--pages` dump 三条路 |
| `examples/showcase/session.py` | 511 | 壳：banner、transcript、composer、scrollbar、toasts、gesture、`/split` 预览、宿主循环、流式回复 |
| `examples/showcase/components.py` | 249 | 六个组件页：data / structure / lists / fields / feedback / markdown |
| `examples/showcase/registry.py` | 111 | 页表 `PAGES`、palette 行、`/help` 文本、`Command` |
| `examples/showcase/page.py` | 71 | `Page` / `PageBody` / `header` / `section` |
| `examples/showcase/styles.py` | 95 | styles 页 |
| `examples/showcase/features.py` | 63 | features 页（能力表 + 三张 keymap 表） |
| `examples/showcase/chat.py` | 52 | chat 页（Message/ToolBlock/EditBlock/StatusLine + 一句话说明） |
| `examples/showcase/script.py` | 87 | headless 回放脚本（`HEADLESS_W/H` + `script()`） |
| `examples/showcase/content.py` | 82 | canned 文案：THEMES、REPLY_LONG/SHORT、THINKING、FIXTURE 路径 |
| `examples/Markdown-Rendering-Test.md` | 346 | Markdown 渲染 fixture（每种构造） |

## 2. 现有 10 页与它们各自的"展示缺口"

| 页 | 现在展示什么 | 缺口（本次重构要解决） |
|---|---|---|
| `overview` | 一段说明 + 页表（静态 Table） | 页表不可点、不是活索引；没有"这是本展台"的一句话定位 |
| `data` | Table（行光标，W6）+ Markdown 短样 + Text + Divider | 无互动指令；Markdown 是静态的 |
| `structure` | Panel/Row/Column/Padding + Tabs + Tree（FocusRing） | 不说明"tab/↑↓/enter/点击"要干什么；失焦变暗这个新特性完全没被点破 |
| `lists` | Select(20/6)+Confirm×2+Autocomplete | `chosen` 无声——宿主从不读它（W4 报告点名的缺口），观众看不到 activate 的结果 |
| `fields` | Input/Editor 四态 | 没有任何"点一下试试"（W5 的落点能力没演示）；粘贴语义没提 |
| `feedback` | ProgressBar/Spinner/Notice + 活条 | toast 只在复制时出现，反馈通道没有展品 |
| `styles` | 三主题 + 色卡 | `/theme` 是隐藏命令；主题切换不是展品的一部分 |
| `features` | 能力表 + 三张 keymap 表 | 表里的"how to see it"是文字描述，不是可做的动作 |
| `markdown` | 静态整页 fixture | **不流式**（用户点名的需求） |
| `chat` | 四个组件样张 + 一句话 | 回复流式（已有），但与 Markdown 页不是同一套机制 |

## 3. 壳的现状（`session.py`）

- **banner**：三条 pinned 块 —— `_title`（accent）、`_hint`（DIM）、`_rule`（Divider）；`_banner_labels()` 在换页/换主题时重绘。hint 一行拼 `↑↓/enter: <body.hint> · tab focus · c-o pane · enter sends · c-j newline · drag copies · ctrl-c quits`（110 列内单行）。
- **页切换**：只有 `/` palette → `Command` → `show(page)`；没有可见导航、没有前后页键。
- **事件路由顺序**（W4 定稿，`run()` 内，逐层 short-circuit）：
  `scrollbar.handle` → `toasts.handle` → `gesture.handle`（+ `_page_click`）→ palette →
  `playing and ring.handle`（composer 为空 + Key 无 char）→ `editor.handle` → `c-c` / `tab`(ring.focus_next) / `c-o`(窗格) / `escape` / `enter`(提交)。
- **点击**：`_page_click` 只把 stationary left click 交给 `self.body.focus`（ring）；pinned 块（banner）**不在**这条路上。
- **流式**：`_answer()` 里 `transcript.append(Message("user", …))` → thinking 逐词 → `Markdown` 块逐**行**前缀赋值（`_stream()`），每行 `invalidate()` + `sleep(LINE_DELAY | 0)`；`_beat()` 是"交互 sleep、headless sleep(0)"的唯一节奏点。
- **`--pages` 路径**（`demo.py`）：`Showcase(tui).show(page); tui.paint()` —— **不跑循环、不跑 tick**，所以任何"靠 tick/异步长出来"的内容在 dump 里必须是**已完成的**（dump-safe 规则）。

## 4. 键位占用（本次可用的空位）

`keys/keymap.py` 三张默认表 + 宿主已占：`left right home end c-a c-e backspace delete up down c-u`（Input/Editor）、`enter`（Editor/composer 差异）、宿主：`tab`、`c-o`、`c-c`、`escape`、`enter`、`/`（palette）。
**未被占用**：`c-n`、`c-p`、`c-t`、`c-w`（audit-interaction 第 6 节）。→ 前后展品用 `c-n`/`c-p`（已复测：全仓 grep 零命中）。

## 4b. 导航条宽度实测（D1 短标签决策的依据）

```
Tabs(12 个全名).render(110)   → 110 列，含 '…'（截断；截断 label 不可点）
Tabs(短标签示例).render(110)  →  97 列，无 '…'
短标签示例：over text struct menus fields feed styles keys shell interact stream chat
```
结论：导航条必须渲染 `Page.nav` 短标签；全名的 `/` 面板与 `--pages` 页头不受影响。

## 5. 门禁与基线（本组改前）

- `uv run pytest -q` → `948 passed, 1 skipped`
- `uv run python examples/demo.py < /dev/null` → exit 0，70 行 dump
- `uv run python examples/demo.py --pages` → exit 0，720 行、10 个 `── /<page>` 头
- `uv run python tools/framebench.py` → `render-hash: 5bcfdf164f89ca383194df2b1d3ac168137082220d690d708ba94c20423aba9a`（对固定 Markdown 文档，**本组不许动**）
- `uv run python -c "import mocode_tui"` → exit 0
- `uv run pytest tests/test_readme_examples.py -q` → `6 passed`（只执行 README 的 `## Quickstart`、`## Integrating with a host`、`## Styling: Theme`、`## Keys and keymaps` 四个标题下的 python 块；`## The demo` 段是 bash，随意改）

## 6. 测试面对展示台的态度

`tests/` 里**没有任何**用例断言 `examples/` 的页表或 dump —— 展示台的重构自由度在测试侧是全开的；它的契约只有 demo.py 的三条命令 + README 的叙述。（这份自由也意味着：**dump 的"正确"只能靠 lead 重记基线**，见总纲。）

## 7. 本次重构可直接依赖的新能力（interaction-model 组刚落地）
| 能力 | 位置 | 展示机会 |
|---|---|---|
| `Clickable.click(row, col)` 全量 | `core/block.py` + 五实现 | Tabs 条可当点击导航；表格/菜单/树可点 |
| `Activable.activate()` + `chosen` | `core/block.py`、`widgets/choice.py`、`widgets/table.py` | 宿主读一次 → toast/回声；控制条（D6 单项 Select 配方） |
| `FocusRing` + `focused` 失焦变暗 | `focus.py`、列表族 | 一页多控件、`tab` 循环、**失焦变暗肉眼可见** |
| `TextBuffer.place` / 字段可点 | `widgets/{textbuf,field}.py` | "点在你想要的位置"可现场演示 |
| bracketed paste（2004） | `core/{ansi,screen}.py` | 真机可粘多行；headless 回放可复现 |
| Table 行光标 | `widgets/table.py` | 数据表可驾驶 |

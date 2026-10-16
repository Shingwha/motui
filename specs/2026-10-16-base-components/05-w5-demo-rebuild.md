# Spec base-components · W5 demo 整体重做（波次 W5）
> ✅ 已合并 2026-10-16 @ `bc5-demo`（tip `851e07c`）→ main `32248e1`；demo exit 0，`--pages` 12 页 864 行。
> 分支 `bc5-demo`；前置：W4（库面定稿）。深读：`00-overview.md`（目标 4、D7）、
> 现状问题 5（demo 混杂）与 `specs/2026-10-07-showcase-redesign/ref/showcase-audit.md`（旧壳事实）。
> **最高约束：demo 是*一个*画廊，页面上没有常驻输入框；`/` 只开一个模态 `Palette` overlay，选完即关。
> 不设 `--app`：任何「完整 app 外壳」都是要删除的混杂源。**

## 目标

1. 删除 `examples/showcase/`（14 文件，`session.py` 935 行），新 `examples/gallery/` 包。
2. **单画廊**：pinned header（title + `Tabs` nav + hint + rule）+ 页面 + pinned 单行 `StatusLine`；
   `/` 开一个**模态 `Palette` overlay**（自带查询行，`widgets.Palette`），关掉即消失。
3. 页面按 **12 个类别**重组，每页一个主题、不跨主题混排；可交互件各自挂块。
4. 回放脚本瘦身：主力用 `/page` 命令 + 键盘驱动，坐标点击集中为顶部常量。
5. `demo.py < /dev/null`（piped 回放）与 `--pages` 仍是门禁契约。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| 旧入口三路（live / piped / `--pages`） | `examples/demo.py` |
| 旧壳与页面装配 | `examples/showcase/session.py`（935 行） |
| 旧页模型（`aside`/`sync` 钩子） | `examples/showcase/page.py` |
| 旧回放（大量硬编码坐标） | `examples/showcase/script.py` |
| fixture / 主题 / `blocks_of` | `examples/showcase/content.py`、`examples/Markdown-Rendering-Test.md` |
| 参考 overlay 控制器 | `src/mocode_tui/chrome.py`（`Toasts`：`paint(frame)->layout`、`handle`、`detach`） |
| 参考 band footer recipe（文档用，不进 demo） | `TUI.add_band(viewport)` / `remove_band()`（`app.py:500,518`） |
| 新原语与 tier | `Button` / `Checkbox` / `Link` / `Palette` / `StatusLine` / `Pointer` / `FocusRing` |

## 目录（新）

```
examples/
  demo.py                     # 入口：画廊（默认 interactive）/ --pages / piped 回放
  gallery/
    __init__.py
    content.py                # 主题变体、fixture 路径、blocks_of 拆分器（从旧 content.py 迁）
    page.py                   # Page / PageBody + exhibit 语法助手
    registry.py               # PAGES（12）+ 动作命令（分离）
    shell.py                  # header/status/PaletteOverlay 装配
    session.py                # Gallery 控制器 + 宿主循环
    script.py                 # 画廊 headless 回放
    pages/
      __init__.py
      overview.py content.py data.py structure.py input.py
      choice.py navigation.py action.py feedback.py
      styles.py streaming.py features.py
```

## 工单（按序执行，每项一个 commit）

### T1 `examples/gallery/page.py` + `content.py`

- `page.py`：`Page(name, nav, description, build)`（沿用 `nav` 短标签契约，总列宽 ≤ 屏宽单行不截断）；
  `PageBody(blocks, focus=None, hint="", tick=None, note=None, enter=None, leave=None)`。
  - `enter(gallery)` / `leave(gallery)`：页面挂载/卸载自有资源（pane、chrome），
    由 `show()` 在换页时调用（取代旧 `aside`/`sync`）。
  - exhibit 语法助手：`header(title, blurb, theme)` / `try_line(text, theme)` / `api_note(text, theme)` /
    `section(label, theme)`（从旧 `page.py` 迁，行为不变）。
- `content.py`：迁移 `THEMES` / `blocks_of` / `fixture_text` / `FIXTURE`（旧 `content.py` 去掉 canned 聊天回复，
  主题与拆分器保留）。
- 验证：`blocks_of` 的既有性质（每块携带其后空行、`"".join(blocks) == text`）保持；主题变体不变。

### T2 `examples/gallery/shell.py` + `session.py`：画廊壳与控制器

- `shell.py`：
  - **Header**（pinned top，4 块）：`Text`（标题 + 当前页）、`Tabs`（页 `nav` 标签，可点）、
    提示行 `Text`（当前页 `hint` + 全局键位，须屏宽内单行）、`Divider`。
  - **Status**（pinned bottom，1 块）：`StatusLine`，左 `<page> · focus=<target>`，右 fps。
  - **PaletteOverlay**：`paint(frame) -> layout` 的 overlay（参照 `chrome.Toasts`），在底部区域绘制
    `Palette` 的行并用 `Theme` band 打底；`open`/`close` 控制注册；关闭时 overlay 移除、零行。
    由 `/` 打开（宿主捕获 `/` 键，不经过任何常驻 editor）。
  - `Scrollbar(tui)`（primary pane）、`Toasts(tui)`、`SelectionGesture(tui, on_end=...)`、
    `Pointer(tui, ring=...)`、`TUI(hover=True)`。
- `session.py`：`Gallery(tui)` 控制器：
  - `show(page)`：关旧页 `leave` → 清 body 块 → 挂新页 `blocks` → 调 `enter` → 聚焦/滚顶/刷新 header+status。
  - 宿主循环 dispatch order（写进 docstring）：
    `scrollbar → toasts → palette（开着时）→ gesture → pointer → ring（键盘）→ 宿主键（c-n/c-p/tab/c-o// /q/c-c）`。
  - `/`：`palette.open()`；palette 消费的事件里读 `chosen` 一次 → `dispatch(name)`。
  - 命令表由 `registry.py` 提供（页面命令 + `split` / `theme` / `fps` / `quit`）。
  - **无常驻 editor**：`/` 之外没有文本输入；`Enter` 只在 ring 聚焦可激活件时有意义。
- 验证（探针）：进入/离开每页 body 块数与 `enter`/`leave` 调用计数；`/` 打开后 palette `is_open`、
  关闭后 overlay 消失；`tab` 在页 ring 内循环。

### T3 `examples/gallery/pages/**`：12 个类别页

每页一个主题、只讲这一主题；统一四件套（`header` / `try_line` / `section` / `api_note`）。
所有可交互件**各自挂块**；能聚焦的页返回 `FocusRing`。

| 文件 | 页名 | 主题 | 玩法要点 |
|---|---|---|---|
| `overview.py` | `overview` | 这是什么 + 可点索引 | 索引 `Select` 或 `Button` 列表 → 打开展项 |
| `content.py` | `content` | `Text` / `Markdown` | 静态 + 一段随宽度换行 |
| `data.py` | `data` | `Table` | 行光标 + `chosen` |
| `structure.py` | `structure` | `Panel` / `Row`/`Column` / `Padding` / `Spacer` / `Divider` | 只读展示 |
| `input.py` | `input` | `Input` / `Editor` | 点击落光标 + hover 整块 |
| `choice.py` | `choice` | `Select` / `Confirm` / `Autocomplete` | 激活 → `chosen` → toast + 页内 echo |
| `navigation.py` | `navigation` | `Tabs` / `Tree` | 点击 + `tab` 焦点 + 行 hover |
| `action.py` | `action` | **`Button` / `Checkbox` / `Link`** | hover 高亮、点击、`chosen` 回声（本组新原语主场） |
| `feedback.py` | `feedback` | `ProgressBar` / `Spinner` / `Notice` / `Toasts` | 一个 `tick` 动画 + 一个触发 toast 的选择器 |
| `styles.py` | `styles` | `Theme` | theme picker → 整壳换肤 + 色卡/属性/色彩形式表 |
| `streaming.py` | `streaming` | 流式 Markdown | 346 行 fixture 按块流入 + `Select` 控制条（play/pause/step/replay/speed），**dump-safe** |
| `features.py` | `features` | panes / scrollback / selection / **hover** / IME | 用 `enter`/`leave` 挂一个右 pane；文字说明 + 可做的动作 |

- `registry.py`：`PAGES`（12）+ `Command`（动作）；描述用一句英文；`nav` 短标签（总宽单行不截断）。
- `streaming` 页：非交互路径**构造即完整**（沿用旧 `MarkdownStream` 的 dump-safe 规则）；
  交互路径按 `PAGE_TICK` 节拍流入。
- 验证：`--pages` 每个页头都有内容、无空页；可交互页的 `chosen` 都有可见回声（toast 或页内行）。

### T4 `examples/demo.py` + `script.py`

- `demo.py`：
  - 无参 + tty → 画廊 interactive（`TUI(hover=True)`）；
  - `--pages` → 画廊 12 页文本 dump；
  - 无参 + piped → 画廊 headless 回放 + dump（**门禁契约**）。
  - module docstring 重写为英文：一个画廊、`/` 模态面板、键位、三条路径。
- `script.py`：**瘦身**——主力 `/page` 命令遍历 12 页；键盘驱动动作（`tab` / `↓` / `enter` /
  `c-n` / `c-p` / `c-o`）；坐标点击集中为文件顶部常量（selection / hover / pane 少量）；
  结尾 `q`/`c-c`。回放不得依赖某页的具体行号超过必要的少量锚点。
- 验证：`demo.py < /dev/null` 与 `--pages` 都 exit 0；`--pages` 页头数 = 12。

### T5 `README.md` demo 段 + 文档 recipe

- `README.md` `## The demo` 段重写：单画廊（无输入框）、12 页清单、`/` 模态面板、无终端两条路径；
  Quickstart/库章节**不动**（W4 已定）。
- `docs/COMPONENTS.md`：补一节 **「组装一个 app（recipe）」**——用 `tui.add_band(viewport)` +
  `Document` + `Editor` + `StatusLine` 自建 footer 的可复制配方（**只文档，不新增 demo 模式**），
  指向本仓 `tests/` 或 README 里可跑的最小片段。
- 验证：README 代码块仍被 `tests/test_readme_examples.py` 执行通过。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` 全绿（贴数字；demo 无专属单测，靠回放与 dump）。
2. `uv run python examples/demo.py < /dev/null; echo exit=$?` → exit 0；dump 里可见：
   header 的 `Tabs` 行、当前页内容、底部 `StatusLine`，且**没有任何常驻输入框**（grep dump 无 editor 光标行）。
3. `uv run python examples/demo.py --pages` → exit 0；页头 = **12**（贴清单）与总行数；
   逐页无空页；`action` 页含 `Button`/`Checkbox`/`Link` 的行；`streaming` 页完整。
4. `/` 面板探针（贴输出）：打开后 overlay 出现、过滤生效、`enter` 取 `chosen`、关闭后 overlay 消失。
5. hover 探针（贴输出）：`Pointer` 在 `action` 页悬停 `Button` 时该行渲染含 `theme.hover`。
6. `streaming` 页探针：交互路径首帧为部分文档、`tick` 后增长；非交互路径首帧即完整 fixture。
7. `uv run python tools/framebench.py` → 报 hash 是否变化（W5 预期变化，基线由 W6 重录；
   此处只如实报告，不改 spec）。
8. 真机项（画廊观感、`/` 面板、hover、pane、selection）→ 无法执行，列「lead 终验项」。

## 禁触清单

- `src/**`、`tests/**`（本波只动 `examples/`、README demo 段、COMPONENTS 的 recipe 小节；
  要改库先停下上报）
- README 的 Quickstart / 库章节（W4 的成果；demo 段除外）
- `specs/**`（spec 归 lead）

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论（逐条 + 关键输出行 + 页头数/行数）/
画廊 dump 片段（证明无常驻输入框）/ `/` 面板探针 / hover 探针 / streaming 探针 /
framebench hash 变化说明 / 偏差与取舍 / 未决问题 / 真机手测：未执行（lead 终验）。

遇到阻塞（`Palette` 作为 overlay 的绘制/输入路由不顺、`streaming` dump-safe 在 headless 下不稳定、
回放仍不得不依赖大量坐标）：**停下上报，不越界自救**。

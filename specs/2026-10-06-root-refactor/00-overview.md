# Spec root-refactor · 总纲

> 操作启动日 2026-10-06。本组是一次**从根源的体系重构**：统一命名与接口、消除补丁式代码、
> 删除冗余、强化自定义能力，并把 example 重写为 `demo.py`。**不考虑向后兼容**——改名即删除旧名，
> 不留 shim、不留 alias、不留弃用期（这是库自己在 `docs/DESIGN.md` 写下的契约，本次贯彻到底）。

## 背景与问题清单

上次重构后，修复 bug、新增功能、性能优化都没有回归到统一设计上，代码出现三类问题
（完整审计证据在 `ref/audit-*.md`，worker 领工单后**必读**自己波次对应的审计文件）：

1. **补丁式代码**：`Pane.split` 调私有 `frame._adopt` 绕过 driver 的 retile no-op；
   `apply_overlays` 把运行中 layout 写回对象状态供两处隐式读取；`_paint_at` 在绘制路径里
   顺手清选择状态；Markdown 流式缓存 70 行混在组件类内带脆弱哨兵；`tui._clock()` 这个
   "tests monkeypatch 的 seam" 成了 chrome/selection 的正式依赖。
2. **命名与契约分裂**：同一"消费事件"语义三个名字（`handle_key -> bool`、
   `handle -> bool`、`handle_key -> str|None|False`）；挂载动词四种（attach/set/add/show）；
   `Input.text` vs `Editor.value`；`Input.cursor: int` vs `Editor.cursor: (row,col)`；
   `TUI.print` 覆盖内建名；19 处 `theme or DEFAULT_THEME` 复制；样式参数前缀漂移。
3. **冗余与死代码**：`StatusBar` 零消费者（被 `StatusLine` 取代）；`Spinner.render` 死方法；
   `Input`/`Editor` 对 `TextBuffer` 逐条转发 11 个方法；两套按权重切矩形算法；
   分隔线两套实现两处注册；ownership 表四重形态；`split_rect`/`index_at_column`/
   `Block.set_component`/`Frame.pane_layouts`/`Text.theme`/console.py 死函数等仅测试引用或零引用。

## 目标体系（重构后的形状）

包结构不动骨架，消除同名冲突、贯彻分层：

```
mocode_tui/
  __init__.py        # 唯一 curated 面（目标 ~64 名，见 05 工单定稿名单）
  app.py             # TUI 驱动（组装根；import core + keys）
  chrome.py          # 帧装配件：Scrollbar + Toasts + Separator（import app + core）
  gesture.py         # 交互策略：SelectionGesture + copy_on_select（原 selection.py 改名）
  testing.py         # headless_tui / snapshot
  core/              # L0 内核：零上游依赖（Text 组件迁入 lines.py，text.py 纯测量）
  keys/              # 输入：decoder/keymap（三张默认 keymap 表同堂）/sources/console
  widgets/           # L1 通用组件（import core；chrome.py 改名 decor.py）
    markdown/
  chat/              # L2 对话层：组件 + 控制器（import core+widgets+app；措辞去 pi 化）
```

依赖方向不变：core ← keys ← widgets ← chat，装配件（app/chrome/gesture/testing）在最上。

## 命名宪法（本次定稿，全部波次遵守）

| 概念 | 统一名 | 淘汰名 |
|---|---|---|
| 消费一个事件 | `handle(event) -> bool` | `handle_key`（widgets/TextBuffer/SlashPalette 的）、SlashPalette 三态返回 |
| 点击交互 | `click(row) -> bool`（组件内部消化 title 偏移等算术） | 宿主侧块内行号算术 |
| 列表移动/激活 | `move(delta)` / `activate(index)` | — |
| 冻结一块 | `seal()`（Block 与 StreamHandle 一致） | 文档里的 "freeze" 措辞 |
| 控制器挂载 | **构造即挂载**（`Composer(tui, …)`、`Scrollbar(tui)`、`Toasts(tui)`、`Transcript(tui)`）+ `detach()` 显式卸载 | `Composer.attach(tui)` |
| 文本属性 | `.text`（内容可变） | `Editor.value` |
| 光标 | `cursor -> tuple[int, int]`（row, col；单行组件 row 恒 0） | `Input.cursor: int` |
| 驱动的系统消息 | `tui.system(text)` | `tui.print` |
| 视口行范围 | `tui.viewport_rows -> (first, last) \| None` | `viewport_region()` |
| 泵/时钟 seam（转正公开） | `tui.clock()`、`tui.tick(now)` | `tui._clock`、`tui._tick` |
| 主题解析 | `Themed` 基类（`core/theme.py`）：构造 `theme or DEFAULT_THEME`，渲染时 `style=` > theme 字段 | 19 处手写 `theme or DEFAULT_THEME` 模板 |
| keymap 三表 | 同居 `keys/keymap.py`（INPUT → EDITOR → COMPOSER 派生链一处可见） | `chat/composer.py` 里的 COMPOSER_KEYMAP 定义 |
| 帧结构变更 | `Frame.revision` 递增计数，driver 据此判 retile 必要性 | `_adopt` 补丁、(rect, band) 相等判据 |
| 事件模型判序 | `Key \| Paste` 即可（MouseEvent 是 Key 子类，判序已在审计中写明） | 冗余的 `Key \| Paste \| MouseEvent` 标注 |

**组件构造规则**：内容参数可为位置参数；样式参数全部 kw-only、语义前缀 + `_style` 后缀；
有颜色的组件一律带 `theme=`；样式在构造时解析并存私有 `_style*`（公开可变样式属性一律删除，
内容属性如 `Text.text`、`Divider.label` 保持公开可变）。

## 全局不变量（每一波、每一个 commit 都成立）

1. **渲染字节不变**：`uv run python tools/framebench.py` 输出的 `render-hash` 在 W1–W5 期间
   恒等于 `5bcfdf164f89ca383194df2b1d3ac168137082220d690d708ba94c20423aba9a`（基线存
   `ref/render-hash-baseline.txt`）。W6 替换 demo 后建立新基线并记录进本组 `ref/`。
2. **测试全绿**：`uv run pytest -q` 零失败（基线 843 passed, 1 skipped；数量随删除项变化，
   失败必须为零）。
3. **demo 管道活着**：W1–W5 期间 `uv run python examples/pi_demo.py < /dev/null` 退出码 0
   （波次对其调用点做机械同步）；W6 用 demo.py 取代。
4. **分层不破**：core 不 import keys/widgets/chat/装配件；keys 只 import core；
   widgets 不 import keys 之外的上游（input/editor 的 keymap 来自 keys.keymap，现状保留）；
   chat 不被 widgets/core import。
5. **不加兼容层**：改名即删旧名；发现旧 shim 失去消费者时顺带拆除。
6. **无 sleep**：库与测试内禁止新增任何 sleep（时钟经 `tui.clock()`/注入）。

## 波次表

| 波次 | 分支 | 写入范围（文件级隔离） | 依赖 |
|---|---|---|---|
| W1 内核整理 | `rr/w1-core` | `src/mocode_tui/core/**`、`tests/test_{frame,viewport,block,painter,core_text,ansi,style,theme,selection,screen}.py` | 无 |
| W2 事件契约+keys | `rr/w2-events` | `src/mocode_tui/keys/**`、`src/mocode_tui/widgets/{input,editor,textbuf}.py`、`src/mocode_tui/chat/slash.py`、`src/mocode_tui/chat/__init__.py`（仅 COMPOSER_KEYMAP import 行）、`tests/test_{keys,keys_sources,widgets_editing,chat_slash,readme_examples}.py`、`tests/_doubles.py`、`examples/pi_demo.py`（仅机械同步调用点） | 无（与 W1 并行，文件不相交） |
| W3 组件层清理 | `rr/w3-widgets` | `src/mocode_tui/widgets/**`（decor 改名含 `widgets/__init__.py`）、`src/mocode_tui/chat/{composer,transcript,message,tools,statusline}.py`、`src/mocode_tui/chat/__init__.py`、根 `__init__.py`（仅 StatusBar/StatusSegment 删除行）、`tests/test_widgets_*.py`、`tests/test_chat_{components,composer,statusline,transcript}.py`、`tests/test_theme.py`、`examples/pi_demo.py`（仅机械同步） | W2（handle 契约） |
| W4 驱动层整理 | `rr/w4-driver` | `src/mocode_tui/app.py`、`src/mocode_tui/chrome.py`、`src/mocode_tui/selection.py`→`gesture.py`、`src/mocode_tui/core/frame.py`（仅 revision/adopt/分隔线段）、根 `__init__.py`（仅 `.selection`→`.gesture` import 行）、`tests/test_app.py`、`tests/test_chrome_*.py`、`tests/test_selection_gesture.py`、`tests/test_api_root.py`（仅 gesture 行）、`tests/test_readme_examples.py`（print→system 行）、`examples/pi_demo.py`（仅机械同步） | W1（frame.py） |
| W5 API 面+文档 | `rr/w5-api` | 根 `__init__.py`、全部层 facade `__init__.py`、`tests/test_api_root.py`、`tests/test_readme_examples.py`、`README.md`、`docs/DESIGN.md`、`docs/COMPONENTS.md` | W3 + W4 合并后 |
| W6 demo+收尾 | `rr/w6-demo` | `examples/demo.py`（新）、`examples/pi_demo.py`（删）、`tools/framebench.py`、`src/mocode_tui/core/painter.py`（frames 计数）、`tests/test_painter.py`、`README.md`（demo 段） | W5 |

合并顺序 = 表序。W1 先于 W2 合并（core 是地基）；W3 先于 W4（W4 的 gesture 改名测试依赖 W3 的
组件清理不冲突，但契约测试顺序更稳）。lead 在每次合并前后各跑一次全量门禁。

## 回归红线（合并门禁，lead 逐条贴真实输出）

```
uv run pytest -q                                   # 零失败
uv run python tools/framebench.py                  # render-hash == 5bcfdf…（W1–W5）
uv run python examples/pi_demo.py < /dev/null      # exit=0（W1–W5；W6 起换 demo.py）
```

## Git / worktree 协议（本组通用，工单不再重复）

- worktree 由 lead 创建于 `C:\Users\shifu\.worktrees\mocode-tui\<分支名>`，分支从**合并时刻的最新 main** 切出。
- worker 绝不操作主检出、绝不 merge / push / tag / checkout main；工作只在自己的 worktree 与分支上。
- 每个 commit 独立过门禁（pytest 全绿 + render-hash 不变 + demo 可运行），不留"改一半"的中间态。
- commit message 英文，格式 `refactor(w<N>): <祈使句摘要>`（与仓库既有 `perf:`/`fix:` 风格一致）。
- **spec 归 lead 所有**：worker 不更新任何 spec、不写状态；完成信号 = 最终报告 + 分支 commit。
- 完成后 worker 停在分支上等 lead 合并；lead 合并后销毁 worktree、保留分支。

## 语言与文档约定

- 代码、docstring、注释、commit：**英文**（沿用仓库现状）。
- 本组 spec：中文。
- 顺带清理的义务：凡是波次触碰的文件，其中的历史包袱注释（"since the frame wave"、
  "the W2 mechanism"、"used to live at"、"W8/W11 palette migration" 等）一律删除或改写为
  现在时的设计陈述；**本波次写入范围之外的文档（README/docs）不动**（W5 统一收口）。

## 诚实出口

若某项清理被发现与字节级渲染等价冲突（例如缓存化改变了浮点/求值顺序），允许降级为
"pytest 全绿 + 渲染断言等价"，但必须在最终报告的"偏差与取舍"里声明冲突点与量化依据；
宁可不改，不可悄悄改渲染。阻塞即停：报告阻塞点后停止，不越界自救。

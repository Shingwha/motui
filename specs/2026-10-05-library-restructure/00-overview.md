> ✅ 全波次(W1-W7)已合并 main(2026-10-05)

# 2026-10-05 library-restructure · 总纲

> 把 mocode-tui 重构成完整、可扩展、易用的分层 TUI 库,供 mocode 主体直接 import 替换其 CLI。
> 不考虑向后兼容:旧 `components/` 包整体拆除,不留 shim、不留兼容别名。

## 目标与范围

一次到位的全仓重构:

1. **三层包结构**:`core/`(内核) / `keys/`(输入) / `widgets/`(通用组件) / `chat/`(pi 风格 coding-agent 组件,mocode 专用)。
2. **Theme 主题系统**:frozen dataclass 集中管理全部语义样式,组件 `style=None` + `theme=None` 双参数,显式 > theme > DEFAULT_THEME。
3. **Keymap 体系**:键名→动作名的可配置映射,`Input`/`Editor` 以 `handle_key(key) -> bool` 消费编辑键,未映射键交还宿主。
4. **内置轻量语法高亮**:零新依赖(保持 wcwidth 唯一),Markdown 围栏块接入,协议可注入替换。
5. **hit_test 鼠标点击**:Viewport 记录行归属,TUI 暴露命中测试,decoder 放开按键按下事件。
6. **新组件**:Editor、Autocomplete、ProgressBar、Tabs、Tree、Spacer、Padding(widgets);StatusLine、SlashPalette、Composer、Transcript(chat)。
7. **定稿**:root API 策展、demo 用 chat 层重写、docs 重写、版本 0.2.0。

## 目标包结构(终态)

```
src/mocode_tui/
├── __init__.py            # 精选公共 API(W1 建立 / W7 定稿)
├── core/
│   ├── style.py           # Style + Theme + 语义常量
│   ├── text.py  lines.py  ansi.py
│   ├── block.py           # Component 协议(冻结)/Block/Document
│   ├── screen.py  viewport.py  painter.py
│   ├── app.py             # TUI + EveryHandle + hit_test(W5)
│   └── testing.py
├── keys/
│   ├── events.py  decoder.py  sources.py  console.py
│   └── keymap.py          # W2 新增
├── widgets/
│   ├── text.py  markdown.py  table.py  spinner.py
│   ├── input.py           # W2 改造为 keymap 驱动
│   ├── editor.py          # W2 新增
│   ├── choice.py          # W5 加 click
│   ├── autocomplete.py    # W4 新增
│   ├── progress.py        # W4 新增
│   ├── tabs.py            # W4 新增
│   ├── tree.py            # W4 新增
│   ├── layout.py          # Row/Column + Spacer/Padding(W4)
│   ├── chrome.py          # Notice/Divider/Panel
│   ├── status.py
│   └── syntax.py          # W3 新增
└── chat/                  # W6 建立
    ├── message.py  tools.py
    ├── statusline.py  slash.py  composer.py  transcript.py
```

## 波次表

| 波次 | 名称 | 分支 | 前置 | 并行 |
|---|---|---|---|---|
| W1 | 结构迁移 + Theme | `lib-w1-structure` | — | 串行 |
| W2 | keymap + Input/Editor | `lib-w2-keymap-editor` | W1 | ∥ W3 W4 W5 |
| W3 | 语法高亮 + Markdown 接入 | `lib-w3-syntax` | W1 | ∥ W2 W4 W5 |
| W4 | 新通用组件 | `lib-w4-widgets` | W1 | ∥ W2 W3 W5 |
| W5 | hit_test 鼠标点击 | `lib-w5-hit-test` | W1 | ∥ W2 W3 W4 |
| W6 | chat 层 | `lib-w6-chat` | W2+W3+W4 合并 | 串行(W5 不冲突可不等,但按序合) |
| W7 | 定稿 | `lib-w7-finalize` | W6 | 串行 |

合并顺序 = W1 → W2 → W3 → W4 → W5 → W6 → W7。并行波从「W1 合并后的 main」各自建分支。

## 全局不变量(每波每 commit 都必须满足)

1. `uv run pytest -q` 全绿(贴真实输出)。
2. `uv run python examples/pi_demo.py < /dev/null` exit 0;W1 额外要求输出与 `ref/w1-demo-dump.txt`(sha256 `0475a382…b7fb73`)**字节级一致**。
3. 组件协议 `render(width) -> list[Line]` 冻结,不得改动签名与语义。
4. 非 TTY 契约不动:静默运行、`read_key()` 返回 None、退出时纯文本转储。
5. 库与测试零 sleep;零新运行时依赖(pyproject dependencies 保持 `wcwidth` 唯一)。
6. 注释与文档用英文(与现状一致),commit message 沿用仓库现有风格(小写前缀 `feat:/fix:/refactor:/demo:` 等)。

## 写入隔离铁律(并行波)

- **禁触**:`src/mocode_tui/__init__.py`、`core/__init__.py`、`widgets/__init__.py`、任何 facade 的 `__all__` —— 归 lead/W7 策展。并行波的新符号只通过自己的模块全路径暴露(如 `from mocode_tui.widgets.progress import ProgressBar`),测试也走全路径。
- **禁触**:`tests/test_api_root.py`(W7 定稿)、`pyproject.toml`(W7  bump 版本)、`docs/`、`README.md`、`examples/`(W7)。
- 每波工单逐文件写明写入范围与禁触清单;越界即停、上报 lead。

## Git / worktree 协议

- worktree 根:`C:\Users\shifu\.worktrees\mocode-tui\<分支名>`,lead 统一创建与销毁。
- 分支从合并时刻的最新 main 创建;agent 不 merge、不 push、不 tag、不 checkout main、不碰主检出与其他 worktree。
- 每个 commit 独立过门禁;合并用 `git merge --no-ff`。
- Git 协议细节遵循 spec-team SKILL 约定,本总纲不再重复。

## 验收(终验,W7 收尾)

1. `uv run pytest -q` 全绿(旧 203 测试迁移 + 新组件契约测试)。
2. demo 交互/管道双模式正常;管道输出重基线到 `ref/w7-demo-dump.txt`。
3. README quickstart 代码实测可跑;docs/DESIGN.md 与 docs/COMPONENTS.md 反映终态结构。
4. `from mocode_tui import ...` 一站式导入成立;`mocode_tui.core/widgets/chat/keys` 四个 facade 各自成立。

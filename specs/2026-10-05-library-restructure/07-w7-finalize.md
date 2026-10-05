> ✅ 2026-10-05 @ 分支 lib-w7 — 已合并 main

# Spec W7 · 定稿:API 策展 + demo 重写 + 文档(波次 W7)

> 分支 `lib-w7-finalize`;前置:W6 已合并;深读:总纲、全部已合并波的最终报告、`src/mocode_tui/__init__.py`、`examples/pi_demo.py` 全文、`README.md`、`docs/`。

## 目标

收尾为完整可发布包:root API 与四个 facade 策展定稿、demo 用 chat 层重写、文档重写、版本 0.2.0、管道输出重基线。

## 工单(按序执行,每项一个 commit)

### T1 root `__init__.py` 与 facade 策展

- `mocode_tui/__init__.py`:面向「mocode 主体一行 import」策展。导出:TUI 驱动面(TUI/EveryHandle)、文档模型(Component/Block/BlockState/Document)、渲染核心(Painter/Viewport/ScreenLayout/Screen/TerminalScreen/HeadlessScreen)、keys(Key/Paste/MouseEvent/KeyDecoder/KeySource/ScriptedKeys/RawTerminalKeys + Keymap/DEFAULT_INPUT_KEYMAP/DEFAULT_EDITOR_KEYMAP)、全部 widgets、全部 chat 组件、Style/Theme/DEFAULT_THEME + 语义常量、Line/Segment/wrap_line、测量三函数、testing 两件、Hit(W5)、Highlighter/RegexHighlighter(W3)。
- `core/__init__.py`、`widgets/__init__.py`、`chat/__init__.py`、`keys/__init__.py` 各自 `__all__` 完整准确;`keys/__init__.py` 的 transitional seams 全部拆除(若仍在)。
- `tests/test_api_root.py` 重写:锁定 root `__all__` 终态清单 + 四 facade 清单;断言无 `components` 残留、无下划线私名泄漏。
- 命名冲突裁决:widgets 与 chat 若有同名符号,chat 侧优先以独特名导出;冲突逐个列在报告里。

### T2 demo 重写

- `examples/pi_demo.py` 用 chat 层重写:Composer.attach 装底部区、Transcript 管消息流、SlashPalette 注册命令、StatusLine 双侧状态、working 走 `composer.set_working`。目标 ~200 行;删除全部 `_MenuSlot/_WorkSlot/_StatusRow/_Row` 私有件(已由库提供)。
- 保持演示内容(banner、流式 markdown、工具块、编辑块、表格、slash palette、IME 锚点、后台 turn)——观众看到的功能不缩水;视觉允许因 W3 高亮与 Theme 化产生合理差异。
- 双模式保留:TTY 交互 + 非 TTY 管道回放。
- 管道输出重基线:`uv run python examples/pi_demo.py < /dev/null > specs/2026-10-05-library-restructure/ref/w7-demo-dump.txt`,sha256 写进报告。

### T3 文档重写

- `README.md`:新 quickstart(15 行内跑起一个带输入的 app)、包结构图、组件目录表(widgets/chat 分开)、Theme 自定义示例、keymap 自定义示例、mocode 集成形态段(Composer+Transcript 五行样例)、「Not on purpose」清单更新。
- `docs/DESIGN.md`:模块图更新为 core/keys/widgets/chat;hit_test、keymap、高亮各补一节;「Deliberately out of scope」更新(math、拖滚动条、SGR 1002)。
- `docs/COMPONENTS.md`:按 widgets/chat 重组组件表;新增组件逐一入表;Theme 字段表替换旧常量表;「Building your own component」保留。
- quickstart 与集成样例代码必须实测可跑(写入 `tests/test_readme_examples.py` 或以脚本实测,报告贴输出)。

### T4 版本与杂项

- `pyproject.toml`:version = "0.2.0";description 更新为分层库表述;确认 dependencies 仍只有 wcwidth。
- 全仓 grep 清零:`mocode_tui.components`、`from .components`、已删常量名(USER_BG 等旧模块常量引用)。
- `.zcode/` 保持 untracked,不入 commit。

## 验收

1. `uv run pytest -q` 全绿(贴真实输出,总用例数)。
2. `uv run python examples/pi_demo.py < /dev/null` exit 0,输出已重基线。
3. `uv run python -c "import mocode_tui; assert 'Composer' in mocode_tui.__all__ and 'Theme' in mocode_tui.__all__"` 通过。
4. README quickstart 实测输出贴报告。
5. `grep -rn "mocode_tui\.components\b" src tests examples docs README.md` 零命中。

## 禁触清单

不改 `core/` 内部实现逻辑(除 facade 与明显遗漏导出);不改各波已交付组件的行为语义(发现 bug 记录并报 lead,不擅自修)。

## 最终报告格式

工单状态表 / commit 清单 / 全部验收项真实输出 / root `__all__` 终态清单 / 重基线 sha256 / 偏差与取舍 / 遗留清单(给 mocode 侧集成的注意事项)。

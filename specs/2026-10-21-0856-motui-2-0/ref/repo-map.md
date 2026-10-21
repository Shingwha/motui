# Repo map — motui 2.0

## 目录

| 路径 | 职责 |
|---|---|
| `src/motui/kernel/` | 根层：Style/Theme/Glyphs、事件、文档模型、屏幕/视口/frame、selection、Host |
| `src/motui/keys/` | 解码、keymap、终端来源 |
| `src/motui/widgets/` | 组件库、Markdown、Syntax |
| `src/motui/interaction/` | focus/pointer/gesture/find/modal/overlays/scrollbar |
| `src/motui/app.py` | `TUI` 驱动与组合根 |
| `src/motui/demo/` | `python -m motui` 的 demo |
| `tests/` | 824 行为契约 + golden 帧 |
| `tools/` | `golden.py`、`framebench.py` |
| `docs/` | CONTRACT / DESIGN / COMPONENTS |

## 命令（统一用 uv）

主检出：

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages > /tmp/pages.txt
```

worktree：先 `uv sync --locked`（会为 worktree 创建本地 `.venv`），之后同上。
若 `uv sync` 因网络失败，用主检出的 venv + `PYTHONPATH="$PWD/src"` 兜底，并在 handoff 记录。

## 关键类型

- `Style` / `Color`：SGR 值类型，truecolor + ANSI 锚点。
- `Theme`：10 个 role group，见 `ref/interfaces.md`。
- `Palette`：品牌色创作层，只用于 `Theme.from_palette()`。
- `Glyphs` / `Border`：默认字符与框线，独立于 Theme。
- `Component.render(width) -> list[Line]`；`Block.rows` 缓存。
- `Host`：interaction 层看到的驱动 seam。

## 约定

- 英文 docstring/注释；commit `area: imperative summary`。
- 测试只读（只有 W1 为了让旧 Theme 构造通过而机械更新测试；W3 更新视觉断言）。
- 不手改 golden；W3 用 `tools/golden.py --update` 统一重录。
- 不新增兼容 shim；W1 的兼容属性是临时脚手架，W4 删除。

## 环境陷阱

- Windows + Git Bash；worktree 放 `C:\Users\shifu\.worktrees\mocode-tui\`。
- 并行 pytest 带 `-p no:cacheprovider`。
- `--pages | head` 在 Windows 会 `Errno 22`，重定向到文件。
- `uv run` 首次可能较慢；不要并行多个 `uv sync` 抢锁。
- golden 比较是字节级；Windows CRLF 只接受整文件 LF→CRLF。

## 找 X

| 想找 | 位置 |
|---|---|
| Theme/Palette/Glyphs | `kernel/{theme,glyphs,style}.py` |
| 行带 | `widgets/bands.py`（W4 前保留） |
| 控件族 | `widgets/{action,choice,textfield,form,combobox,autocomplete,dialog}.py` |
| 列表导航 | `widgets/{list,tree,navlist,tabs,menubar,strip,rows,scroll,collapsible}.py` |
| 数据内容 | `widgets/{table,decor,diff,indicators,syntax}.py`、`widgets/markdown/` |
| interaction | `interaction/{find,modal,overlays,palette,scrollbar}.py` |
| 公开面测试 | `tests/test_api.py` |

# 仓库地图（2.1.2 语义重构）

> 基线：main @ `ca3e53c`（2.1.0 + demo showcase rebuild），2026-10-29 17:04。
> 所有命令在仓库根执行，使用 `uv`。

## 1. 目录职责

```
src/motui/
  kernel/    纯值层：Cell/Segment/Line/Surface、Style/Theme、text 测量、
             geom/layout/scroll、events、document/Section、selection、
             frame、KeyDecoder。无 I/O，不 import 上层。
  pixel/     可选子格栅格：Raster、PixelPalette、PixelLayer、Marker、quantize。
             只 import kernel。
  widgets/   组件库：base（Widget/Container/HasResult）、cursor、mark、
             action（Button/Checkbox/Link）、choice、list、table、tree、
             tabs/menubar/navlist/strip、combobox/autocomplete、
             text/textfield/textbuf、form/dialog、layout、decor、scroll、
             indicators、diff、rows、syntax、markdown/、canvas、pixel_canvas。
  app/       Runtime/Workspace/App、FocusManager、Pointer、Gesture、Find、
             Modal/CommandPalette、overlays、scrollbar、commands。
  terminal/  Screen/Painter、ANSI、输入解码、capability。
  testing/   headless_tui、snapshot、Emulator、Rows/texts 等测试夹具。
  demo/      13 个场景的 showcase（splash、menu、components、layout、motion、
             dashboard、terminal、themes、gallery 等）。
tests/       镜像包布局；golden/semantic/ 有 9 个场景快照。
docs/        ARCHITECTURE / CONTRACT / WIDGETS / MIGRATION / adr/ / releases/
tools/       api.py（公开面快照）、semantic.py（场景 golden）、
             framebench.py（性能/render-hash）、growth.py
specs/       历次工程的 spec 组；本组是 2026-10-29-1704-widget-semantics。
```

## 2. 入口点与核心模块

- 包入口：`src/motui/__init__.py`（curated face，约 40 名）；`__main__.py` 进 demo。
- 公开面共 7 个 facade：`motui`、`motui.kernel`、`motui.pixel`、`motui.terminal`、
  `motui.widgets`、`motui.app`、`motui.testing`。
- 组件基类：`src/motui/widgets/base.py`（`Widget`、`Container`、`HasResult`）。
- 游标算术：`src/motui/widgets/cursor.py`（`Cursor`）。
- 多选集合：`src/motui/widgets/mark.py`（`MarkSet`）。
- 键位描述符：`src/motui/widgets/strip.py`（类名 `Keymap`，不是
  `KeymapDescriptor`；`__get__`/`__set__` 提供类默认表 + 实例副本）。
- 焦点/激活回退：`src/motui/app/focus.py`（`FocusManager.handle` 目前只有
  `enter` → `activate()`；本工程加 `space`）。
- 场景入口：`src/motui/demo/registry.py`、`scene.py`、`preview.py`。

## 3. 构建、测试、lint 命令（已实测）

```bash
uv run pytest -q -p no:cacheprovider          # 1663 tests collected @ 基线
uv run ruff check .                            # 基线全绿
uv run pyright                                 # 基线全绿
uv run lint-imports                            # 5 contracts kept
uv run python tools/api.py --check             # 188 行公开面快照
uv run python tools/semantic.py --check        # 9 个场景 golden
uv run python tools/framebench.py              # 11 项计时 + render-hash
```

单文件/单用例：

```bash
uv run pytest -q tests/widgets/test_contracts.py
uv run pytest -q tests/kernel/test_cell.py -k overlay
uv run ruff check src/motui/kernel/cell.py tests/kernel/test_cell.py
uv run pyright src/motui/kernel/cell.py
```

注意：`pyproject.toml` 的 ruff `exclude` 目前排除了 `src/motui/widgets`、
`src/motui/app`、`tests/widgets`、`tests/app`、`tests/terminal`、`tests/golden`、
`src/motui/__init__.py`；这些目录的改动不会被全仓 ruff 检查，worker 需对
自己改的文件单独跑 `ruff check <paths> --config "exclude=[]"`（与
`CONTRIBUTING.md` 的 pixel_canvas 命令同法）。pyright 只检查 kernel、pixel、
testing、pixel_canvas 和 tools；widgets 其余文件不在类型检查范围。

## 4. 关键类型、接口、数据流

- 渲染协议：`Component.render(c: Constraints) -> Surface`。
- `Constraints(width, max_height=None)`；组件必须自己遵守 `max_height`。
- `Surface.of(rows, width)` 补齐；`Surface.clipped(rows, width)` 不补齐。
- `Line` 由 `Segment` 组成；`Segment(text, style, link, action)`。
- `Widget` 的公开属性赋值自动 `touch()`；列表原地修改要手动 `touch()`。
- 焦点环 = 每个 pane/dock 文档里的 `focusable` 前序列表；`focus_scope` 截断下降。
- 键盘路由：`FocusManager.handle` → 目标 `keymap[key]` → `on_action` →
  `on_key` → `activatable` 的 enter 回退。
- 点击路由：`Frame` 命中 → `FocusManager.click` 走 `child_at` 链，最深
  `clickable` 叶子收 `on_click`，祖先收 `focus_at`。
- 结果：`take()` 读一次清空；`None` 表示无结果（Dialog 的取消是“调用 take
  本身”这个信号）。
- 主题：`Theme` 十个角色组；`Widget.group(name)` 按 `styles` 覆盖 > 组件
  theme > `DEFAULT_THEME` 解析。

## 5. 约定

- 注释/docstring：英文，第三人称现在时；模块 docstring 说明职责与边界。
- commit：短祈使句，可带 `wave:` 前缀；本工程建议
  `w1: ...`、`w2: ...`，每波一个或多个 commit。
- 测试：一个源模块一个测试文件；跨组件契约放 `test_contracts.py`（本工程
  并行波用 family 专属契约文件避免写冲突）。
- 不引入 alias/shim；旧名直接删。
- 不主动 push / tag / 发版，等 lead 的 W8。

## 6. 环境陷阱

- Windows + Git Bash；路径用正斜杠。worktree 放
  `C:/Users/shifu/.worktrees/mocode-tui/`。
- 每个 worktree 首次 `uv run` 会建自己的 `.venv`；共享 uv 缓存，通常几十秒。
- `uv run python tools/semantic.py --update` 只能为**有意的**视觉变化重录；
  普通重构后必须 `--check` 全绿。
- `tools/api-2.1.txt` 由 lead 独占更新；worker 不提交。
- `src/motui/demo/` 的 `__pycache__` 和 `dist/` 不入库；不要清理用户未跟踪文件。
- `specs/` 在 sdist exclude 里，但在仓库中提交。
- 测试用 `pytest-asyncio` 的 auto 模式；不要在测试里引入真实时钟。

## 7. “找 X 去哪”

| 找什么 | 去哪 |
|---|---|
| 组件构造签名 | `src/motui/widgets/<family>.py`；`uv run python -c "import inspect,motui.widgets as w; ..."` |
| 公开导出 | `src/motui/widgets/__init__.py`、`src/motui/__init__.py`、`tools/api-2.1.txt` |
| 焦点/激活回退 | `src/motui/app/focus.py` 的 `FocusManager.handle` / `click` |
| 键位默认表 | 各组件的 `keymap = Keymap({...})`；`strip.py` 的描述符 |
| 状态/结果 | 各组件的 `index`/`selected`/`take`；`widgets/cursor.py`、`mark.py` |
| 主题 token | `src/motui/kernel/theme.py`；`Theme.flat()` |
| 行/表面组合 | `src/motui/kernel/cell.py`；`Line.merge_span`、`overlay()` helper |
| 容器命中 | `widgets/layout.py`、`decor.py`、`scroll.py` 的 `child_at` |
| 绘制生命周期 | `widgets/canvas.py`、`pixel_canvas.py` |
| 场景快照 | `tests/golden/semantic/*.txt`、`tools/semantic.py` |
| 历史决策 | `docs/adr/`（001–026）、`docs/CONTRACT.md` |
| 迁移表 | `docs/MIGRATION.md` |

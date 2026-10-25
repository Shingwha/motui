# W1 交接 · 内核拆分（机械迁移，行为零变化）

> 分支 `2.0/w1-kernel`；起点 `33c82be`（W0b 合并后）。前置：`handoff/W0a-values.md`、`W0b-harness.md`。
> 结论：T1–T6 全部完成；**1019 passed**；57 golden 逐字节不变；render-hash 不变；`core/` 消失；kernel 无 I/O。

## A. 交付面与门禁

### 文件迁移（实际）
- `core/{ansi,screen,decoder,clipboard}.py` → `terminal/{ansi,screen,decoder,clipboard}.py`
- `core/sources.py` → `terminal/keys.py`；`core/console.py` → `terminal/win32.py`；`core/painter.py` → `terminal/paint.py`
- 新 `terminal/capability.py`（`terminal_size` / `detect_color_mode` / `auto_theme`）、`terminal/render.py`（`styled_line`）
- `core/frame.py` → `kernel/frame.py` + 新 `kernel/overlay.py`；`Rect` 用 `kernel.geom.Rect`；`core/chrome.py` 的 `Separator` 并入 `kernel/frame.py`
- `core/viewport.py` + `core/scroll.py` → `kernel/layout.py`（W0 `Constraints/ScrollAxis/Scroll` 保留）
- `core/block.py` → `kernel/document.py`（`Block` → `Section`，字段仍 `id/component/pin`）
- `core/{selection,events,keymap,hit,style,glyphs,theme,text,lines}.py` → `kernel/{selection,events,keymap,hit,style,glyphs,theme,text,cell}.py`
- `core/widget.py` → `widgets/base.py`；`core/cursor.py` → `widgets/cursor.py`；`core/mark.py` → `widgets/mark.py`；`Text` → `widgets/text.py`
- `core/__init__.py` 与整个 `src/motui/core/` 删除；`tests/core/` 按模块拆到 `tests/{kernel,terminal,widgets}/`（`test_viewport→test_layout`，新增 `tests/terminal/test_capability.py`）

### 公开面
- `kernel.__all__` 恰 62 名：`Axis Border Cell Chrome Color ColorMode ColorPalette Component Constraints DEFAULT_EDITOR_KEYMAP DEFAULT_INPUT_KEYMAP DEFAULT_THEME Document EDITOR_SUBMIT_KEYMAP ELLIPSIS Event EventSource EveryHandle FG_CODES FocusEvent Frame GLYPHS Glyphs Hit KeyEvent Keymap Line MouseEvent NONE Overlay Pane PasteEvent Pos RESET Rect ResizeEvent RowRange ScreenLayout Scroll ScrollAxis Section Segment Selection Separator Size Split Style Styles Surface Theme Viewport WrapMode action_at cut_line ellipsize_tail extract highlight sgr_prefix slice_line visible_width wrap_line wrap_text`
- `terminal.__all__` 恰 13 名：`Clipboard HeadlessScreen KeyDecoder MemoryClipboard Painter RawTerminalKeys Screen ScreenClipboard TerminalScreen auto_theme detect_color_mode styled_line terminal_size`；不导出 `ansi`/字节函数。
- root `motui.__all__` 仍是原 41 名（只换来源：`Text/Widget` 从 widgets，其余 kernel/terminal/app/testing）。
- `Screen` ABC 成员：抽象 `width height live size encoding enter leave write flush refresh_size close`；具体默认 `copy_to_clipboard(text)->False`；`color_mode` 为类注解（两实现实例属性）。库内无 `isinstance(..., Screen)`。

### 门禁实测（2026-10-25，本 worktree）
- `pytest -q -p no:cacheprovider`：**1019 passed**（1017 旧 + api facade +1、capability +1、Text/Widget 矩阵）。
- `tools/golden.py --check`：`57 topics match`；`tools/framebench.py`：`render-hash a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`。
- `python -m motui < /dev/null` exit 0 / 70 行；`--pages` exit 0 / 4059 行。
- `grep -rnE "from .*core|import motui\.core" src/motui tests tools` 为空（exit 1）；`src/motui/core/` 不存在。
- `import motui` 后 `'motui.core' not in sys.modules`；`ruff check .` All checks passed；`pyright` 0 errors；`lint-imports` 4 kept / 0 broken。
- `tools/api.py --check`：`179 names match`（旧 189 → core 消失、terminal 加入）。公开面计数：**root 41 / kernel 62 / terminal 13**，root 与 kernel 超验收目标（30/40），W5 收敛。
- `tools/growth.py --quick`：pytest pass、golden pass、OK。

## B. 偏差、取舍与下一波

1. **Painter 在 terminal**（工单 D1 覆盖源 spec 的 `kernel/paint.py`）：kernel 不构造 terminal 字节。
2. **`styled_line(line, mode="truecolor")`** 是唯一 SGR/OSC8 路径；模块级 `@lru_cache(4096)` 以 `(line, mode)` 为键（Line 不可变、可哈希）。kernel `Line` 删除 `styled`/`_styled`；`Line.styled()` 的 1.x 调用点全部迁移。
3. **`Screen` ABC** 不 runtime-check；`copy_to_clipboard` 本波带 `False` 默认，W4 移入 Clipboard 能力时删除。
4. **Rect kw_only 未放宽**：AST codemod 把全仓 100 处位置调用改为关键字（脚本已删除）；`tests/kernel/test_geom.py` 保留一处 `Rect(0,0,1,1)` 断言 TypeError。`Split/Pane/Frame` 全用 `geom.Rect`。
5. **Section 只改名**：`Section(id, component, pin=...)`；变量名 `block`、`block_id`、`BlockRule/_BlockScan` 未动。`Document.add/get/remove` 返回 `Section`。
6. **`Theme.auto(env)` 现在要求显式 env**；`terminal.capability.auto_theme(env=None)` 才读 `os.environ`。`detect_color_mode`/`terminal_size` 只在 terminal。
7. **临时归属**：`EveryHandle/RowRange` 暂留 `kernel/hit.py`（W4）；`ScrollState/Scrollable` 在 `kernel/layout.py`（W4）；`cursor.py`/`mark.py` 独立在 widgets（W3 并入 `base.py`）。
8. **overlay 机制拆分**：`LAYERS/Overlay/apply_overlays` 在 `kernel/overlay.py`；`Frame.apply_overlays` 退化为委托，签名与行为不变（`with_pane_rows` 返回注解改为 `ScreenLayout | None`，真实语义如此）。
9. **静态 ratchet**：pyright `basic` + `strict=["kernel/geom.py","testing","tools/api.py","tools/growth.py"]`；ruff 移除 `src/motui/core`、新增 `tests/terminal` 到 exclude，并对 8 个迁移文件/5 个迁移测试加显式 per-file-ignores（E501/RUF009/RUF005/B008/B017/B023/B905/E402/F841/RUF015/RUF059）；import-linter 新增 widgets/terminal 两条契约，kernel 的 forbidden 去掉 core、加 testing。
10. **pinned 文件**：`tools/golden.py` 仅 docstring 的模块路径更新；`tools/framebench.py` 仅 1 行 import；`tests/golden/**` 零改动；demo 仅 import 行。
11. **W0b 事实复核**：baseline 1017/57/hash 全部复现；旧 api 快照 189 名因 core facade 消失而重录为 179（预期）。
12. **W2 要迁移的 `render(width)` 清单（grep 38 处）**：
    - `widgets/`: action.py:160,277,391；base.py:63；choice.py:631；collapsible.py:233；combobox.py:306；decor.py:135,256；dialog.py:425；diff.py:582；form.py:254；indicators.py:109,385,481；layout.py:95,210,273,364；list.py:511；markdown/component.py:821；navlist.py:304；rows.py:122,178,243；scroll.py:332；strip.py:213；table.py:733,808；text.py:141；textfield.py:510；tree.py:411
    - `app/`: command_palette.py:108,270；`kernel/`: document.py:48,346；`demo/`: shell.py:80、stage.py:94
13. **未决**：`ScrollAxis` 的 sticky previous-extent（W2.6）；`Line.clip` 仍是整数硬裁（W2.5）；`kernel/__init__` 与 root 名单需 W5 收敛；`ScrollState` 与 `Scroll` 双轨并存到 W2.6。

## C. 位置与 commit

- `terminal/screen.py:39` Screen、`:121` TerminalScreen、`:266` HeadlessScreen；`terminal/render.py:55` styled_line；`terminal/paint.py:66` Painter；`terminal/capability.py` 三探针。
- `kernel/cell.py:103` Cell、`:127` Segment、`:201` Line、`:626` Surface；`kernel/document.py:272` Section、`:447` Document；`kernel/layout.py:49/69/165/496/735` Constraints/ScrollAxis/ScreenLayout/Viewport/ScrollState；`kernel/frame.py:107/252/309/1010/1621` Chrome/Split/Pane/Frame/Separator；`kernel/overlay.py:38/60`。
- `widgets/text.py:19` Text；`widgets/base.py:25` Widget；`pyproject.toml:66` ruff、`:95` pyright、`:112` import-linter；`tools/api.py:40` FACES。
- commit：
  - `f974861` terminal: move the I/O modules into a terminal package
  - `63e2f47` terminal: add the Screen ABC and the SGR renderer
  - `4042e01` kernel: move the pure values into the kernel
  - `1af902e` kernel: rewrite the tree onto kernel, terminal and widgets imports
  - `5eb78e0` kernel: publish and pin the kernel and terminal facades
  - `3ef7155` test: move the tests onto the new layers and tighten the static gates
  - 本文件（最后一个 commit）

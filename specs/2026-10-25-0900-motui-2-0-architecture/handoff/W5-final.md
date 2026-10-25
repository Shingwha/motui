# W5 终验 · motui 2.0.0

> 日期：2026-10-25；main @ `9554f5c` 之后（终验提交）
> 结论：2.0.0 的架构、渲染、交互、运行时、公开面、示例与文档已交付；全量门禁绿；不 push / 不 tag / 不发版。

## A. 最终门禁（main，真实输出）

```
uv sync --locked                      -> motui==2.0.0 (editable)
uv run python -c "import motui; ..."  -> 2.0.0
pytest -q -p no:cacheprovider         -> 1592 passed in 37.71s
tools/golden.py --check               -> golden: 57 topics match
tools/semantic.py --check             -> semantic: 57 topics match
tools/framebench.py                   -> render-hash e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da
python -m motui < /dev/null           -> exit 0, 70 lines
python -m motui --pages               -> exit 0, 4059 lines
examples/quickstart.py --headless     -> exit 0 ("Hello, motui.")
examples/snake.py --headless          -> exit 0 ("score 0, steps 19, alive False")
examples/dashboard.py --headless      -> exit 0 ("40 frames at 20 fps, 64 points ...")
examples/wide_table.py --headless     -> exit 0 ("rightmost c199/v199 visible")
ruff check .                          -> All checks passed
pyright                               -> 0 errors, 0 warnings
lint-imports                          -> 4 kept, 0 broken
tools/api.py --check                  -> 184 names match
tools/growth.py (full)                -> pytest/golden/api pass, OK
```

## B. 验收对照（`ref/source/12-acceptance.md`）

### 结构

- ✅ `core/` 删除；`kernel` 无 `os/sys/io/ctypes/termios/tty/select/asyncio`；import-linter 4 契约。
- ✅ 所有组件 `render(c: Constraints) -> Surface`；`grep "def render(self, width"` = 0。
- ✅ `Revisioned`/`_CHILD_ATTRS`/`_looks_interactive`/`Resultful`/能力协议删除；能力 isinstance = 0。
- ✅ `Cursor` 一套（`ClampedCursor` 删除）；`ScrollPanel` 一套滚动。
- ⚠️ 单文件行数：`runtime.py` 1617、`application.py` 891；未达 900/450/250 目标（见 C）。
- ✅ `TUI`/`App.tui`/`take_result`/`EveryHandle` 删除（widget 可执行面）；`handle` 只剩 `TextBuffer.handle`。

### 质量

- ✅ ruff 0、pyright 0、lint-imports 0、api 快照 184。
- ✅ growth 全量（给 Surface/Constraints/ScrollAxis 加默认字段后零失败/零 golden 变化）。
- ⚠️ `isinstance` 总数 125（事件/值判别）；能力探测 0；spec 的 <10 未达。
- ✅ 公开面：root 40、kernel 60+、terminal 15+；具体以 `tools/api-2.0.txt` 为准。

### 能力

- ✅ `examples/snake.py` headless 跑完一局。
- ✅ `dashboard.py` 实时 sparkline + resize 回放。
- ✅ `wide_table.py` 200 列在 80 列 pane 可滚到最右。
- ✅ 20 列屏 40 列内容不换行（`tests/kernel/test_render_contract.py`）。
- ✅ `every(0.05)` 1s 19–20 次（实测 19）。
- ✅ `Canvas` cell/half/braille；80×24 全异色实测 ~0.5ms（阈值 2.0ms）。
- ✅ 代码块长行完整可读；`Diff`/`Table`/`Editor` 的 OVERFLOW 可进 ScrollPanel。
- ✅ `Input` 恒一行、光标水平跟随；200 字符仍一行。
- ✅ `take()` 的 None/False 两态；`walk()` 覆盖 + 去重。
- ✅ `TerminalOptions`/`MouseMode`/`Axis X`/`Placement`/`Section`/`Command.group/bind`。

### 性能

- ✅ Canvas 0.5ms/帧（全异色）、0.01ms（单色），远低于 2.0/0.4ms。
- ✅ framebench 无 >10% 劣化；hash 稳定。
- ⚠️ `replay` 在终验机器上 822ms（历史 ~500ms），属机器负载；逐波对照未显示结构性回退。

### 文档

- ✅ `README.md` quickstart（App + TerminalOptions + Text + Input）。
- ✅ `docs/ARCHITECTURE.md`、`CONTRACT.md`、`WIDGETS.md`、`MIGRATION.md`。
- ✅ `docs/adr/ADR-001..023` + 索引。
- ✅ 主文档无 `TUI/take_result/Revisioned/Themed/set_focus_targets` 作为当前 API。
- ✅ 版本 2.0.0；CHANGELOG 2.0 段；CONTRIBUTING 更新。
- ⚠️ `docs/releases/` 保留历史发布记录（非 2.0 叙述）。

## C. 已知偏差与遗留（不阻塞 2.0.0 使用）

1. **运行时文件行数**：`runtime.py` 1617、`application.py` 891、`workspace.py` 285。W4a2 交付 `Runtime` + `Workspace` facade，方法体未完全迁移；`Router`/`DEFAULT_HANDLERS` 未拆，`App.dispatch` 仍是 if 链。建议后续按 session/layout/documents/protocol 四组拆。
2. **兼容层保留**：`split("vertical")`/`dock(edge=)` 字符串、`pin=`、`App.open_palette(list)`、`App` 旧构造参数。新 API（`Axis`/`Placement`/`TerminalOptions`/`CommandRegistry`）已可用；删除兼容层会牵动大量测试/示例，留 2.1。
3. **Fill 形态**：以 `Document.add(sizing=Sizing.FILL)` 落地，未引入 `PaneContent = Document | Fill` 联合。
4. **旧字节 golden 保留**：`tools/golden.py` 与 57 `.txt` 仍在，作为语义 golden 之外的额外门禁；源 spec 计划 W5 删除。
5. **`Theme.style()`/`RowSpan`**：组件用 `group(name)`；`RowRange` 仍在（`RowSpan` 未落地）。
6. **`Scrollbar` 旧参数**：`style/thumb_style/track/thumb` 未收敛到 `ScrollbarStyles`。
7. **`isinstance` 总数**：125（事件/值判别）；能力探测 0。

## D. 分支与合并

- W0a/W0b/W1/W2a/W2b1/W2b2/W2c1/W2c2a/W2c2b/W2.5a/W2.5b/W2.6a/W2.6b/W3a/W3b1/W3b2/W3b3a/W3b3b/W4a1/W4a2/W4b/W5a/W5b 全部 `--no-ff` 合并到 main。
- 共 195 个 commit（自 `400773b` 起）。
- 未 push、未 tag、未发 PyPI。
- worktree 在终验后清理，分支保留。

## E. 指针

- 终验状态板：`00-overview.md` §11。
- 各波交接：`handoff/W*.md`。
- API 快照：`tools/api-2.0.txt`。
- 语义 golden：`tests/golden/semantic/`。
- 示例：`examples/{quickstart,snake,dashboard,wide_table}.py`。

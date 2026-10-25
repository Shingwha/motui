# W5b 交接 · 示例、CI、demo 文案与 2.0 终验

> 分支 `2.0/w5b-release`；起点 `a5aa8bc`（W4b 合并后）。T1–T5 完成：**1592 passed**；57 byte / 57 semantic；demo 70 / 4059；四示例 exit 0；`render-hash` 仍 `e7ca544b…`（理由见 B3）。

## A. 交付面与门禁

### 示例与 CI

- 新增 `examples/quickstart.py`：**30 行**，`App` + `TerminalOptions(screen=HeadlessScreen(60, 6))` + `Text` + `Input`；`app.add` 两次、`app.paint_now()`、打印 `runtime.rows` 前三行。
- `--headless` 与不带旗标（无 TTY）都 exit 0；输出固定两行文本 + 一空行。
- `tests/test_examples.py` 新增 `test_the_quickstart_paints_headless_with_or_without_the_flag`，两种调用都跑；既有 snake/wide_table/dashboard 用例不动。
- `.github/workflows/ci.yml` 在 `demo -- every page dumped` 后加四步：quickstart / snake / dashboard / wide_table 的 `uv run python examples/<name>.py --headless`。
- 四示例本机真实输出：quickstart `Hello, motui.`；snake `score 0, steps 19, alive False`；dashboard `40 frames at 20 fps, 64 points, last=0.668, painted_rows=20`；wide_table `200 columns, x_offset=1321, rightmost c199/v199 visible`。

### demo 文案（展示串，非行为）

- `TUI(...)`/`TUI().run()`/“TUI toolkit” → `App(...)`/`App().run()`/“terminal toolkit”（overview 的 intro 代码块、layer 表、api_line；markdown 的代码块）。
- `take_result()` → `take()`；`activate()` / `activate/take_result` → `on_action("activate")` / `take()`；`tui` 形参名 → `runtime`/`app`。
- `Clickable · Activable · Controller · Resultful · Container · Revisioned` → `focusable · clickable · hoverable · activatable · HasResult · Container`；component-matrix 列头 `activate` → `action`（避免 9 列头在表内折行）。
- 自然英语动词“activate”改成“press/run/confirm”（button/toasts/focus/keymap 等展示串）；`motui 1.2` → `motui 2.0`。
- demo 专用 `ScrollView(ScrollPanel)` 子类在 layout/interactions 两处退役，直接用 `ScrollPanel`；footer 的 focus 标签 `scrollview` → `scrollpanel`。
- `_stage_ids` 改存 `DocumentSection`，`_clear_stage` 传 Section；catalog 用 `Session.catalog_section` 记账，`mount_shell` 按 Section 移除/重挂。

### shim 删除

- `src/motui/app/commands.py`：删除 `_LegacyCommandMeta` 与 `__signature__`；`Command` 只剩 `@dataclass(..., kw_only=True)`。demo 改全关键字构造，`description=topic.group` 保持 palette 字节不变，新增 `group=topic.group` 字段。
- `src/motui/app/application.py`：`App.remove(section: Section)` 只收 Section；非 Section 抛 `TypeError`。`tests/app/test_app.py` 两处迁到 Section，新增反向断言；`test_commands.py` 删除位置参数兼容用例并扩成两个 TypeError。
- **保留**：`split("vertical")` / `dock(edge=)` / `undock("top")` 字符串入口（工单明确本轮保留；测试与示例仍大量使用）。`tests/app/test_app.py` 的注释从“W5 删除”改为“kept through 2.0”。

### golden 重录与分类

- `golden.py --update` + `semantic.py --update`：**31/57 byte、同样 31/57 semantic 变化**；其余 26 组未动（`git show HEAD:file` 逐字节比对确认，工作区 LF/CRLF 噪声已通过 `git add` 清掉）。
- 分类**只有 showcase-text**：所有变化是字形移动及其后的 SGR run 偏移；逐文件核对无 `:L` link 变化、无仅 cursor 移动。**没有 command-group**（palette 的 description 未变）。
- 变更 topic：autocomplete、button、checkbox、collapsible、dialog、link、list、markdown、menu-bar、modal、palette、radio-group、scroll-view、slider、toasts、tooltip；interactions 的 find/focus/modal-stack/pointer/scrollbar/selection；patterns 的 command-palette/form-validation/own-shell/streaming-markdown；reference 的 api-layers/component-matrix/keymap/non-goals；overview/welcome。
- `tests/golden/README.md` 增加“2.0 showcase text”节，并改掉“byte golden W5 删除”的旧句（本波保留它作额外门禁）。
- `tools/api-2.0.txt` 未改：`api --check` 仍是 **184 names**（shim 删除不改公开名）。

### 终验（本 worktree，Python 3.12.14 / uv 0.12.21）

- `pytest -q -p no:cacheprovider`：**1592 passed**（37.53s）。
- `golden --check`：**57 topics match**；`semantic --check`：**57 topics match**。
- `framebench`：9 行全出；`render-hash = e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da`（未变）；耗时与 W4b 同量级（stream-split 13.3–14.4 ms，replay 501–609 ms），无 >10% 劣化。
- `python -m motui < /dev/null`：exit 0，**70** 行；`--pages`：exit 0，**4059** 行。
- `ruff` All checks passed；`pyright` 0 errors；`lint-imports` 4 kept / 0 broken；`growth.py` full：pytest/golden/api 全 pass，`OK (full probe)`。
- `motui.__version__` 仍 **1.2.3**（pyproject 未动，W5a 负责 2.0.0；本分支的版本终检由 lead 在 W5a 合并后复核）。
- 行数：`runtime.py` **1617**、`workspace.py` **285**、`application.py` **891**、`commands.py` **171**。Runtime 仍超 450 目标，拆分留待后续。

## B. 兼容层、偏差与坑

1. **保留的字符串入口**：`split(axis: Axis | str)` 的 `"vertical"/"horizontal"` 与 `dock/undock` 的 `edge=` 字符串是已知兼容层；W5 之后可删，本轮不动 100+ 测试。另有 `pin=` / `Document.add(pin=)` 与 `App.open_palette(list)` 入口仍在：本工单未点名，且 `pin` 位于 `kernel/**` 禁触区，留给后续波次/lead 决策。
2. **字节 golden 保留偏差**：源 spec §3.6 计划 W5 删除 `.txt`；本波按工单保留 `tools/golden.py` 与 57 字节文件作为额外门禁，CI 两套都跑。
3. **render-hash 未变**：`framebench.hash_workload` 是合成会话（Scrollbar + 两个 Markdown + split + 固定滚动脚本），不挂任何 demo topic；展示文案到不了该路径。“新 baseline”记录为同值 `e7ca544b…`，不是漏更新。
4. **Command group 可见性**：`group=` 已进 Command，但 `CommandRegistry.options()` 仍用 `description`；把 group 放到 palette 展示会改 palette golden（W6+），本轮刻意不做。
5. **`TUI` 残留**：`grep -rn "TUI" src/motui --include=*.py` 12 处，全是 docstring/注释里的历史名或“TUI toolkit”措辞：`__init__.py`、`kernel/frame.py`（4）、`terminal/terminal.py`、`widgets/{choice,list,table,textfield}.py`。均在禁触区，留给 W5a/docs 或后续清理。
6. **`take_result` 可执行 0**：`src/` 内 grep 为 0。`activate(` 只剩 `FocusManager._activate`（2.0 内部实现）和 `widgets/list.py` 一条 docstring；对外调用一律 `on_action("activate")`。
7. **测试净增 0**：T1 +1（quickstart），T3 删 1（位置参数 Command 兼容用例），总数仍 1592。
8. **semantic 重录噪声**：`--update` 会重写全部 57 文件；用 `git show HEAD:<path>` 归一化 CRLF 后确认只有 31 个真实变化，其余 26 个 `git add` 后无内容 diff。

## C. 位置与 commit

- 示例/CI：`examples/quickstart.py`、`tests/test_examples.py`、`.github/workflows/ci.yml`
- demo：`src/motui/demo/{model,session,shell,stage}.py`、`src/motui/demo/topics/{overview,components_text,components_actions,components_data,components_forms,components_layout,components_overlays,interactions,patterns,reference}.py`
- shim：`src/motui/app/{commands,application}.py`；测试 `tests/app/{test_app,test_commands}.py`
- golden：`tests/golden/{topics,semantic}` 各 31 个文件、`tests/golden/README.md`
- commit：
  - `d04bf58` examples: a thirty-line quickstart paints a text row and an input headless（T1）
  - `9f08627` ci: every shipped example runs headless on both platforms（T2）
  - `4e39f9b` demo: the showcase speaks App, take and on_action（T3，含 matrix 列头修正）
  - `573f2eb` golden: the showcase text is 2.0 and both sets are re-recorded（T4）
  - 本文件（T5 收口）

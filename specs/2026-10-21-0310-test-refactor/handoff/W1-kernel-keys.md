# W1 · kernel + keys handoff

> 分支 `tests-w1-kernel-keys`；写范围 `tests/kernel/**`、`tests/keys/**` 与工单点名的旧文件删除。
> 基线：`00b7515`（W0 共享层）；本分支 HEAD 见最后一节。

## A 自动事实

### diff stat（`git diff --stat main...HEAD`，handoff 提交前）

```
37 files changed, 3463 insertions(+), 5785 deletions(-)
```

新增/重写：

```
tests/kernel/{__init__,test_text,test_lines,test_style,test_theme,test_block,
  test_viewport,test_frame,test_painter,test_screen,test_selection,test_ansi,
  test_cursor,test_glyphs,test_mark,test_clipboard,test_events}.py
tests/keys/{__init__,test_decoder,test_keymap,test_sources}.py
```

删除（`git rm`，旧用例已迁移/重写，不是直接丢弃）：

```
tests/test_core_text.py                 tests/test_style.py
tests/test_theme.py                     tests/test_default_theme_paints_structure.py
tests/test_block.py                     tests/test_viewport.py
tests/test_frame.py                     tests/test_painter.py
tests/test_screen.py                    tests/test_selection.py
tests/test_ansi.py                      tests/test_cursor.py
tests/test_glyphs.py                    tests/test_mark.py
tests/test_clipboard.py                 tests/test_events.py
tests/test_keys.py                      tests/test_keys_sources.py
tests/test_decoder_fuzz.py
```

范围核对：`git diff --name-status main...HEAD` 只含上述 `tests/kernel/**`、`tests/keys/**`
与删除项；`src/**`、`tools/**`、`tests/testing/**`、`tests/__init__.py`、
`tests/conftest.py`、`tests/widgets/**`、`tests/app/**`、`tests/interaction/**`
零改动。

### 用例数（pytest 收集数）

| 目录 | 收集数 | 工单区间 |
|---|---|---|
| `tests/kernel` | **219** | 150–220 |
| `tests/keys` | **55** | 45–70 |
| 合计 | **274** | 195–290 |

### 门禁输出（本 worktree，Python 3.13.16，`PYTHONPATH=$PWD/src`）

```
$ pytest -q -p no:cacheprovider tests/kernel tests/keys
274 passed in 0.83s

$ pytest -q -p no:cacheprovider            # 全量，W2/W3 旧文件仍在
2019 passed in 11.97s

$ grep -RIn "\._[a-z]" tests/kernel tests/keys
0 matches

$ grep -RIn "sleep(" tests/kernel tests/keys
0 matches
```

开工基线（同一 worktree、同一解释器）：`2190 passed, 2 skipped in 17.68s`。
两个 skip 是旧 `tests/test_keys_sources.py` 的 POSIX-only 用例
（`select()` 在 Windows 只能探测 socket），随旧文件删除；新目录因此 0 skip。
全量 `0 failed`。

### 提交

```
b5c4249 tests: open the kernel and keys test directories -- empty contract files
dea67ae tests: rewrite text and line primitives -- measure, wrap, fit, cut, style -- replace test_core_text
e194a9b tests: rewrite style, theme, glyph, event and document tests -- values and contracts, not constants
80eb6ce tests: rewrite layout, render and byte-contract tests -- viewport, frame, painter, screen, selection, ansi, cursor, mark, clipboard
362ded7 tests: rewrite decoder, keymap and source tests -- decode matrix, derivation chain, console replay and pipe lifecycle
```

## B 取舍

### 删掉的东西与原因

1. **私有实现镜像**
   - `Segment._width` / `Style._prefix` 的 hidden-cache 断言；
   - `_MARK_RANGES`、`_cell_spans`、`_is_mark`、`_VARIATION*` 的私有表/扫描器断言；
   - `Text` 的 block 行缓存计数、`Text.revision()` 快照、viewport 的 sealed-cache 失效、
     frame 的 per-row memo 对象同一性、painter 的 `frames` 计数、selection 的 row-cache
     同一性；
   - `test_keys_sources` 里通过 `source._thread` 做 teardown 的写法。
   这些断言会在改缓存/字段名时无故变红，且不是宿主可观察行为。行缓存/字节基线由
   `tools/golden.py` 与真实渲染 smoke 兜底。

2. **文档镜像与迁移考古**：删除 “red before the fix”、“old pad_to”、“textual/W7 bug”、
   D1/D2/D4/D5 编号叙事、“常量表逐字段相等”等断言；测试名只描述行为。

3. **常量清单**：glyph 的 15 常量逐字节表缩为 4 个代表性字形 + seat 规则；
   theme 不再与旧模块常量逐字段相等（只保留 `Theme()` 默认值、band 默认和派生表）；
   `FG_CODES` 只读 pin 删除（命名色码由 prefix 行为覆盖）。

4. **重复路径**：
   - 43 个 keymap 派生断言/逐按钮 console 映射收敛为表驱动；
   - style 的 13 个 env matrix case 收进一个循环（仍覆盖全部组合）；
   - `ScriptedEvents` 回放自测从 kernel 删除（测试 helper 自身行为；W3 的真实
     driver 测试会使用它）；
   - 逐组件 theme 测试只保留 `Divider`（显式优先）、`Markdown`（组件取 theme）和一个
     默认主题不变量；组件内部样式由 W2 的组件测试负责。

5. **environment-specific**：`terminal_size()` 的正数断言删除（它测的是运行机器的
   终端，不是产品契约）；`enable_vt()` 的真实 Windows console 行为不单测，screen
   测试通过 monkeypatch 固定 liveness。

### 有意不再覆盖的行为

- **POSIX-only 的 settle-after-silence 与 self-pipe 唤醒**：基线在 Windows 上本来就
  skip，且需要真实 50 ms 等待；新 `test_sources.py` 保留 pipe/cooked/EOF/close/
  double-start 生命周期，但不覆盖真实 select deadline 分支。建议 lead 在 POSIX CI 上
  补 1 个 smoke（当前工具链无 POSIX CI 则接受缺口）。
- **`Text` 的行缓存 / revision 机制**：按 T4/删除判据属实现镜像；`Text` 的
  render/streaming/width 边界、click/take_result、hover 合并仍有测试。
- **`descend()` 容器坐标下降**：属 W2/W3 的容器路由范围（`child_at` 由 W2 测）；
  W1 不重复。
- **逐字节全帧布局**：kernel 的 ansi/screen/painter/keys.decoder 仍锁精确字节
  （字节即产品）；frame/selection/theme 只断言语义（行文本、列区间、样式字段），
  完整视觉字节交给 `tools/golden.py`（58 topics）。

### 保留/迁移的核心行为

- 文本测量四类簇（combining / VS16 / ZWJ / regional indicator）、tab=1 列、控制符 0 列；
  `wrap_text` 空格/硬断/CJK/width 0/1；`fit_text`/`ellipsize_tail` 的预算后置条件。
- `Line`/`Segment` 的 fit/fill/filled/add/merge_span/styled/styled_with、
  `slice_line`/`cut_line`/`wrap_line`、OSC 8 link、payload 随 cut/fit/fuse 存活、
  `action_at` 左闭右开。
- SGR 顺序、命名色/truecolor、merge、quantize 16/256、downgrade、
  `detect_color_mode` 全 env 组合。
- Block/Document：转发、seal 一次性、auto id 跳过显式 id、重复 id、get/remove、
  blocks 快照、pin 校验。
- Viewport：固定区、窗口切片、offset clamp、stick bottom、scroll_to、row_blocks/
  block_order、窗口与全量物化等价、流式内容重新计数。
- Frame：Rect、Split 比例/裁剪、Pane split/close（折叠、重分、id 规则、focus 回退、
  divider 按 name 剥离）、chrome 预算/裁剪/堆叠、splice_row 网格与三切 oracle、
  compose pass-through、ownership、dock、overlay 层序、with_pane_rows。
- Painter：首帧/零字节/单行 diff/清空行/尺寸变化全刷/非 live/光标 anchor/
  color mode downgrade。
- Screen：headless 记录、enter/leave bracket、mouse/paste/focus 开关、liveness 一次
  决策、OSC 52 转发与拒绝、color mode。
- Selection：方向归一、边界裁剪、宽字符不劈、跨 block、removed endpoint、extract。
- ANSI：光标/清屏/鼠标/同步/粘贴/OSC 52/标题/hyperlink/光标形状（字节契约）。
- CursorWindow：两种窗口策略、clamp、move、cursor-on-screen 不变量。
- MarkSet / mark_prefix；Clipboard 两后端。
- Decoder：可打印/控制键、CSI/SS3/tilde/kitty/modifyOtherKeys、SGR/X10/urxvt、
  paste 跨 feed、escape 降级、UTF-8 增量、非 bytes TypeError、2 个 fuzz 不变量。
- Keymap：三张默认表的派生链与关键绑定。
- Sources：Windows console record→event（含 press/drag/release、hover 开关、重复计数、
  focus/resize、与 VT 路径 parity）、cooked pipe、EOF sticky、finish flush、close 幂等、
  double start 单 reader。

## C 指针

- 共享 helper：只用 `tests.testing` 的 `Rows/many/texts/RecordingScreen/...`；
  本波未请求新 helper，未改 `tests/testing/**`。
- 新文件与契约：
  - `tests/kernel/test_text.py` — 宽度真值与 wrap/fit/ellipsize + `Text` 组件；
  - `tests/kernel/test_lines.py` — Segment/Line 全部公开操作与两种 offset 空间；
  - `tests/kernel/test_style.py` / `test_theme.py` — SGR 与主题解析；
  - `tests/kernel/test_glyphs.py` / `test_mark.py` / `test_cursor.py` — 行视图原语；
  - `tests/kernel/test_block.py` / `test_viewport.py` — 文档与窗口；
  - `tests/kernel/test_frame.py` — 分屏/合成/ownership/overlay；
  - `tests/kernel/test_painter.py` / `test_screen.py` / `test_ansi.py` — 字节层；
  - `tests/kernel/test_selection.py` — overlay 与 extract；
  - `tests/kernel/test_events.py` / `test_clipboard.py` — 值类型与能力协议；
  - `tests/keys/test_decoder.py` — 解码矩阵 + fuzz 不变量；
  - `tests/keys/test_keymap.py` — 三张默认表（W2 不应重复测）；
  - `tests/keys/test_sources.py` — console replay + pipe 生命周期。
- 给 lead/W2/W3 的提醒：
  - `tests/_doubles.py` 在本分支仍被旧 W2/W3 文件使用（W0 未删）；W1 目录不引用它。
  - `Text` 的 inline span click/hover 已在 `test_text.py` 覆盖，W2 无需重复。
  - `MarkSet`/`CursorWindow`/`mark_prefix` 已由 W1 覆盖，W2 只测组件如何消费它们。
  - keymap 三表已由 W1 覆盖，W2 的 editing 测试只测路由行为，不再 pin 表内容。
  - POSIX-only source 分支是本波唯一有意留下的平台缺口。

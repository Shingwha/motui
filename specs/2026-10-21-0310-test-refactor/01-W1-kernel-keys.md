# W1 · kernel + keys 测试重写

> 分支 `tests-w1-kernel-keys`；前置 W0（共享 testing 层已在 main）；写入范围 `tests/kernel/**`、`tests/keys/**`。

## 目标

把 kernel 与 keys 的测试重写成**行为契约**：只测公开 API 的输入/输出、编码字节、布局数学与错误路径。
最高约束：**不读私有属性、不测缓存/revision 机制、不逐字节锁组件布局**；`src/**` 零改动。

## 前置上下文

- 必读顺序：`specs/2026-10-21-0310-test-refactor/00-overview.md` → `ref/repo-map.md` → `ref/interfaces.md` §1–§4。
- 基线命令（开工先跑，贴真实输出）：

```bash
cd C:/Users/shifu/.worktrees/motui/tests-w1-kernel-keys
PYTHONPATH=$PWD/src C:/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python.exe \
  -m pytest -q -p no:cacheprovider tests/kernel tests/keys
```

（开工时 `tests/kernel` 还不存在，先跑全量确认 2190 passed / 2 skipped。）
- 稳定区（勿改）：`tests/testing/**`、`tests/__init__.py`、`tests/conftest.py`、`src/**`、`tools/**`。
- 已知约束/坑：见 `repo-map.md` §6；Windows Git Bash；不要 `uv sync`。

## 工单（按序执行，每项一个 commit）

### T1 建目录与骨架

- 新建 `tests/kernel/__init__.py`、`tests/keys/__init__.py`。
- 新建目标文件（可先空壳）：
  `tests/kernel/{test_text,test_lines,test_style,test_theme,test_block,test_viewport,test_frame,test_painter,test_screen,test_selection,test_ansi,test_cursor,test_glyphs,test_mark,test_clipboard,test_events}.py`、
  `tests/keys/{test_decoder,test_keymap,test_sources}.py`。
- 验证：`pytest --collect-only tests/kernel tests/keys` 不报导入错误。

### T2 文本与行原语

- 从 `tests/test_core_text.py` 重写：
  - `test_text.py`：`visible_width`（ASCII/宽字符/组合簇/ZWJ/VS16/控制符/tab）、`wrap_text`（空格/硬断/CJK/width 0/1）、`fit_text`、`ellipsize_tail`、`Text` 的 render/streaming/width 边界。
  - `test_lines.py`：`Line`/`Segment` 的 width/fit/fill/add/merge/styled/wrap/cut/slice/overlay/fuse；宽字符与簇不劈开。
- 删除：`Segment` 隐藏宽度缓存断言、`styled_with` “never caches”、“compact mark table is all Mn”、revision 机制断言。
- 保留：簇边界（combining/VS16/ZWJ/regional indicator）作为行为测试；`Line.fit` 后置条件可保留 1 个参数化。
- 删除旧文件：`tests/test_core_text.py`。
- 验证：`pytest -q tests/kernel/test_text.py tests/kernel/test_lines.py`。

### T3 样式、主题、字形、事件、文档模型

- `test_style.py`：SGR 前缀、命名色/truecolor、属性顺序、merge、quantize 16/256、downgrade、`detect_color_mode`。删 `has slots and writes hidden prefix cache`。
- `test_theme.py`：默认 token 形状、frozen/replace、显式样式优先、组件从 theme 取样式；吸收 `test_default_theme_paints_structure.py` 的**一个**不变量（默认主题不刷背景、不反色）。删旧常量清单、逐组件 theme 测试中与组件行为重复的部分。
- `test_glyphs.py`：seat/pair/宽度 + 3–5 个代表性字形；删 15 个常量的逐字节表。
- `test_events.py`：事件类型关系、frozen/值相等、默认字段、`EventSource` 协议；删 `ScriptedEvents` 自测（只留 1 个 smoke，或直接删）。
- `test_block.py`：`Block.render` 转发、seal、`Document` auto id/重复 id/get/remove/blocks snapshot/pin 校验；删 `rows caches...` 整个用例。
- 删除旧文件：`tests/test_style.py`、`test_theme.py`、`test_default_theme_paints_structure.py`、`test_glyphs.py`、`test_events.py`、`test_block.py`。
- 验证：对应文件全绿。

### T4 布局与渲染核心

- `test_viewport.py`：layout 尺寸/offset clamp/stick bottom/scroll_to/pinned 区域/ownership；删 sealed cache、row_blocks 不可变 tuple 等内部断言。
- `test_frame.py`：`Rect`、`Split` 比例、`Pane.close` 折叠/重分、`Chrome` budget、compose、ownership、overlay 顺序；删“composed row handed back while plan stands”缓存断言。
- `test_painter.py`：首帧/无变化零字节/单行 diff/尺寸变化全刷/非 live/光标；删 `frames` 计数内部断言。
- `test_screen.py`：headless 记录、alt-screen bracket、live/non-live、clipboard、color mode。
- `test_selection.py`：`Selection.between` 归一化、highlight 边界/宽字符、extract 跨 block/越界；删 cache 值不变、读取 row cache 之类断言。
- `test_ansi.py`：光标/清屏/鼠标/同步/粘贴/OSC52/标题/超链接/光标形状；保留字节契约，合并重复的 payload round-trip。
- `test_cursor.py`：窗口策略、clamp、单行窗口；删 `_last_paint` 之类内部。
- `test_mark.py`、`test_clipboard.py`：保留核心，各 4–6 个。
- 删除旧文件：`tests/test_viewport.py`、`test_frame.py`、`test_painter.py`、`test_screen.py`、`test_selection.py`、`test_ansi.py`、`test_cursor.py`、`test_mark.py`、`test_clipboard.py`。
- 验证：对应文件全绿。

### T5 keys

- `test_decoder.py`：可打印/控制键、CSI/SS3、修饰键、SGR/X10/urxvt 鼠标、bracketed paste、跨 feed 组装、非法字节降级；并入 `test_decoder_fuzz.py` 的 2 个不变量（随机字节不抛、逐字节=整块）。
- `test_keymap.py`：`DEFAULT_INPUT_KEYMAP` / `DEFAULT_EDITOR_KEYMAP` / `EDITOR_SUBMIT_KEYMAP` 的派生关系与关键绑定（从 editing 测试移来，W2 不再重复测）。
- `test_sources.py`：Windows console 记录→事件、VT 路径、pipe fallback、start/close/EOF 生命周期；删逐按钮重复的映射，保留 1 个参数化表。
- 删除旧文件：`tests/test_keys.py`、`test_keys_sources.py`、`test_decoder_fuzz.py`。
- 验证：`pytest -q tests/keys`。

### T6 收口

- 全目录跑：`pytest -q -p no:cacheprovider tests/kernel tests/keys`。
- 自查：`grep -R "\._[a-z]" tests/kernel tests/keys`（dunder 除外）应为 0；`grep -R "sleep("` 为 0。
- 统计用例数，确认落在 **195–290**（kernel 150–220 + keys 45–70）。
- 写 `handoff/W1-kernel-keys.md`。

## 验收

1. 上述 pytest 全绿，贴真实数字。
2. 全量 pytest 0 failed（旧 W2/W3 文件仍在，允许通过）。
3. `git diff --stat main...HEAD` 只含 `tests/kernel/**`、`tests/keys/**`、删除的旧文件、handoff。
4. 私有属性 grep 0；sleep grep 0。
5. 每个目标文件有 docstring 并覆盖 `ref/interfaces.md` §4 的清单。

## 禁触清单

`src/**`、`tools/**`、`tests/golden/**`、`tests/testing/**`、`tests/__init__.py`、`tests/conftest.py`、
`tests/widgets/**`、`tests/app/**`、`tests/interaction/**` 以及根级 `tests/test_*.py`（除本工单列出的删除项）。

## 交接包

完成后在分支最后一个 commit 写 `handoff/W1-kernel-keys.md`，按 SKILL 的 Handoff 模板：
A 自动事实（diff stat、新文件/用例数、门禁输出）；B 取舍（删了什么、为什么、哪些行为有意不再覆盖）；
C 指针（关键文件、遗留）。

## 最终报告

工单状态表 / commit 清单（hash + message）/ 自测真实结论 / 偏差与取舍 / 探索审计 / 未决问题。

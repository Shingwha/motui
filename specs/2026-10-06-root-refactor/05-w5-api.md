✅ 2026-10-06 @ rr/w5-api

# Spec root-refactor · API 面定稿 + 文档收口（波次 W5）

> 分支 `rr/w5-api`；前置：W3 与 W4 均已合并。
> 深读：`specs/2026-10-06-root-refactor/00-overview.md`（总纲，必读）+
> `specs/2026-10-06-root-refactor/ref/audit-keys-api.md`（第 3 节 API 盘点）。

## 目标

**公开 API 面按"作为 module 给别人用"的标准重新定稿**：根面收窄到宿主真正需要的名字、
机制名上根（Selection/extract/highlight）、低层构造名下放 facade；三份文档
（README / DESIGN / COMPONENTS）与前四波的全部变更收口对齐，不许文档撒谎。

写入范围（范围外零 diff）：
- 根 `src/mocode_tui/__init__.py`、`core/__init__.py`、`keys/__init__.py`、
  `widgets/__init__.py`、`chat/__init__.py`、`widgets/markdown/__init__.py`
- `core/frame.py`、`core/ansi.py`（**仅** T2b 授权的 split_rect/clear_line 删除段）
- `tests/test_api_root.py`（重写 pin）、`tests/test_readme_examples.py`、
  `tests/test_frame.py`、`tests/test_ansi.py`（**仅** T2b 授权的用例删除/措辞改写）
- `README.md`、`docs/DESIGN.md`、`docs/COMPONENTS.md`
- 若 facade 收窄导致某测试 import 失败：该测试的 import 行同步（报告声明）

禁触：一切非 `__init__.py` 的源文件（若发现前四波遗留的 API 问题，**记录进报告**，不改）、
examples/、tools/、specs/。

## 工单（按序执行，每项一个 commit）

### T1 根面定稿
以当前根 `__init__.py` 为基，应用以下变更（逐条核对前四波后的实际状态）：

**删除**（低层构造/类型别名，宿主不直接用；各自 facade 保留）：
- `TerminalScreen`（core 有）、`RawTerminalKeys`（keys 有）、`Screen`（core 有；协议类型，
  自定义 screen 的宿主从 core 拿）、`KeySource`（core 有）、`Keymap`（keys 有；dict 别名）。
  前四波已删的 `StatusBar`/`StatusSegment` 确认不在。

**新增**（机制名上根，host 不必钻 core）：
- `Selection`、`extract`、`highlight`（自 `mocode_tui.core`——core/__init__ 已导出，根再导出）。

**保持**：`TUI`、`EveryHandle`、`Hit`、`Block`、`Component`、`Pane`、`ScriptedKeys`、
`HeadlessScreen`、`Key`、`Paste`、`MouseEvent`、`Line`、`Segment`、`Style`、`Theme`、
`DEFAULT_THEME`、九色常量（ACCENT/DIM/MUTED/SUCCESS/ERROR/WARNING）、`Text`、`Markdown`、
全部 widgets 组件名、全部 chat 名、`SelectionGesture`、`copy_on_select`、`headless_tui`、
`snapshot`、`DEFAULT_INPUT_KEYMAP`、`DEFAULT_EDITOR_KEYMAP`、`visible_width`、`wrap_text`。

预期根面 ≈ 64 名（删 5 加 3；以逐字清单为准）。模块 docstring 重写：一句话定位 +
分层导览 + "the one import line for a host" 的示例。导入排序遵守 test_api_root 的
常量/类/函数分组规则。

### T2 facade 同步
- `core/__init__.py`：核对与实际 core 内容一致（W1 后 `Text` 从 lines 导出、`Themed`
  不导出（私有基类）、`Clickable` 导出（W3 加的协议，公开扩展点））。
- `keys/__init__.py`：补 `COMPOSER_KEYMAP`（W4 前它是 chat 的——W2 已迁 keys/keymap.py，
  确认 keys facade 导出三表 + KeyDecoder + RawTerminalKeys）。
- `widgets/__init__.py`：删 StatusBar 后核对；docstring 的 "Each component implements the
  frozen protocol" 声明改为准确表述（纯渲染组件遵守 render 协议；交互组件另有
  handle/click 控制器方法——与 audit B §6 的裁决一致）。
- `chat/__init__.py`：核对（W2 的 COMPOSER_KEYMAP 来源行、W3 的清理）。
- `widgets/markdown/__init__.py`：`default_inline_rules` 加入（W3）、注册表 tuple 化后的
  类型注记。
- 全部 facade 的 `__all__` 与 docstring 对齐；模块命名空间的"意外公开"（audit C §3）
  逐个核对：import 了但不在 `__all__` 的名字，要么进 `__all__` 要么改为私有引用。

### T2b W1 阻塞项收口：split_rect 与 clear_line 的删除（lead 授权补充，2026-10-06）

W1 曾因 test_api_root 逐字 pin 无法删除两个符号，本波写入范围恰好覆盖全部牵涉文件，
由你一并完成：

- `core/frame.py`：删 `split_rect` 与随之失去消费者的 `_spans`（先 grep 确认）；
  保留 `Split.rects`（"余数补给最后一个"语义）为其唯一实现。**`Split.rects` 行为不变**——
  删除即消灭"丢弃余数"这条从未被产品消费的平行语义。
- `core/ansi.py`：删 `clear_line()` 函数出口（`CLEAR_LINE` 常量保留）。
- `core/__init__.py`：facade 的 `__all__` 摘除 `split_rect`、`clear_line`。
- `tests/test_frame.py`：删钉住 `split_rect` 语义的用例（`Split.rects` 的用例全部保留）；
  `tests/test_ansi.py`：删 `clear_line` 用例，顺手把"1002 motion reports are new since
  selection W1"的历史措辞改为现在时。
- `docs/DESIGN.md` / `README.md` / `docs/COMPONENTS.md` 中对 `split_rect` 的引用同步清除。

### T3 test_api_root.py 重写
- ROOT_ALL = 新根面逐字清单；LAYER_ALLS = 各 facade 新 `__all__`；
  down-list（在 facade 但不在根）更新；排序断言（常量/类/函数分组）保留；
  TUI all-caps 特判保留；可解析性断言保留；无私有泄漏断言保留。
- 新增断言：`from mocode_tui import Selection, extract, highlight` 可用。

### T4 README 收口
逐段核对与更新（保留现有结构，改事实）：
- **Quickstart**：`Composer(tui, ...)` 构造挂载（不再是 `Composer(...).attach(tui)`）；
  `handle` 契约；`palette.chosen` 用法。片段必须与 test_readme_examples.py 的执行一致。
- **Chrome/panes/overlays** 段：dispatch order 四步不变；`gesture.py` 路径更新
  （`from mocode_tui import SelectionGesture` 不变，无需改）；确认无失效引用。
- **Package layout** 树：`selection.py→gesture.py`、`widgets/chrome.py→widgets/decor.py`、
  Text 在 lines、keys/keymap.py 三表。
- **What lives where** 表：按 T1/T2 定稿重写。
- **Components 表**：删 StatusBar 行；`Select`/`Confirm`/`Tabs`/`Tree`/`Autocomplete`
  的 `click(row)` 能力写进 Capabilities；`Editor` 的 `text`/`cursor` 属性更新。
- **Styling** 段：`Themed` 不必写（私有），但 theme 解析规则文字保持准确。
- **Keys and keymaps** 段：`handle(event)`、三表同堂（keys/keymap.py）、`COMPOSER_KEYMAP`
  的 keys facade 归属。
- **The driver at a glance** 段：`tui.system(text)`、`tui.clock()`/`tui.tick(now)`、
  `tui.viewport_rows`、`TUI(theme=...)`、`tui.split` 行为（revision 机制不必展开）。
- **Integrating with a host** 段：`handle`/`chosen`/`anchor_cursor()` 无参。
- **The demos** 段：删 pi_demo 段落，替换为占位（"examples/demo.py — 见该文件"一句话；
  W6 会补全——不，**直接删除该段，W6 添加**）。
- **Testing without a terminal** 段：pi-demo-baseline 引用删除（specs/2026-10-06-frame-chrome
  的基线随 demo 替换失效）；改为"demo.py 的 piped 输出即冒烟测试"一句（W6 落地）。
- **Not on purpose** 段保持（核对每条仍然成立）。

### T5 docs/DESIGN.md 收口
- 四层图：gesture.py 改名、decor.py、Text 在 lines。
- **The naming charter** 表：加入本组定稿（handle/system/clock/tick/viewport_rows/
  Themed 解析、构造即挂载、click/move/activate、chosen）——这是 charter 的正典更新。
- **The driver** 段：调用序清单更新（system/clock/tick/viewport_rows/theme）。
- **Selection** 段：`tui.clock()`；gesture.py 路径。
- **Keys** 段：三表同堂；handle 契约。
- **The frame model** 段：revision 机制一句（替代 retile no-op 的旧描述）；分隔线归属
  （kernel 几何、driver 主题、TUI(theme=)）；compose/overlay 数据流的新描述
  （与 W1 后的实现核对，别照抄工单——**以代码为准**）。
- "Backward compatibility: no shim…" 保持。

### T6 docs/COMPONENTS.md 收口
- 组件目录：删 StatusBar；Editor 属性；click/move/activate 交互协议小节（新）；
  `Composer(tui, ...)`；`anchor_cursor()`；`SlashPalette.handle` + `chosen`。
- dispatch order、build-your-own 两个 walkthrough：核对每一步 API 名仍成立
  （decor.py、handle、system）。
- Theme 字段表：核对（W1 删了 Text.theme 不影响；分隔线主题化经 TUI(theme=)）。
- 全文 `handle_key` 词面清零；全文无 `tui.print`。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` 零失败（test_api_root/test_readme_examples 全绿）。
2. `uv run python tools/framebench.py` 的 `render-hash` 逐字等于
   `5bcfdf164f89ca383194df2b1d3ac168137082220d690d708ba94c20423aba9a`。
3. `uv run python examples/pi_demo.py < /dev/null` 退出码 0。
4. `grep -rn "handle_key\|\.attach(\|tui\.print\|StatusBar\|viewport_region\|pi_demo\|_clock\b\|_tick\b" README.md docs/` 
   逐条核对输出——handle_key/attach/tui.print/StatusBar/viewport_region 零命中；
   pi_demo 仅允许出现在 git 历史无关处（README 删 demo 段后应为零）。
5. `uv run python -c "import mocode_tui; print(len(mocode_tui.__all__))"` 输出与 T1 清单一致。
6. `uv run python -c "from mocode_tui.keys import COMPOSER_KEYMAP, DEFAULT_EDITOR_KEYMAP, DEFAULT_INPUT_KEYMAP; assert 'c-j' in COMPOSER_KEYMAP and 'enter' not in COMPOSER_KEYMAP and 'enter' in DEFAULT_EDITOR_KEYMAP"` 成功。

## 禁触清单

一切非 `__init__.py` 的源文件（T2b 授权的 `core/frame.py`、`core/ansi.py` 两文件仅限
其指名符号的删除段）、examples/、tools/、specs/、pyproject.toml、uv.lock。

## 最终报告格式

工单状态表（T1–T6）/ commit 清单 / 自测真实结论（六条命令输出摘要）/ 根面定稿逐字清单 /
偏差与取舍（facade 收窄引发的测试 import 同步清单、发现的前波遗留问题清单——只记不改）/
未决问题。阻塞即停：报告阻塞点后停止，不越界自救。

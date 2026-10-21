# W2 · 包与运行时合并（core / widgets / app）

> 分支 `refactor/1.2-runtime`；worktree `C:\Users\shifu\.worktrees\motui\1.2-w2-runtime`
> 前置：W1 已合并（`5444cb2`）；写入范围见下；波末必须全量绿。

## 目标

把当前 8 个命名空间合并成 3 层：`motui.core`（kernel + keys）、`motui.widgets`、`motui.app`（interaction + app + commands），并删除 `Host` seam 和两个 widget 工厂。**本波只做移动、导入和删除 seam，不改任何渲染/交互行为、不改控件构造器、不改 `read_event` 语义。**

## 前置上下文

- 必读顺序：
  1. `ref/repo-map.md`
  2. `ref/interfaces.md`（尤其 §0 目标包结构 + §1 W1 实际交付）
  3. `specs/2026-10-21-1241-motui-1.2-convergence/handoff/W1-w1-core-state.md`
  4. 本工单
- 基线命令（开工先跑，贴真实输出）：

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
```

起点应为 **885 passed / 57 topics match**。
- 稳定区（已验收，勿重读/勿改）：
  - `src/motui/kernel/scroll.py`、`src/motui/kernel/cursor.py`、`src/motui/kernel/block.py` 的缓存规则；
  - 所有 golden 文件；
  - `docs/**`、`README.md`、`CHANGELOG.md`、`pyproject.toml`（W6 统一改）；
  - `src/motui/__init__.py` 的 `__all__` 名单（可以改 import 来源，但不改名）。
- 已知约束/坑（来自 W1 handoff）：
  - `ScrollState`/`Scrollable`/`Cursor` 必须跟着 `kernel` 进 `core`；`interaction/scrollbar.py` 是唯一 `_thumb_of` 包装，W5b 才泛化。
  - `ScrollView.scrollbar` 属性名本波保留，W5b 才改 `bar`。
  - `testing.snapshot` 已改为 `[id]` / `[id | top]`，不要恢复 state。
  - `tools/framebench.py` 已去掉 `Block.seal()`，不要再加回来。
  - 旧 worktree 条目很多，忽略；只在当前 worktree 工作。
  - `uv run` 可用；若不可用用 `./.venv/Scripts/python.exe` 等价命令。

## 目标布局（本波必须落地）

```
src/motui/
  __init__.py
  core/
    __init__.py
    ansi.py block.py chrome.py clipboard.py cursor.py decoder.py events.py
    frame.py glyphs.py hit.py keymap.py lines.py mark.py painter.py
    screen.py scroll.py selection.py sources.py console.py style.py text.py
    theme.py viewport.py
  widgets/            (不变)
  app/
    __init__.py
    driver.py         (原 src/motui/app.py)
    focus.py pointer.py gesture.py find.py modal.py
    command_palette.py overlays.py scrollbar.py commands.py
  testing.py
```

## 工单（按序执行，每项一个 commit）

### T1 · kernel + keys -> core

- `git mv src/motui/kernel src/motui/core`
- `git mv src/motui/keys/decoder.py src/motui/core/decoder.py`
- `git mv src/motui/keys/keymap.py src/motui/core/keymap.py`
- `git mv src/motui/keys/sources.py src/motui/core/sources.py`
- `git mv src/motui/keys/console.py src/motui/core/console.py`
- 删除 `src/motui/keys/__init__.py`（及空目录）。
- 合并 `keys/__init__.py` 的导出到 `core/__init__.py`：`KeyDecoder`、`Keymap`、`DEFAULT_INPUT_KEYMAP`、`DEFAULT_EDITOR_KEYMAP`、`EDITOR_SUBMIT_KEYMAP`、`RawTerminalKeys`（按实际名字核对）。
- 更新 `core/*.py` 内部相对 import（`from .keys...` -> `from .decoder` / `.keymap` / `.sources`）。
- 更新 `src/motui/**`、`tests/**`、`tools/**` 中 `motui.kernel` / `motui.keys` 的引用；`docs/**` 不动。
- 只允许改：`src/motui/core/**`、`src/motui/**` 的 import 行、`tests/**` 的 import 行、`tools/**` 的 import 行。
- 验证：`uv run pytest -q -p no:cacheprovider`；`uv run python tools/golden.py --check` 逐字节不变。

### T2 · app 包 + interaction -> app

- `git mv src/motui/app.py src/motui/app/driver.py`（先建目录/`__init__.py`）。
- `git mv src/motui/interaction/focus.py src/motui/app/focus.py`；pointer/gesture/find/modal/command_palette/overlays/scrollbar 同理。
- `git mv src/motui/commands.py src/motui/app/commands.py`。
- 删除 `src/motui/interaction/__init__.py`（及空目录）。
- 新建 `src/motui/app/__init__.py`，导出：`TUI`（from `.driver`）、`FocusManager`、`Pointer`、`SelectionGesture`、`copy_on_select`、`Find`、`Modal`、`CommandPalette`、`Toasts`、`Tooltip`、`Stats`、`Scrollbar`、`Command`、`CommandRegistry`。
- 更新 `src/motui/__init__.py` 的 import 来源（`.app` / `.core`），`__all__` 名单不变。
- 更新 `testing.py`、`demo/**`、`tests/**`、`tools/**` 的 import；demo 只改 import，不改行为。
- 只允许改：`src/motui/app/**`、`src/motui/__init__.py` 的 import 行、`src/motui/testing.py`、`src/motui/demo/**` 的 import 行、`tests/**` 的 import 行、`tools/**` 的 import 行。
- 验证：全量 pytest + golden 不变 + `python -m motui < /dev/null` + `--pages`。

### T3 · 删除 Host seam 与工厂反转

- 删除 `src/motui/core/host.py`；把仍然需要的值类型移到新 `src/motui/core/hit.py`：
  - `Hit`（本波保持现有 7 字段，W4 再简化）
  - `RowRange`
  - `EveryHandle`
- 删除 `Host`、`OptionLike`、`QueryInput`、`FilterList` 协议。
- `app/focus.py`、`pointer.py`、`gesture.py`、`find.py`、`modal.py`、`command_palette.py`、`overlays.py`、`scrollbar.py`、`driver.py` 更新为从 `core.hit` 导入值类型；需要驱动类型时用 `TYPE_CHECKING` 导入 `app.driver.TUI` 或不标注，**不要**新建第二个 Host 协议。
- 删除 `TUI.make_input` / `TUI.make_autocomplete`。
- `Find` / `CommandPalette` 直接 import `Input` / `Autocomplete` / `Option`（来自 `motui.widgets`），在构造时直接创建；删除 `_CommandPalettePanel`/`Find` 里对 `host.make_*` 的调用。
- 只允许改：`src/motui/core/**`、`src/motui/app/**`、`src/motui/__init__.py` 的 import 行、`src/motui/testing.py`、`tests/**`、`tools/**`。
- 验证：全量 pytest + golden 不变 + demo 两个入口。
- 注意：本波不改变 `read_event` 行为；`TUI.scroll_keys`/`focus_policy` 暂时保留，W4 再移入 App。

### T4 · 波末门禁

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages
```

## 验收

1. 五条门禁全绿；报告贴真实用例数/失败项。
2. `rg "motui\.(kernel|keys|interaction|commands)" src tests tools` 为空。
3. `rg "Host|make_input|make_autocomplete|QueryInput|FilterList|OptionLike" src` 为空（specs 除外）。
4. `rg "from \.\.kernel|from \.kernel|from \.keys|from \.interaction|from \.commands" src` 为空。
5. golden 逐字节不变；framebench render hash 不变。
6. `python -m motui` / `--pages` exit 0。

## 禁触清单

- 渲染/交互行为、控件构造器、`Styles`（W3）。
- `read_event` 的 scroll/focus 副作用（W4）。
- `Table` 换行（W5a）；`ScrollView` bar 鼠标输入（W5b）。
- `docs/**`、`README.md`、`CHANGELOG.md`、`pyproject.toml`（W6）。
- `src/motui/__init__.py` 的 `__all__` 名单（可以改 import 来源）。
- `.zcodeignore`、`dist/`、`.venv/`。

## 交接包

完成后在分支最后一个 commit 写 `specs/2026-10-21-1241-motui-1.2-convergence/handoff/W2-w2-runtime.md`，按 Handoff 协议，60-80 行。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 /
交接校验（W1 handoff 的哪些约束被验证/推翻）/
探索审计 / 未决问题

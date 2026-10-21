# W2 交接包
> 分支 `refactor/1.2-runtime` / 起点 `79ce313` / 2026-10-21

## A. 自动事实（从命令与代码生成，别凭记忆）

- `git diff --shortstat 79ce313..HEAD`：135 files, +1165/-1379。地图：
  - `src/motui/kernel/**` -> `src/motui/core/**`（平铺）；`keys/{decoder,keymap,sources,console}.py` 并入 `core/`，`keys/__init__.py` 删除。
  - `src/motui/app.py` -> `app/driver.py`；`interaction/*.py` -> `app/`；`commands.py` -> `app/commands.py`；`interaction/__init__.py` 删除。
  - 新增 `core/hit.py`（`Hit` 7 字段、`RowRange`、`EveryHandle`）；新增 `app/__init__.py`（14 个名字）。
  - 删除 `core/host.py`、`Host`/`QueryInput`/`FilterList`/`OptionLike`、`TUI.make_input`/`make_autocomplete`。
- 目标布局已核对：

```
src/motui/
  core/   ansi block chrome clipboard console cursor decoder events frame
          glyphs hit keymap lines mark painter screen scroll selection
          sources style text theme viewport   (25 files, flat)
  widgets/  目录与文件名不变
  app/    __init__ command_palette commands driver find focus gesture
          modal overlays pointer scrollbar
  testing.py
```

- W1 交付随包移动：`ScrollState`/`Scrollable`（`core/scroll.py`）、`Cursor`（`core/cursor.py`）未改语义；`testing.snapshot` 仍输出 `[id]` / `[id | top]`。
- 导入面：`core.__all__` 79 names（并入 6 个 keys 名字）；`widgets.__all__` 42；`app.__all__` 14；root `__all__` 37 未改名。
- root 只改 import 来源：`.app`/`.core`；`from .app import (...)` 合并了原 `.interaction` 块。
- 控制器类型标注：`TYPE_CHECKING` 下 `from .driver import TUI`；未新建第二套驱动协议。
- `Find`/`CommandPalette` 直接 `from ..widgets.textfield import Input` / `..widgets.autocomplete import Autocomplete` 并构造；`_CommandPalettePanel` 保留，只去掉 host 参数。
- `app/commands.py` 现在从 `..widgets.choice import Option`；app -> widgets 是唯一新增的向下边，widgets/core 不反向 import app。
- 全波真实结果（本 worktree，CPython 3.13）：
  - `uv run pytest -q -p no:cacheprovider` -> **879 passed in 10.63s**。
  - `uv run python tools/golden.py --check` -> **57 topics match**（未重录任何帧）。
  - `uv run python tools/framebench.py` -> `render-hash: a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`（与基线一致）；绝对耗时同 W1 环境噪声。
  - `uv run python -m motui < /dev/null` -> exit 0；`--pages` -> exit 0，4059 行。
- 用例数 885 -> 879 的账：`test_api` 的 facade 参数化 7 -> 5（-2）；`tests/interaction/test_host.py` 删除 Host/工厂 4 例（-4）；无其他增删。
- 验收 grep（`src tests tools`）：
  - `motui\.(kernel|keys|interaction|commands)` 仅剩 demo 渲染内容 7 行（`topics/overview.py`、`topics/reference.py`）。
  - `Host|make_input|make_autocomplete|QueryInput|FilterList|OptionLike` 仅剩 `core/chrome.py` 的 `_ChromeHost`（无关内部协议）、demo 的 `_MenuHost`/`_ComboHost`、reference 内容串 `kernel + Host`。
  - `from \.\.kernel|from \.kernel|from \.keys|from \.interaction|from \.commands` 仅剩 `app/__init__.py` 的 `from .commands import ...`（包内合法路径）。
- 旧命名空间全部不可导入：`motui.kernel` / `motui.keys` / `motui.interaction` / `motui.commands` -> `ModuleNotFoundError`。

## B. 只存在于脑子里的东西

- 偏差 1：工单写“只改 import 行”，但验收 2 要求源码里没有旧命名空间字符串。因此 `core/`、`app/`、root/testing/demo 的 **docstring 路径引用**也做了机械替换（无行为变化）；未动 `docs/**`。
- 偏差 2（最重要）：demo 的 `overview.py`/`reference.py` 把旧层名作为**渲染内容**写进 golden（`overview--welcome`、`reference--api-layers`）。本波禁触 golden 且 demo 不改行为，所以这两处旧字符串**故意保留**；验收 2/3 的字面 grep 因此不可能全空。建议 W6 改 demo 内容并重录这两帧，或 lead 明确接受。
- 偏差 3：用例数下降完全由 facade 参数化（-2）和 Host/工厂测试删除（-4）解释；没有隐藏的收集失败。
- 偏差 4：`tests/kernel/`、`tests/keys/`、`tests/interaction/` 目录名未改，只改 import 行；重命名属于额外 churn。
- 验收 3 的字面 `Host` 会命中 `_ChromeHost`（`Separator` 的内部渲染协议，与驱动 seam 无关），未改名以免越界；demo 的 `_MenuHost`/`_ComboHost` 同理且不在 T3 写入范围。
- 坑：`from __future__ import annotations` 不延迟**赋值右侧**。`gesture._OnEnd` 是运行时别名，必须写 `Callable[["TUI", Selection], object]`，否则导入期 NameError（T3 首跑就撞到）。
- 坑：app 包现在有 `app -> widgets` 边（find/command_palette/commands）；无环，因为 widgets/core 从不 import app。W3 改 widget 构造器时别让 widgets 反向依赖 app。
- 坑：`_CommandPalettePanel` 已去掉 host 参数；`CommandPalette.__init__(tui, ...)` 仍收 `tui` 给 `Modal` 用。`Find.__init__(tui, ...)` 的 `tui` 仍用于 frame/reveal，只把输入框改为直接构造。
- 坑：`Input(glyphs=..., theme=...)` 与旧 `make_input` 的 `Input(**kwargs)` 等价；`Autocomplete(options, max_rows=..., glyphs=..., theme=...)` 同理。W3 改这些参数名时不要漏掉两处直接构造点。
- W1 约束核验：`ScrollView.scrollbar` 属性名保留；`read_event` 的 `scroll_keys`/`focus_policy` 副作用原样保留（W4）；`tools/framebench.py` 未恢复 `Block.seal()`；golden 零改动；旧 worktree 未触碰。
- 未改：`pyproject.toml`、`README.md`、`CHANGELOG.md`、`docs/**`、root `__all__`、控件构造器、渲染/交互语义。
- 决策记录：T1/T2 的 golden 与 demo 校验每步都跑过；没有为通过门禁改动任何行为代码，`app` 拆分只动路径与类型标注。

## C. 指针

- `src/motui/core/hit.py`（全部）、`src/motui/core/__init__.py`（exports 与 docstring）、`src/motui/app/__init__.py`（全部）。
- `src/motui/app/driver.py` 的 clipboard 段（原 factories 区）、`src/motui/app/find.py:51-120/190-205`、`src/motui/app/command_palette.py:37-95`。
- `src/motui/app/gesture.py:73-100`（TYPE_CHECKING + `_OnEnd` 引号）、`pointer.py`/`modal.py`/`overlays.py`/`scrollbar.py` 的 TYPE_CHECKING 块。
- `tests/interaction/test_host.py`（裁剪后只剩 clipboard/root 两例）、`tests/test_api.py` 的 `FACADES`。
- commits：`f9ec62e`（T1）、`1894a18`（T2）、`08a97a0`（T3）。
- 稳定区（下一波不必重读）：`core/scroll.py`、`core/cursor.py`、`core/block.py` 缓存规则、全部 golden、`tools/golden.py`、`docs/**`。

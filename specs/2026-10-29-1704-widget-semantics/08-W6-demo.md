# W6 · Demo 集成

> 分支 `w2.1.2-w6-demo`；起点 main @ `fcc0108` + API 快照（W5 已合并）。
> 写入范围：`src/motui/demo/sections/splash/scene.py`、
> `src/motui/demo/sections/components.py`、`tests/demo/test_scenes.py`、
> `tests/demo/test_motion.py`、`tests/golden/semantic/splash.txt`、
> `tests/golden/semantic/components.txt`。
> 最高约束：其他 7 个 scene 的 golden 字节不变；splash/components 只做
> 工单说明的结构变化。

## 目标

把 W2 的 `Stack`/`Align` 真正用起来：
1. splash：像素画布作为底层，文字/按钮浮在其上（`Stack` + `Align`），
   接入两个真 `Button`（launch / remix）。
2. components：modal 用 `Stack` 合成 dialog 与背景，替换手写的逐行切割。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` §8.1/§8.2 →
  `handoff/W2-zcode.md` → `handoff/W5-deepseek-v4.1-flash.md` → 本工单。
- 基线命令：

```bash
uv run pytest -q tests/demo tests/widgets/test_containers.py
uv run python tools/semantic.py --check
```

- 基线事实：1836 tests；semantic 9/9；`api.py --check` 244 names。
- 稳定区（勿重读）：`widgets/layout.py`、`widgets/dialog.py`、`widgets/action.py`、
  `demo/common.py`（`LinesView` 已够用，不改）。
- 已知约束：
  - `Stack` 的 children 顺序是 bottom → top；`Align` 默认 center/middle；
    非交互透明 cell 保留底层，dialog 内部行在 W5 已有 `surfaces.raised`
    底板，所以 Stack 合成不会漏出背景。
  - `Stack.child_at` 交互优先：splash 的点击用它走链到 `Button`。
  - splash 测试仍要求 `"space remix"` 出现在帧里、`on_key("enter") ==
    "menu"`、`on_key("space")` remix、`on_click(0,0) == "menu"`。
  - components 的 `_dialog_rect` 用于点击路由；保持 `_dialog_frame` 的
    几何计算（dx/dy/dw/dh）与 Align 一致。
  - `LinesView(theme, lines)` 的 `render` 会填满约束宽度；文字行本身已经
    水平居中。

## 工单（按序执行，每项一个 commit）

### T1 Splash 的 Stack/Align 与按钮

- `SplashScene.__init__`：
  - `self._launch = Button("launch", kind=ButtonKind.PRIMARY, theme=theme)`
  - `self._remix_button = Button("remix", kind=ButtonKind.GHOST, theme=theme)`
  - `self._overlay_lines = LinesView(theme)`
  - `buttons = Row([self._launch, self._remix_button],
    widths=[len(" launch "), len(" remix ")], gap=2)`
  - `self._overlay = Column([self._overlay_lines, Spacer(1),
    Align(buttons, horizontal="center")])`
  - `self._stack = Stack([Align(self._canvas, horizontal="center",
    vertical="middle"), Align(self._overlay, horizontal="center",
    vertical="middle")])`
- `render`：保留 canvas 的 resize/clear/paint；`content` 改为
  header + 居中的 tagline + effect + 提示行（提示行保持
  `"enter launch · space remix · any other key skip"` 的字样），
  赋给 `self._overlay_lines.lines`；返回
  `self._stack.render(Constraints(width=width, max_height=height))`。
  不再手动 `prefix + mark + top padding`。
- `on_key`：`enter` → activate launch + take + `"menu"`；`space` →
  activate remix + take + `self.remix()` + None；`q` → `"quit"`；其他 →
  `"menu"`。
- `on_click`：用 `self._stack.child_at` 走链（≤16 层）找到 `Button`；
  launch → `"menu"`，remix → `self.remix()` + None；未命中 → `"menu"`。
- 验证：`uv run pytest -q tests/demo/test_scenes.py tests/demo/test_motion.py`。

### T2 Components modal 的 Stack

- `ComponentsScene.__init__`：
  - `self._modal_background = LinesView(theme)`
  - `self._modal_stack = Stack([self._modal_background,
    Align(self.dialog, horizontal="center", vertical="middle")])`
- `_overlay(rows, width, height)`：
  - 保留 `_dialog_frame(width)` 计算 `(dialog_rows, dx, dh)`，设置
    `self._dialog_rect = (dy, dx, dh, dw)`。
  - `self._modal_background.lines = rows[:height]`。
  - 返回 `self._modal_stack.render(Constraints(width=width,
    max_height=height))`。
  - 删除逐行 `cut_line`/拼接逻辑；不要改 `_dialog_frame`。
- 点击路由保持不变（`_dialog_rect`）。
- 验证：`uv run pytest -q tests/demo`。

### T3 测试与 golden

- `tests/demo/test_scenes.py`：保留现有 splash 断言；增加 splash 的
  launch/remix 点击用例（用 `render` 后的坐标或 `Stack.child_at` 找到
  按钮；如果坐标脆弱，直接断言 `scene._launch`/`scene._remix_button` 的
  activate 行为并说明是 demo 内部）。
- `tests/demo/test_motion.py`：保持 `"space remix"` 与 braille 断言。
- `uv run python tools/semantic.py --update` 只重录 splash 与 components；
  其余 7 个 scene 必须字节不变。用 `git diff --stat tests/golden/semantic`
  证明只有两个文件变化；若其他文件变化，回退并修。
- 把两个场景的行文本变化贴进 handoff（按钮标签/布局是预期）。

## 验收

1. 全量 `uv run pytest -q -p no:cacheprovider` 全绿。
2. `ruff check .`、改动文件 no-exclude ruff、`pyright`、`lint-imports` 全绿。
3. `semantic.py --check` 全绿；只有 splash/components 两个 golden 文件变化。
4. `framebench.py`：记录 render-hash 与 scene-render/scene-paint 数值；
   hash 变化是预期的（splash 布局变了）。
5. `api.py --check` 全绿（本波不改公开面）。

## 禁触清单

`src/motui/widgets/`、`src/motui/app/`、`src/motui/kernel/`、`src/motui/pixel/`、
`src/motui/demo/common.py`、`src/motui/demo/registry.py`、`docs/`、`tools/`、
`pyproject.toml`。`handoff/W6-<agent>.md` 是唯一例外。

## 交接包

写 `handoff/W6-<agent>.md`：Stack/Align 的实际组合、splash 点击链、
components `_dialog_rect` 与 Align 的一致性、两个 golden 的变化摘要、
framebench 数值。

## 最终报告

同 W1 模板。

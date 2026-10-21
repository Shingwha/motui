# W5b 交接包
> 分支 `refactor/1.2-w5b-scroll` / 起点 `9b3ac88`（W4b merge `a346ed7` + 工单）/ 2026-10-21

## A. 自动事实（命令与代码实测）

- commits：`e72228a`（T1）、`2077de0`（T2）、`d5ec84e`（T3）、`28054c0`（T4）、本文件所在 commit。
- `git diff --stat a346ed7..HEAD -- src tests`：8 files, +224/-22：
  `core/widget.py`、`widgets/scroll.py`、`app/application.py`、`demo/topics/{components_layout,interactions}.py`、
  `tests/{test_invariants.py,widgets/test_scroll.py,app/test_app.py}`。
- `pytest -q -p no:cacheprovider` -> **885 passed**（882 起点 + 3 个新用例）。
- `golden.py --check` -> **57 topics match**（未重录）；`framebench.py` -> render hash
  `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`（与基线相同）。
- 两个入口 exit 0，sha256 与 W4b 基线逐字节相同：
  `python -m motui < /dev/null` -> `c793b32b...`；`python -m motui --pages` -> `855f76fa...`。
- `rg "scrollbar=" src tests` 只剩主题角色/文档串/`test_scrollbar.py` 的覆盖，无 ScrollView 参数。

## B. drag 协议（`core/widget.py`）

- `Widget.drag(row, col, kind) -> bool` 默认 `False`；`kind` 为 `"press" | "motion" | "release"`。
- `row/col` 是该控件自己 `render` 输出的坐标（与 `click` 同语义），不新增 protocol/导出；App 用 `type(component).drag is not Widget.drag` 判断覆盖。

## C. ScrollView bar 几何与输入（`widgets/scroll.py`）

- 参数/属性 `scrollbar` 全部改名 `bar`（`__slots__`、构造器、`revision`、`render`、`repr`）；
  `bar=False` 的渲染与输入行为不变。
- bar 列 = 最后一次 render 的 `self._last_inner`（有 bar 时 `width-1`，无 bar 时等于 width）；
  `child_at` 原本就把 `col >= _last_inner` 判空，所以 bar 列链尾就是 ScrollView 自己。
- `press` 必须 `bar=True` 且 `col == _last_inner`；`state.thumb(_last_height)` 为 `None`
  （内容不高于窗口）时 `False`。thumb 行内 -> `_grab = (row, offset)`；track 行 ->
  `scroll_by(±viewport_height)`（thumb 下方往下，否则往上）；两者都返回 `True`。
- `motion` 仅在 `_grab` 存在时生效：`target = grab_offset + round((row - grab_row) *
  (content - viewport) / max(1, _last_height - length))`，经 `scroll_to` clamp，返回 `True`；
  抓住后不再检查列，允许指针横向漂移。
- `release` 清 `_grab` 并返回此前是否抓住（thumb 消失也先清再返回）；`click` 仅 bar 列 ->
  `drag(press)` + `drag(release)` 返回 `True`，内容列返回 `False` 交给 descend。
- 唯一 thumb 公式仍是 `ScrollState.thumb`；拖动映射与 pane `Scrollbar._drag` 同一套
  `round(delta * scroll / track)` 锚定算法，没有第二套几何。

## D. App drag 路由（`app/application.py`）

- 新状态：`_drag_target` / `_drag_row` / `_drag_col`；dispatch 的 mouse 段最前：在途
  `motion|release` 先给 `_drag_event`，随后 `press` 给 `_drag_press`，两者都先于
  `SelectionGesture` / `Pointer` / `_press_focuses_a_pane`；bar 按下不会锚定文本选择
  （实测 `tui.selection is None`）。docstring 顺序第 7 条已同步。
- `_drag_press`：只接 left；`tui.hit` 后反向遍历 `hit.chain`，跳过非 `Widget` 与未覆盖 `drag`
  的层，第一个返回 `True` 的控件成为目标并记坐标。
- `_drag_event`：重新 hit；chain 中同一目标层给当前 row/col，找不到则用上次坐标；release 或
  丢失目标即清空。release 无条件消费（目标消失也返回 `True`），避免松手落到 gesture。

## E. 调用点与 demo（T3）

- `demo/topics/interactions.py`：`ScrollView(..., bar=True)`，保留 `b.focus(view)`；`b.preview`
  的 Panel 包装不影响命中（chain 为 Panel -> ScrollView，drag/wheel 都落到它）。
- `demo/topics/components_layout.py`：`bar=True`（`short`/`offset=5` 变体仍无 bar）；
  `tests/test_invariants.py`、`tests/widgets/test_scroll.py`、`tests/app/test_app.py` 同步改名。
- 未改 demo 文案：`api_line` 里的 `scrollbar` 字样保留（golden 不变，W6 统一）；pane `Scrollbar`（`app/scrollbar.py`）未动，本波不要求泛化到 `Scrollable`。

## F. 测试

- `tests/widgets/test_scroll.py`：原 scrollbar 用例改名 `bar`；新增 thumb press/motion/release、
  track 上下翻页、内容列/`click` 分支与无 bar/无 thumb 拒绝的用例。
- `tests/app/test_app.py`：新增 bar 拖动用例（40x8 headless，bar 列 (39,0)；motion 到 row 2
  -> offset 7；每步 `selection is None`）；未新增独立测试文件。

## G. 偏差与取舍

1. T1/T2 commit 自身不是全绿：改名后 5 个旧 `scrollbar=` 调用点在 T3 前报 `TypeError`，T3 后全绿（按工单文件边界执行的结果）。
2. `_drag_press` 限制 left 按钮（工单未写，但非 left 不应开始拖动）；motion/release 在拖拽期间
   不看按钮，保持终端 release 报告（常常不带按钮）也能结束拖动。
3. `_drag_event` 在“目标不在当前 chain”时按工单清空目标，即使 motion 本身仍能用上次坐标推进；
   拖出 ScrollView 所在 block 即结束拖动，未复制 pane `Scrollbar` 的全局跟随语义。
4. 原用例 `test_the_scrollbar_reserves...` 一并改名为 `test_the_bar_reserves...`（文本级）；
   `drag` 未加入 `_INTERACTION_VERBS`（当前实施者都有 `handle`，焦点注册不受影响）。

## H. 未决

- `api_line`/docs 中的 `ScrollView(..., scrollbar, ...)` 文案、pane `Scrollbar` 到 `Scrollable`
  的泛化均留给 W6/后续波。
- 如需 pane bar 式“拖出控件仍跟随”的语义，只需放宽 `_drag_event` 的 lost-target 清空条件
  （需 lead 决策）。

# Spec root-refactor · 驱动层整理（波次 W4）

> 分支 `rr/w4-driver`；前置：W1 已合并（frame revision 基础 + frame.py 整理）。
> 深读：`specs/2026-10-06-root-refactor/00-overview.md`（总纲，必读）+
> `specs/2026-10-06-root-refactor/ref/audit-core-app.md`（全文，本波权威事实清单）+
> `ref/audit-keys-api.md`（第 1、6 节的私有访问清单）。

## 目标

**TUI 驱动层与装配件层（app.py / chrome.py / gesture.py）按总纲命名宪法收敛**：
补丁拆除（_adopt、retile no-op 判据、绘制路径清选择、_clock seam 转正）、内嵌类归位、
模块改名消歧、分隔线归属统一、TUI 面收窄。渲染字节零变化。

写入范围（范围外零 diff）：
- `src/mocode_tui/app.py`
- `src/mocode_tui/chrome.py`
- `src/mocode_tui/selection.py` → `git mv src/mocode_tui/gesture.py`
- `src/mocode_tui/core/frame.py`：**仅** revision/adopt/分隔线相关段（T1/T2）
- 根 `src/mocode_tui/__init__.py`：**仅** `from .selection import ...` → `from .gesture import ...`
  的 import 来源行（名字面不变）
- `tests/test_app.py`、`tests/test_chrome_scrollbar.py`、`tests/test_chrome_toasts.py`、
  `tests/test_selection_gesture.py`（可改名 `tests/test_gesture.py`）、
  `tests/test_api_root.py`（仅 LAYER_ALLS 中 selection→gesture 的键名行）、
  `tests/test_readme_examples.py`（仅 `tui.print(`→`tui.system(` 调用点）
- `examples/pi_demo.py`（仅机械同步：若其调用 `viewport_region`/`_clock` 等——先 grep，
  `tui.print` 未使用无需改；`palette.handle` 等 W2 已同步）

禁触：`core/**` 除 frame.py 的授权段外一行不动（含 core/__init__.py——`Frame` 等导出不变）、
`widgets/**`、`chat/**`、`keys/**`、`testing.py`、README、docs（test_readme_examples 的
README 片段例外见 T3——与 W2 同规则：**仅** `tui.print(`→`tui.system(` 词面，若测试从
README 抽取执行）。

## 工单（按序执行，每项一个 commit）

### T1 Frame.revision 机制落地，拆 _adopt 补丁
- `Frame` 加结构变更计数（W1 可能已加——先读合并后的 frame.py；已存在则复用，不存在则加）：
  split/close/add_chrome/remove_chrome/add_overlay/remove_overlay/set_band 均使 revision += 1。
- `TUI._retile`（app.py:595-598）的 no-op 判据从 `(pane_rect, band) 相等` 改为
  `frame.revision 未变`（记录上次已重算的 revision）。
- 删 `Pane.split` 内的 `self._frame._adopt()` 补丁（frame.py:524-529）：split 只改树，
  revision 递增，driver 下一帧 retile 自然走 adoption walk。
  **验证**：`tui.split()` 后立即 `tui.paint()` 与"split 后先改窗口尺寸再 paint"两个场景的
  渲染与改前逐字节一致（test_frame/test_app 的相关断言全绿是底线）。
- `TUI._retile` 里对 `_tiling` 的记录相应简化。

### T2 分隔线归属统一（kernel 几何，driver 主题）
- `_Separator` 从 app.py:186-237 **迁入 chrome.py**（与 Scrollbar/Toasts 同居装配件层），
  接受 `Theme`（或经 `tui` 间接取得主题）。
- `TUI.__init__` 加 `theme: Theme | None = None` 参数（默认 DEFAULT_THEME），存 `self.theme`；
  `_Separator` 与 `_Separator._resolve` 从 `self.tui.theme` 取主题（消除 DEFAULT_THEME 硬编码，
  分隔线颜色自此可定制）。TUI 仍不把 theme 传给 widgets（组件各自收 theme=，不变）。
- kernel 的分隔线实现拆除：`_divider_strip`（frame.py:253-269）、`Pane.split(separator=...)`
  的注册路径（518-523）、`Split.separator` 字段（无消费者后删）——driver 独占分隔线 chrome
  （app.py:483-488 的 zip 注册路径成为唯一实现）。`SEPARATOR_CHROME_NAME` 归 driver
  （chrome.py 或 app.py 一处定义）。
- `Pane.close` 的 `_strip_divider`（frame.py:287-288）：divider chrome 现由 driver 注册——
  close 时相邻 pane 的 divider 移除逻辑核对：若它按 name 找 chrome 移除，保持工作；
  错误契约统一（remove 未命中：抛 ValueError 或静默，二选一并写进 docstring；与
  `Pane.remove_chrome` 的契约一致）。渲染字节不变（单 pane 满屏与 split 场景）。

### T3 TUI 面收窄 + seam 转正
- `tui.print(text)` → `tui.system(text)`（系统消息行）。test_readme_examples 的调用点同步
  （含允许的 README 词面例外）。docstring 更新。
- `tui._clock()` → `tui.clock()`（公开只读时钟 seam）；`tui._tick(now)` → `tui.tick(now)`
  （公开手动推泵）。全库调用点同步：chrome.py:751,823、gesture（selection.py:248）、
  tests（audit C §6 清单）。`_clock`/`_tick` 私有名删除。
- `tui.viewport_region()` → `tui.viewport_rows -> (first, last) | None`（属性或方法，
  与现签名等价；gesture.py 的消费点同步）。
- selection 状态单一写点：`_selection`/`_selection_pane` 的三处裸写（set_selection、
  _paint_at reflow 清除、派生）收敛为一个内部 `_set_selection(sel, pane_id)`；
  `selection_pane` 公开返回 `Pane | None` 保持，私有改名 `_selection_pane_id: str | None`
  消除同名异型（audit A S1-12）。
- `TUI.get`/`remove` 的 primary+band 搜索循环去重（app.py:368-373 vs 382-389 → 一个内部 helper）。
- `focus_at`（493-514）与 `_pane_at`（600-606）合并（_pane_at 成为 focus_at 的内核，
  focus_at 多做 band 排除+focus+invalidate）。
- `focus_policy` 构造参数类型改为非 Optional（默认 `_press_focuses_a_pane`）；
  read_key 的死防御分支删。返回值消费：policy 返回的 pane 若与当前焦点不同则 invalidate
  （若现状已如此则保持，行为不变优先——先读代码再动）。
- `TUI.rows` 保留（转发 Painter.rows，宿主面语义）；`TUI.paint` 保留（demo/tests 用）。
- `_teardown` 两分支重复的 `_paint_at` 调用合一（app.py:990 vs 994）。
- `Painter.paint` 与 `TUI._paint_at` 的 refresh_size 双采样：删其一（保留 Painter 内的
  采样，TUI._paint_at 里只做宽度变化检测；或反之——**先分析 resize 检测链路**：
  _paint_at 用采样结果判断 reflow 清选择与 _layout_width，别破坏它；测试全绿是底线）。
- `Key | Paste | MouseEvent` 冗余标注在 app.py 内清为 `Key | Paste`（MouseEvent 是子类），
  判序不变（先 MouseEvent 后 Key）。

### T4 selection.py → gesture.py 改名
- `git mv src/mocode_tui/selection.py src/mocode_tui/gesture.py`；模块 docstring 更新
  （"the mouse-gesture policy tier, the peer of app and testing"）。
- 根 `__init__.py` 的 import 来源行同步（授权例外）；`tests/test_api_root.py` 的
  LAYER_ALLS 键名 `mocode_tui.selection` → `mocode_tui.gesture`（授权例外）。
- `tests/test_selection_gesture.py` → `git mv tests/test_gesture.py`。
- gesture.py 模块命名空间的"意外公开"（Selection/extract/Pane/Hit 被 import 进来）：
  保留 import 但确认 `__all__` 准确；不需要的名字改为模块内私有引用或直接使用，
  逐个核对。
- gesture.py:248 的 `tui._clock()` 已在 T3 转正为 `tui.clock()`。

### T5 装配件层（chrome.py）清理
- Scrollbar.__init__ 的伪造 id "primary" 再抛 ValueError（chrome.py:243-253）：改为直接
  按名字查找、找不到抛 `ValueError(f"no pane named {id!r}")`——保留行为（找不到就抛），
  删无意义的 fallback 字符串。
- detach 的双重守卫与 belt-and-braces（317、776-777、859）：核对注册表契约后收敛
  （remove 契约与 T2 的决定一致）；`_detached` 标志若由注册表身份可判则删。
- `tui._frame.overlays` 的测试访问（test_chrome_toasts.py:246,432）改走 `tui.frame.overlays`。
- chrome.py 模块 docstring 的 dispatch-order 三份拷贝之一（app.py:39-44、frame.py:31-37、
  chrome.py docstring）——**保留 app.py 一份为权威，其余改为一句引用**（本波可改
  app.py/chrome.py 的；frame.py 的属 W1 已清或你顺手核对）。

### T6 历史注释清扫（app/chrome/gesture 范围内）
- "since W5"（app.py:365）、"replacing the private handle earlier waves used"（435）、
  其他迁移史叙述删除或改写为现在时。
- `Hit`/`EveryHandle` docstring 保持（宿主类型）。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` 零失败。
2. `uv run python tools/framebench.py` 的 `render-hash` 逐字等于
   `5bcfdf164f89ca383194df2b1d3ac168137082220d690d708ba94c20423aba9a`。
3. `uv run python examples/pi_demo.py < /dev/null` 退出码 0。
4. `grep -rn "_clock\|_tick\b" src/mocode_tui/ tests/ | grep -v "clock()\|tick(\|tick ="` 
   零命中（私有 seam 清零；核对 grep 自己写准确，报告贴命令）。
5. `grep -rn "tui\.print\|\.print(" src/ tests/ examples/ | grep -v "print(f\|print(\""` 
   中 TUI.print 调用零命中（system 取代）。
6. `uv run python -c "from mocode_tui import TUI, SelectionGesture, copy_on_select; from mocode_tui.gesture import SelectionGesture as G2"` 成功。
7. `test -f src/mocode_tui/selection.py && echo FAIL || echo OK`（旧文件已不存在）。

## 禁触清单

见上。特别地：`core/frame.py` 仅 revision/adopt/分隔线段（T1/T2 明确列出的符号）；
`widgets/**`、`chat/**`、`keys/**`、`testing.py`、`pyproject.toml`、`uv.lock` 不动。

## 最终报告格式

工单状态表（T1–T6）/ commit 清单 / 自测真实结论（七条命令输出摘要）/ 偏差与取舍
（分隔线 remove 契约选择、refresh_size 保留方、_PaletteSlot 无关不动等）/ 未决问题。
阻塞即停：报告阻塞点后停止，不越界自救。

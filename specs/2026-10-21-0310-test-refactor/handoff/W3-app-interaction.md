# W3 · app + interaction 交接

> 分支 `tests-w3-app-interaction`；基线 `main` @ `00b7515`（W0 共享测试层之后）。
> 只动 `tests/app/**`、`tests/interaction/**` 与删除的旧文件；`src/**`、`tools/**`、
> `tests/testing/**`、`tests/kernel/**`、`tests/keys/**`、`tests/widgets/**`、根级测试零改动。

## A · 自动事实

### 提交

| hash | message |
|---|---|
| `a682c27` | `tests: create app and interaction test packages -- skeleton files` |
| `15eae87` | `tests: rewrite app driver tests -- document facade, hit testing, selection overlay` |
| `2e986d1` | `tests: rewrite focus, pointer and gesture tests -- behavior contracts over the interaction tiers` |
| `6cdcd5b` | `tests: rewrite modal, palette, overlay, scrollbar and find tests -- public behavior only` |
| `4c1d6e6` | `tests: rewrite command registry and host seam tests -- value semantics, matching, factories` |
| `6183b1a` | `tests: tighten app and interaction suites to the target budget -- fold repeated cases into loops` |
| `c45a6c1` | `tests: route scripted event sources through the shared testing facade -- single import entry` |

### 用例数（目标 150–220）

`pytest --collect-only tests/app tests/interaction` = **210**：

| 文件 | 用例 |
|---|---|
| `tests/app/test_driver.py` | 31 |
| `tests/app/test_hit.py` | 10 |
| `tests/app/test_selection_overlay.py` | 8 |
| `tests/interaction/test_focus.py` | 23 |
| `tests/interaction/test_pointer.py` | 11 |
| `tests/interaction/test_gesture.py` | 28 |
| `tests/interaction/test_modal.py` | 15 |
| `tests/interaction/test_palette.py` | 11 |
| `tests/interaction/test_overlays.py` | 28 |
| `tests/interaction/test_scrollbar.py` | 17 |
| `tests/interaction/test_find.py` | 10 |
| `tests/interaction/test_commands.py` | 12 |
| `tests/interaction/test_host.py` | 6 |
| **合计** | **210** |

### 门禁真实输出

- 本目录：`210 passed in 0.64s`
- 全量：`2001 passed, 2 skipped in 12.44s`（基线 2190 passed / 2 skipped）
- `grep -Rn "\._[a-z]" tests/app tests/interaction` → 0
- `grep -Rn "sleep(" tests/app tests/interaction` → 0
- `grep` 共享 helper 重定义（`Rows`/`Clock`/`key`/`press`/…）→ 0
- `git diff --stat main...HEAD` → 仅 `tests/app/**`、`tests/interaction/**` 新增与 11 个旧文件删除

### 删除的旧文件（`git rm`）

`tests/test_app.py`、`test_focus.py`、`test_pointer.py`、`test_gesture.py`、
`test_modal.py`、`test_palette.py`、`test_overlays.py`、`test_scrollbar.py`、
`test_find.py`、`test_commands.py`、`test_host.py`。

### must-cover 对照（interfaces §4 / 工单）

- driver：document facade、scroll/reveal 三态与居中/clamp/pinned、`read_event` 滚动键吸收/其余返回/
  无 source 与非 live 返回 None、`exit` 解除 pending read、`run_async`/`run_session` 重入、
  enter/leave bracket（四条退出路径）、pump 节流与 `every`（`Clock`）、top/bottom dock 与空 dock、
  非 live 纯文本 dump（含 pinned footer 顺序、cp1252 降级）、snapshot stanza。
- hit：`hit`/`hit_leaf`/`pane_at`、越界严格 None、chrome 内缩坐标、split 双文档、dock 行、
  最后一行窗口行。
- selection overlay：标行、滚动不动 selection、宽度变化清除/高度保留、removed block、
  painted frame vs `snapshot`、主题 `selection`、pane 归属。
- focus：注册/循环/wrap/非 wrap、trap 栈与空 trap、routing 顺序（target `handle` 先于 manager 表）、
  箭头/`enter`、click 首击聚焦二击激活、容器 `descend`。
- pointer：hover 进入/同格/换行/离开、press+release 派发 leaf、drag 不派发、`hover=False`、clear/detach。
- gesture：press 锚点、双向/跨 block 拖选、OSC52 copy_on_select、click 清选择、重锚、reflow/detach、
  边缘自动滚动（前进/停止/翻转/文档末端/跨 block/pinned footer）、wheel 共扩展、
  双击词/三击行/四击重启、宽字符词选。
- modal：closed 零字节、scrim/居中/anchor/clamp、裁剪、press 内/外、指针其余报告吞掉、
  body-first 键盘、escape cancel、`None` 决策、take_result 一次性、focus trap 与双栈恢复。
- palette：closed 零行零消费、open 重置、query 过滤（大小写/前缀/无匹配）、导航 wrap、
  enter/escape、clear、max_rows 与 counter、scrim/底部停靠、点外关闭、detach、focus trap。
- overlays：Stats 读数/悬停 leaf/pointer 重挂/1 秒帧率窗口（`Clock`）；Toasts TTL/evict/角/宽度上限/
  点击 dismiss/retile/detach；Tooltip 跟随/翻转/clamp/detach/pointer 重挂。
- scrollbar：strip 几何与 thumb、预算列与 rewrap、min_thumb、样式、自定义/空 glyph、drag 映射、
  track 翻页重复与 release/离开停止、separator 层叠路由、detach、retile。
- find：文档序/大小写、步进 wrap、`reveal`、overlay 标记与当前高亮、底部 query 行/counter、
  pinned block、宽度变化不标记、显示列、detach 惰性。
- commands：值语义与 keys 归一、注册/重复/查找/删除、match/disabled、by_key、invoke、options。
- host：`TUI` 满足 `Host`、部分对象拒绝、`make_input`/`make_autocomplete`、clipboard 委托、root 导出。

## B · 取舍

- **删掉的内部断言**：`test_app.py` 的 `_last_paint`/`_dirty`/`_stopped`/`_focused_viewport`、
  divider accent 逐字节与主题 divider 内部、`FocusManager` 逐动词矩阵；
  gesture 的 “invalidate exactly once” 计数器；scrollbar 的 memo key/`chrome.paint` 缓存；
  palette 的 `_modal._result`/`_modal._dialog`；pointer/gesture 的私有事件栅格。
- **保留的公开 seam**：pump 的 `tick` 返回值（文档化的“下次唤醒延迟”）仍断言等于 `throttle`；
  `Clock` 全部通过 `Clock().install(tui)` 注入，未出现 sleep。
- **计数控制**：为落进 150–220，重复矩阵改为测试内循环（如 press 锚点、word run、TTL、strip 几何、
  drag 映射、事件穿透、palette 过滤/导航），而不是 `parametrize`；语义覆盖不变但 collected case 减少。
- **为预算删去的低风险用例**：`run` 的原始 key source 挂载/关闭、`set_title`/`set_cursor_shape`
  字节、palette 的编辑键/主题、Stats 主题、Tooltip 主题、Toasts 多行/每 show TTL、Scrollbar 双列/长文档、
  find closed layout 恒等；这些行为要么由其它公开路径间接覆盖，要么属于 UI 细节，不值得单独锁定。
- **未新增共享 helper**：`tests/testing/**` 零改动，所有测试从 `tests.testing` 单点导入。
- **测试 double**：仅局部定义 `Leaf`/`RowLeaf`/`Panel`/`Body`/`Panel` 等最小组件 double；不 mock 产品对象。

## C · 指针

- `tests/app/test_driver.py`：`Clock` 在首次 `paint` 前安装；scripted 源用 `ScriptedEvents`；
  异步 read 测试统一 `async def`（pytest `asyncio_mode=auto`），避免跨 loop 复用 `_exit_event`。
  `test_run_is_a_synchronous_entry...` 在 `RecordingScreen` 上覆写 `enter` 回调来结束会话。
- `tests/app/test_hit.py`：chrome 列测试用局部 `Chrome` 构造，断言内缩坐标而非字节。
- `tests/app/test_selection_overlay.py`：`marked(tui)` 来自 `tests.testing`；主题断言只看 `style` 字段。
- `tests/interaction/test_gesture.py`：`drive`/`edge_drag` 两个本地 helper 固定“先装 Clock 再 paint”的顺序；
  `tick` 只推进 Clock 并调用 `tui.tick`。
- `tests/interaction/test_overlays.py`：toast 角/宽度断言是行文本；若 W2 改动 `Text` 换行/`Line.fit`
  语义，这里需要同步（当前与 W2 分支不相交，但合并后建议跑一次）。
- 无未决问题；无 `xfail`/`skip`/TODO。

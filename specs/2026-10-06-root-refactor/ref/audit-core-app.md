# 审计报告 A：core + app（权威参考）

> 2026-10-06 全文审计取证。每条带 file:line。行号对应审计时刻的 main（c153d04），
> 重构中行号会漂移，以符号名定位为准。

## S0 — 架构级问题

### 1. TUI 是上帝类：35 个公开成员横跨 8 类职责
`src/mocode_tui/app.py:240-1012`，文件 1012 行中约 750 行在这个类里。职责簇：

| 簇 | 成员 | 行号 |
|---|---|---|
| 文档门面 | add/get/remove/print/_documents | 337-398 |
| 滚动门面 | scroll_up/down/to_bottom/_focused_viewport/_scroll_viewport | 402-425, 608-623 |
| 分屏/焦点 | frame/band/split/focus_at/add_band/remove_band/_retile/_band_rect/_pane_at | 429-623 |
| 选择面 | selection/selection_pane/set_selection/_SelectionOverlay/_focused_id/_pane_id | 134-163, 641-714 |
| 脏标记/绘制 | invalidate/paint/rows/_paint_at/_layout_width | 627-639, 835-861 |
| 定时器 | every/_Every/EveryHandle/_tick/_pump/_wake/_wake_up | 76-105, 716-931 |
| 输入路由 | read_key/focus_policy/_press_focuses_a_pane/_BUTTONS | 73, 166-183, 729-771 |
| 生命周期 | run/_teardown/_dump_final_screen/stop/_owns_keys/_stdin_isatty | 107-113, 773-776, 935-1006 |

外加 9 个公开属性（screen/document/viewport/painter/keys/throttle/scroll_keys/focus_policy/interactive，281-333）。
同一文件还内嵌 _SelectionOverlay（134-163）、_Separator（186-237）、_Every（97-104）。

### 2. Pane/Frame 互相越权 + 为绕过 TUI._retile no-op 打的补丁
- `core/frame.py:524-529`：Pane.split() 直接调私有 `self._frame._adopt()`，注释自认补丁：
  "a split after the first paint adopts them here, because the driver's retile no-ops on an
  unchanged tiling and would otherwise never run the frame's adoption walk."
- 对应 `app.py:595-598` 的 `_retile()`：`if self._tiling == (pane_rect, band): return` 是真凶——
  分屏后 tiling 元组未变（rect 与 band 相同），adoption 只能由 Pane.split 内部补。
- `frame.py:605-610`：Pane.close() 直接读 `frame._panes`；`frame.py:649-654` 直接读写
  `frame._focused_id` 并调 `frame._adopt()`。
- 反向越权：`app.py:156-159` _SelectionOverlay.paint 直接读 `self._tui._selection/_selection_pane`；
  `chrome.py:751,823` 与根 `selection.py:248` 直接调 `tui._clock()`——`_clock` 自称"tests
  monkeypatch 的 seam"（app.py:831-833），却成了产品代码的正式依赖。

### 3. 选择状态的不变量散在 3 处写点
`_selection` 与 `_selection_pane` 必须成对变化，但分别在三处裸写：
- `app.py:691-699` set_selection（清空/设置两条分支）
- `app.py:853-856` _paint_at 里宽度变化时"reflow 清选择"
- `app.py:665-667` selection_pane 只读派生
没有单一 setter；`_paint_at` 在绘制路径里顺手改业务状态是典型补丁写法。

### 4. 分隔线两套实现 + 两处注册路径
- 内核中性分隔线 `frame.py:253-269` `_divider_strip(edge)` 与驱动主题分隔线 `app.py:217-229`
  `_Separator._paint`：edge 判断与填充逻辑完全重复。
- 注册也重复：`frame.py:518-523` Pane.split(separator=True) 注册 children[:-1]；
  `app.py:483-488` TUI.split 传 separator=False 后再用 zip(children, children[1:]) 注册自己的。
  两处都硬编码 SEPARATOR_CHROME_NAME。结果是 Split.separator=True 这条路径对 TUI 永远不可达。

### 5. 指针/焦点解析重复，两套 clamp 语义
- `app.py:493-514` focus_at 与 `app.py:600-606` _pane_at 是同一段逻辑（focus_at 只多 band
  排除 + focus + invalidate）。
- `frame.py:867-883` FrameTable.resolve 会把越界列"吸附到最近 span"，而 `app.py:826` hit_test
  又用 `col = max(0, min(x - rect.x, rect.width - 1))` 自行 clamp。两条 clamp 规则并存不同层。

### 6. Ownership 表多重存储
- `viewport.py:87` _row_blocks；`viewport.py:207-220` 复制进 ScreenLayout.row_blocks；
  `viewport.py:310-322` Viewport.row_blocks 属性再复制一份（仅测试消费）。
- `frame.py:1113-1143` 又重排成 FrameTable(rows=...)。
- 产品消费者全部走 layout/frame table（core/selection.py:207-213、frame.py:1135）。

### 7. Compose 的 pass-through 特例与后续补丁
- `frame.py:1144-1153`：单 pane 且满屏且无 chrome 时 composed = layouts[0]（直接复用 viewport
  的 layout）；否则 ScreenLayout(rows=rows, viewport_rows=[])。
- 为保住特例，`with_pane_rows` 在 `frame.py:1271-1275` 用逐行 `is` 比较做第二层判断。
- `apply_overlays` 在 `frame.py:1231-1235` 循环中反复改写 `self._layout = layout`，把"运行中的
  layout"塞进对象状态供 with_pane_rows（1259）与 pane_layout 读取——隐式协议。

## S1 — 命名与边界不一致

8. 同一"处理事件"契约三种名字：TUI.read_key（app.py:729 async）、handle_key（widgets/input.py:120、
   editor.py:140、textbuf.py:108、chat/slash.py:107——slash 还是三态返回）、handle（selection.py:184、
   chrome.py:267,781）。同一 bool=consumed 语义三层不同动词。
9. seal vs freeze：Block.seal（core/block.py:84）与 docstring "frozen"（block.py:35）混用；
   chrome.py:525 "window freezes the content"；chat/transcript.py:32-35 "seal freezes"。
10. 注册/挂载动词分裂：Composer.attach（composer.py:182）、TUI.add_band vs Frame.set_band
    （frame.py:973）、Frame.add_overlay、Pane.add_chrome、keymap 用 "bind"。卸载也有
    detach/remove_*/close 多种。
11. "region" 一名三义：Frame.region(pane_id)->Rect（1066-1075）、Frame._regions()->tuple（1162-1167）、
    Frame._region_order（912）；派生 TUI.viewport_region 返回 tuple[int,int] 而非 Rect（app.py:516-536）。
12. selection_pane 公私有类型不一致：公开返回 Pane|None（app.py:652-667），私有存 str|None（app.py:325）。
13. focus 一族五个名字：Pane.focus()（frame.py:672）、Frame.focus(pane|str)（1027）、TUI.focus_at(x,y)
    （493）、focused_pane 属性（1013）、focus_policy 回调（311）。
14. TUI.print 覆盖内建名（app.py:391-398），与其兄弟 add/remove/get 命名风格也不一致。
15. 私有成员被外部消费：chrome.py:751,823、selection.py:248 调 tui._clock()；
    tests/test_chrome_toasts.py:246,432 读 tui._frame.overlays（公开 TUI.frame 已存在）；
    tests/test_app.py:467-612 把 tui._clock、tui._tick 当正式依赖。
16. focus_policy 的 Optional 类型与实际不符（app.py:289-290 vs 311-313），read_key 的
    `if self.focus_policy is not None:`（769）永远为真。
17. 联合类型冗余：Key|Paste|MouseEvent 反复出现（MouseEvent 是 Key 子类，events.py:51）；
    _BUTTONS = ("left","middle","right")（app.py:73）与 MouseEvent.button: int 编码并存。

## S2 — 重复逻辑（可合并）

18. TUI.get / remove 的 primary+band 搜索循环逐字重复（app.py:368-373 与 382-389）。
19. 两套"按权重切矩形"算法：frame.py:180-195 _spans + split_rect（198-228）与 frame.py:231-250
    _ratio_sizes + Split.rects（356-379），余数策略相反（前者丢弃、后者补给最后一个）。
20. 同一 chrome 协商跑两遍：compose 已算 _negotiate（1120），Pane.band()（452-466）每次重跑。
21. _ResolvedRange 内三处重复：core/selection.py:81 与 143 建同样的 dict；holds（148-151）重复
    row_range（161-163）的包含判断；__init__（127-128）裸索引。
22. 空格行构造两条路：Line.pad_to（lines.py:188-193）与 Line.filled（195-206）。
23. 三个列索引 API 同一实现：index_at_column（text.py:187-204）、index_pair_at_columns（207-216）
    都是 index_bounds_at_columns 的薄包装；产品只调后者。
24. 常量与函数双重出口：ansi.py:33 CLEAR_LINE 与 ansi.py:36-38 clear_line() 同值；
    keys/console.py:33 直接拼 ESC 绕过 ansi 构造函数宣言。
25. refresh_size 两个主人：TUI._paint_at（app.py:850）与 Painter.paint（painter.py:79）同帧两次采样。
26. _teardown 两分支重复 _paint_at 调用（app.py:990 与 994）。
27. Text.render 循环（text.py:504-508）在 chat/message.py:75-76、91-92 又各写一遍。
28. viewport 双重 staleness 防抖（viewport.py:129-133 与 245-250）。

## S3 — 死代码 / 测试专用暴露

| 符号 | 位置 | 证据 |
|---|---|---|
| Block.set_component | core/block.py:80-82 | src 无消费者；仅 test_block.py:55-58、test_painter.py:63,79 |
| Viewport.row_blocks 属性 | core/viewport.py:310-322 | 仅 test_viewport.py:159-164 |
| Viewport.total_rows / viewport_height | core/viewport.py:299-307 | 仅测试；chrome 读 layout.total_rows |
| Frame.pane_layouts | core/frame.py:1174-1182 | 仅 test_frame.py:491,503 |
| split_rect | core/frame.py:198-228 | 产品路径用 Split.rects |
| index_at_column | core/text.py:187-204 | 仅 test_core_text.py:409-420 |
| Text.theme | core/text.py:488,495-499 | 全仓无读取点，纯死字段 |
| ansi.clear_line() | core/ansi.py:36-38 | 与 CLEAR_LINE 双出口 |

轻度冗余：EveryHandle.__repr__（app.py:93-94）、_Every.handle 与 EveryHandle 一对一、
Frame.overlays 属性仅 chrome.py:776 一个产品消费者。

## S4 — API 不简洁（要点）

- TUI.__init__ 6 kwarg；Screen 协议 9 成员；Theme 约 20 字段。
- 复杂元组返回：viewport_region -> tuple[int,int]|None；_ResolvedRange.row_range 的 None 双义。
- 同一件事两种做法：TUI.paint() 手动帧 vs pump 自动帧；三条滚动入口；TUI.rows 纯转发 Painter.rows。
- 哨兵不一致：Style._prefix 用 ""（style.py:134,142-145——无样式每次重算 SGR）；Segment._width 用 -1。
- 错误契约不一致：set_selection(pane=None) 静默解析 vs 未知 pane 才 ValueError；Pane.remove_chrome
  未命中抛错（447-449）而 _strip_divider 未命中静默（287-288）。
- focus_policy 返回值被丢弃（app.py:770）。

## S5 — 职责混乱与依赖

- text ↔ lines 循环依赖：lines.py:30 顶层 import text；text.py:502 延迟 import lines（自认补丁）。
  Text 组件寄生在测量模块里（text.py:14-15 自述）。
- viewport 依赖表现层：core/viewport.py:25,30 为 MORE_BELOW 导入 style.MUTED（可接受，core 内部）。
- 主题通路断裂：app.py:233 _Separator._resolve 直接 DEFAULT_THEME；TUI 无 theme 参数。
- 历史包袱注释：app.py:365 "since W5"、435、frame.py:593 "not this wave"、330 "the W2 mechanism"、
  events.py:17、style.py:165 "W11 palette upgrade"、theme.py:74/103/127/131、widgets/layout.py:12。
- dispatch order 三份拷贝（app.py:39-44、frame.py:31-37、chrome.py 模块 docstring）。
- Frame 职责 7 件事：tiling/矩形代数/chrome 协商/合成器/ownership 表/overlay 注册表/focus。

## 附：补丁气味危险度排序

1. frame.py:524-529 _adopt 补丁 + app.py:595 tiling no-op（S0-2）
2. frame.py:1144-1153 pass-through + 1271-1275 身份比较 + apply_overlays 状态回写（S0-7）
3. app.py:853-856 绘制路径内清选择（S0-3）
4. viewport.py:171-173 bottom 区域优先抢占空间策略硬编码（行为保持，勿动语义）
5. viewport.py:201-202 MORE_BELOW 覆盖末行同时保留 ownership（两个表语义耦合）
6. text.py:177-183,219-320 ASCII fast-path 与 fit_text 修正环（wcwidth 差异补丁，行为保持）
7. style.py:142 `if not self._prefix` 哨兵缺陷（空样式每次重算）
8. app.py:314-316 三元嵌 and 的优先级技巧
9. block.py:110-115 _next_auto_id while 循环绕开显式 id 冲突
10. app.py:968-971 body_error 优先于 pump_error，pump 异常被静默丢弃

# Spec 测试重构 · 2026-10-21

> 启动：2026-10-21 03:10（UTC+8）；基线 `main` @ `966734d`；motui 1.1.8。
> 门禁基线（改前，2026-10-21 复核）：
> - `uv run pytest -q -p no:cacheprovider` = **2190 passed / 2 skipped**（12.50s）
> - `uv run python tools/golden.py --check` = **58 topics match**
> - `uv run python tools/framebench.py` = exit 0，render-hash `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`，replay 322 ms
> - `python -m motui < /dev/null` 与 `python -m motui --pages` = exit 0
>
> W4 收口后（2026-10-21）：`pytest` = **824 passed / 0 skipped / 0 failed（3.53s）**；
> golden **58 topics**；render-hash 仍 `f872...`；demo 两入口 exit 0；`src/**`、`tools/**` 零 diff。
>
> 协议：lead 在 `main` 写 spec / 共享测试层 / 契约；worker 在**仓库外 worktree**作业，分支从前一刻
> main 创建，每波一个分支、一个 handoff、一次 `--no-ff` 合并。worker 不 merge / push / tag / 碰主检出。
> spec 归 lead，worker 只写自己名下的 `handoff/W<N>-<agent>.md`。

## 用户指示（原文）

> 我现在需要你帮我整体重构所有测试，当前的测试存在很多问题，第一就是没有聚焦，什么乱七八糟的内容
> 都有测试，并且很多脆弱性测试，改代码就必须改测试代码的这种，完全没必要有这种测试，第二就是重复性
> 太高，需要整体精简一下，第三就是测试方法没有合并汇总，重复性很高的测试方法可以统一放在 testing
> 里面。测试不需要考虑向后兼容，该删的就直接删就行。我希望测试的内容精炼合理，架构清晰，该有的测试
> 要有，该删除的测试要删。

## 目标

把 2190 个用例的“实现镜像套件”重构成一套**行为契约套件**：

1. **聚焦**：只测用户/宿主能观察到的行为与公开契约；删掉文档、演示 IA、缓存机制、私有字段、
   迁移考古类测试。
2. **抗重构**：重构内部实现（缓存、字段名、拆分模块）不需要改测试；只有公开行为变化才改测试。
3. **去重**：同一行为只测一次；跨组件重复的模式收敛为参数化测试或共享 helper。
4. **清晰**：`tests/` 按层分目录；共享测试方法只有一个入口 `tests/testing/`；文件职责一眼可见。
5. **该有的要有**：每个公开组件至少一个行为测试；核心算法、协议、错误路径、边界不变少。

目标规模：**500–800 个用例**，全量 < 8s；实际数字由覆盖审计决定，不为数字删有效测试。

## 非目标

- 不改 `src/motui/**` 的产品行为（本操作只动 `tests/**`；`src/motui/testing.py` 也保持三名字不变）。
- 不追求覆盖率百分比；没有覆盖率门禁，靠行为清单与 invariants 兜底。
- 不重写 `tools/golden.py` / `tools/framebench.py` / CI；它们仍是独立门禁。
- 不引入 pytest 插件、mock 框架或新依赖。
- 不改版本、不发版（W8 仍等用户指令）。

## 拍板决策

| # | 决策 | 取值 |
|---|---|---|
| T1 | 测试组织 | 按产品层分目录：`tests/kernel/`、`tests/keys/`、`tests/app/`、`tests/widgets/`、`tests/interaction/`；根目录只留 `test_api.py`、`test_packaging.py`、`test_invariants.py`、`test_smoke.py` |
| T2 | 共享测试方法 | **唯一入口** `tests/testing/`（`tests.testing` 包，`tests/__init__.py` + 各子目录 `__init__.py`）。`tests/_doubles.py` 删除；禁止在测试文件里重复定义 `key/press/motion/texts/Rows/many/Clock` |
| T3 | 公开测试面 | `src/motui/testing.py` 保持 `ScriptedEvents` / `headless_tui` / `snapshot` 三名字不变；`tests/testing` 重新导出它们，测试一律从 `tests.testing` 导入 |
| T4 | 断言层级 | 只断言公开 API：构造、`render(width)` 的行数/文本/可见宽度/样式、`handle/click/move/activate` 的返回、`take_result()`、公开错误。**禁止**读 `obj._x`、`block.rows` 缓存命中、`revision()` 作为断言对象、`frames` 计数 |
| T5 | 精确字符串 | 只有“字节就是产品”的层（`ansi`/`screen`/`painter`/`keys.decoder`）允许断言精确转义序列；组件层断言语义（行数、包含文本、样式字段、宽度上界），每个行为只留一个代表性精确样例 |
| T6 | 重复模式 | “sealed block / revision 到达屏幕”“disabled/hover/focus band”“glyph 宽度”等跨组件重复模式：每种只留**一个参数化测试**，覆盖 2–4 个代表组件，不再逐组件复制 |
| T7 | 元测试 | 删除：docs claims、README 示例执行、demo IA/topic/protocol、pytest 内 golden、精确 `__all__` 名单、主题旧常量。保留：公开名单可解析且无私有泄漏（1 个）、版本/元数据一致（1–2 个）、demo 启动 smoke（1–2 个）、全组件渲染 invariants（1–3 个） |
| T8 | golden | `tests/test_golden_frames.py` 删除；`tools/golden.py --check` 继续在 CI 与门禁运行，作为唯一逐字节视觉门禁 |
| T9 | 时间 | 不 sleep；定时行为一律用 `tests.testing.Clock` 装到 `tui.clock` |
| T10 | 删除不替代 | 删掉的测试不补“等价物”；只有审计确认的公开行为缺口才补新测试 |
| T11 | 命名 | 测试名描述行为，不出现波次号、旧 API 名、迁移叙事（`the_old_page_model_is_gone` 一类全删） |
| T12 | 文件职责 | 一个组件族一个文件；`test_widgets_form.py` 与 `test_widgets_forms.py` 合并；`test_widgets_basics.py` 按 Tabs/Tree 拆开 |

## 删除判据（满足任一即删）

1. **文档镜像**：断言 README/COMPONENTS/DESIGN/CONTRACT 的措辞、计数、链接、章节。
2. **迁移考古**：断言旧名字消失、旧模型不在、stale name 不出现。
3. **实现镜像**：断言缓存命中、revision 生效、重复 render 走哪条路径、组件内部计数器。
4. **逐字节全屏**：除了视觉门禁（golden 工具）以外，用完整帧字符串锁布局的测试；只保留字节即产品的层。
5. **重复路径**：同一行为已有更强/更直接的测试；或同一断言在不同组件上重复 N 次且无组件特有语义。
6. **自测 helper**：测试 `ScriptedEvents`/`Rows`/`RecordingScreen` 自身的行为（保留 1 个 smoke）。
7. **常量清单**：精确 pin `__all__` 的 34/40/44 个名字、主题旧常量逐字段相等、glyph 全表逐字节。
8. **平台无关的伪测试**：不触发任何产品代码、只验证 Python 语义的测试。

## 保留判据（必须至少有一个）

- 每个公开 widget 类的**核心动作**：构造 + `render` + 一个交互动词 + 结果语义。
- 核心算法：文本测量/换行/裁剪、行拼接、样式合并、diff hunk、decoder 状态机、viewport/frame 布局。
- 公开协议与错误：`take_result` 一次性、越界 `None`、重复 id 报错、disabled 拒绝、只读拒绝。
- 驱动生命周期：`run/run_async/read_event/exit`、pane/dock/hit、selection overlay。
- 交互层：focus 循环/trap、pointer hover/click、gesture 拖选、modal 栈、overlay 绘制、find/palette。
- 编码字节：ANSI 序列、OSC52、屏幕 enter/leave、painter 行 diff。
- 边界：width 0/1、宽字符、组合 emoji、空文档、空组件、负坐标。

## 目标目录

```
tests/
  __init__.py
  conftest.py                 # 把仓库根放进 sys.path，无隐藏 fixture
  testing/                    # 唯一共享测试方法入口
    __init__.py               # 重新导出下面所有名字 + motui.testing 三名字
    clock.py                  # Clock
    doubles.py                # Rows / RecordingScreen / many
    events.py                 # key / press / release / motion / wheel / paste / resize
    layout.py                 # texts / rows / marked
  kernel/
    test_ansi.py  test_block.py  test_clipboard.py  test_cursor.py
    test_events.py  test_frame.py  test_glyphs.py  test_lines.py
    test_mark.py  test_painter.py  test_screen.py  test_selection.py
    test_style.py  test_text.py  test_theme.py  test_viewport.py
  keys/
    test_decoder.py  test_keymap.py  test_sources.py
  app/
    test_driver.py  test_hit.py  test_selection_overlay.py
  widgets/
    test_action.py  test_autocomplete.py  test_bands.py  test_choice.py
    test_combobox.py  test_containers.py  test_data.py  test_delegate.py
    test_dialog.py  test_diff.py  test_editing.py  test_form.py
    test_indicators.py  test_markdown.py  test_menubar.py  test_navigation.py
    test_rows.py  test_scroll.py  test_syntax.py
  interaction/
    test_commands.py  test_find.py  test_focus.py  test_gesture.py
    test_host.py  test_modal.py  test_overlays.py  test_palette.py
    test_pointer.py  test_scrollbar.py
  test_api.py                 # 公开面可解析 + 无私有泄漏（简化版）
  test_packaging.py           # 版本/元数据一致（1–2 个）
  test_invariants.py          # 全公开组件 × 边界宽度
  test_smoke.py               # demo 两入口 + render_topic 全集 smoke
```

## 波次、依赖与写范围

| 波次 | 内容 | 依赖 | 写范围 |
|---|---|---|---|
| **W0** | spec + `tests/testing/` 共享层 + `tests/__init__.py` + `tests/conftest.py` | 无 | `specs/<group>/**`、`tests/{__init__,conftest}.py`、`tests/testing/**`（lead 在 main 完成） |
| **W1** | kernel + keys 测试重写 | W0 | `tests/kernel/**`、`tests/keys/**`；删除旧 kernel/keys 测试文件 |
| **W2** | widgets 测试重写 | W0 | `tests/widgets/**`；删除旧 `tests/test_widgets_*.py`、`test_container_hit.py`、`test_glyph_vocabulary.py` |
| **W3** | app + interaction 测试重写 | W0 | `tests/app/**`、`tests/interaction/**`；删除旧 app/interaction/host/commands 测试文件 |
| **W4** | 契约/smoke/invariants + 旧 meta 测试删除 + 终验 | W1/W2/W3 | `tests/test_api.py`、`tests/test_packaging.py`、`tests/test_smoke.py`、`tests/test_invariants.py`；删除 demo/docs/readme/golden 旧测试（lead 完成） |

W1/W2/W3 可并行：写入范围文件级不相交，共享 `tests/testing` 只读。W4 在三个分支合并后由 lead 执行。

## 波次级门禁

每个 worker 在分支 HEAD 必须跑：

1. `C:\Users\shifu\Desktop\mocode-tui\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider <自己的目录>`：0 failed
2. 全量 `pytest -q -p no:cacheprovider`：0 failed（并行期允许旧文件仍在，但自己删除的文件必须已删）
3. `git diff --stat main...HEAD`：范围 = 工单写范围，无蠕变
4. `grep -R "\._[a-z]" tests/<自己的目录>`：0 处私有属性访问（`__all__`、`__name__` 等 dunder 除外）
5. `grep -R "sleep(" tests/<自己的目录>`：0 处
6. 用例数：自己目录的收集数落在工单给的目标区间；低于下限需在 handoff 解释

lead 合并后终验：

1. 全量 pytest 0 failed，记录新总数
2. `python tools/golden.py --check` 58 topics match（渲染字节不应变化）
3. `python tools/framebench.py` exit 0，render-hash 仍为 `f872...`
4. `python -m motui < /dev/null` / `--pages` exit 0
5. `python -c "import motui, motui.kernel, motui.keys, motui.widgets, motui.interaction"` 无环
6. `git diff --stat main...HEAD`：只动 tests/specs
7. 删除文件清单与目标目录逐一核对

## 共享文件所有者

| 文件 | 所有者 | 规则 |
|---|---|---|
| `tests/__init__.py`、`tests/conftest.py` | lead | worker 只读 |
| `tests/testing/**` | lead | worker 只读；需要新 helper 先写进 handoff，由 lead 合并后加 |
| `tests/kernel/**`、`tests/keys/**` | W1 | 其他波只读 |
| `tests/widgets/**` | W2 | 其他波只读 |
| `tests/app/**`、`tests/interaction/**` | W3 | 其他波只读 |
| `tests/test_api.py`、`test_packaging.py`、`test_smoke.py`、`test_invariants.py` | lead | worker 禁触 |
| `tests/golden/**`、`tools/**`、`src/**`、`pyproject.toml` | lead | 本操作零改动 |

## 全局不变量

1. 只改 `tests/**` 与 `specs/<group>/**`；`src/**`、`tools/**`、`pyproject.toml` 零 diff。
2. 测试只经公开 facade 导入：`motui`、`motui.kernel`、`motui.keys`、`motui.widgets`、`motui.interaction`、`motui.app`、`motui.testing`，以及这些模块文档化的子模块（如 `motui.kernel.lines`、`motui.widgets.textfield`）。禁止 `motui.*._private`。
3. 不在测试文件里复制 helper；一律 `from tests.testing import ...`。
4. 不 sleep；时间经 `Clock`。
5. 不 mock 产品对象（现有测试没有 mock，保持）；用真实 headless 组件与真实 driver。
6. 删除的测试不留在 git 历史之外：直接 `git rm`，不留 skip/xfail。
7. 渲染字节变化 = 0；golden 与 framebench 必须与基线一致。

## 状态

| 波次 | 状态 | 分支 | 合并 commit |
|---|---|---|---|
| W0 | ✅ 2026-10-21 | main | `00b7515` |
| W1 | ✅ 2026-10-21 | `tests-w1-kernel-keys` | 见 git log |
| W2 | ✅ 2026-10-21 | `tests-w2-widgets` | 见 git log |
| W3 | ✅ 2026-10-21 | `tests-w3-app-interaction` | 见 git log |
| W4 | ✅ 2026-10-21 | main | 见 git log |

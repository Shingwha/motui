# W6 handoff · 交互层解耦、Host、FocusManager 与 overlay 层

## A · 交付

分支 `w6-interaction`；实现 commit 按提交顺序：

| commit | 内容 |
|---|---|
| `09254bc` | kernel: Host seam / overlay layers / Separator 下移 |
| `4725493` | interaction: FocusManager、Host 类型、take_result、focus trap |
| `fc7fd5a` | demo: FocusManager 与 take_result 调用点同步 |
| `b6d5293` | tests: host/manager/layer/trap 覆盖 |
| `7e4bcd5` | docs: README、COMPONENTS、DESIGN 同步 |

`git diff --stat main...HEAD`（handoff 前）：38 files changed, 1400 insertions(+), 662 deletions(-)；
无 golden、`widgets/**`、`keys/**`、`docs/CONTRACT.md`、`pyproject.toml`、`uv.lock` 改动；
kernel 禁触文件（events/block/lines/viewport/painter/selection/theme/style/clipboard）未动。

新增/变更公开签名（本波范围）：

```python
motui.kernel.host: Host (runtime-checkable), Hit, RowRange, EveryHandle
motui.kernel facade: EveryHandle, Hit, Host, RowRange
motui.app.__all__ == ["TUI"]                    # 值类型不再从 app 导出
TUI.copy_to_clipboard(text); make_input(...); make_autocomplete(options, ...)
motui.FocusManager / motui.interaction.FocusManager（替换 FocusRing，无 alias）
  FocusManager(targets=(), *, wrap=True, on_change=None)
  targets/focused/add/remove/focus/focus_next/focus_previous/handle/click/push_trap/pop_trap
kernel.frame.LAYERS = (background,content,selection,chrome,overlay,modal,tooltip,toast)
Frame.add_overlay(overlay, *, layer="overlay")  # 未知 layer -> ValueError
kernel.chrome.Separator                          # 原 interaction.scrollbar._Separator
Modal(..., focus=None): take_result(); open/close 压/弹 trap; detach 关闭+清空+不吞事件
Palette(..., focus=None): take_result() 委托 Modal；删除公开 chosen
```

基线真实结果（Windows，HEAD 待提交 handoff）：

- `pytest -q -p no:cacheprovider`：**1926 passed, 2 skipped**（基线 1900 + 26 新增）。
- `golden.py --check`：`golden: 11 pages match`。
- `framebench.py`：render-hash `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`（未变）。
- demo：`< /dev/null` exit 0 / 70 行；`--pages` exit 0 / 792 行；验收 5 import exit 0。
- 验收 6：interaction 的 `from ..app|from ..widgets` **0 命中**；app.py 的 interaction 仅 docstring。

测试改动：`test_focus.py` 按新语义重写（构造不设焦点、add/remove/on_change、trap/嵌套、
非 Focusable 路由）；新增 `test_host.py`；`test_frame.py` 新增层序/未知 layer/裁剪；
`test_modal.py` 新增 take_result、detach、trap、双 modal 层序；`test_palette.py` 新增 focus 转发；
其余为 `FocusRing→FocusManager`、`chosen→take_result` 与显式 `focus_next()` 同步；
`test_api_root.py` 更新 kernel/app facade。

## B · 偏差、取舍与约束

- **验收 7 未达成（唯一失败项）**：`grep -rn "FocusRing" src tests README.md docs` 仍 6 命中——
  `kernel/block.py:102`、`widgets/{dialog,form,textfield}.py` 共 5 处 docstring，以及
  `docs/CONTRACT.md:168` 的历史陈述。这些文件在本波红线内**禁触**；均为纯 docstring，
  无代码/导出引用。需要 lead 授权 W7 或单独一次 docstring-only 清扫。
- `FocusManager` 去掉旧构造期 `TypeError`：契约允许非 Focusable 路由目标（Dialog），
  `_set_focused` 只给 Focusable 写 flag；构造与 `add` 都不写组件状态。
- `Host` 严格按工单签名（含 `make_input`/`make_autocomplete`/`copy_to_clipboard`）。运行期
  `Find` 仍读 `host.reveal`，gesture 读 `selection/selection_pane/document/scroll_keys`，
  `Stats` 读 `painter`——未写入冻结 protocol；无类型门禁，运行正确，但 Host 并非完整表面。
- demo 的 trap：dialog 的 `Modal` 传 `session.body.focus`；`Palette`/ComboBox 的 `Modal` 在
  build 期构造、新 body 尚不存在，故传 `None`（`Palette(focus=)` 已实现并有单测）。
- `Modal.detach()` 改为注销+关闭+清空，且是终态（之后 `open()` no-op、不吞事件）；
  旧测试中 detach 后 `is_open is True` 的断言已更新。
- `FocusManager.add` 不主动清新目标的 `focused=True`；下一次真正移动会重写全部 flag。wheel、pane focus、gesture 未动；demo 文案与 golden 未动。

## C · 关键位置与稳定区

- `kernel/host.py:29`（EveryHandle）、`:47`（RowRange）、`:57`（Hit）、`:88`（Host）。
- `kernel/chrome.py:39`（Separator）；`kernel/frame.py:59`（LAYERS）、`:1426`（add_overlay）、
  `:1469`（apply_overlays）、`:1509`（with_pane_rows 裁剪）。
- `interaction/focus.py:56`（FocusManager）、`:157`（add/remove）、`:300`（push/pop_trap）。
- `interaction/modal.py:181`（open）、`:205`（close）、`:218`（detach）、`:239`（take_result）。
- `interaction/palette.py:190`（构造）、`:203`（take_result）。
- `app.py:367`（copy_to_clipboard）、`:379`（make_input）、`:392`（make_autocomplete）、
  `:700`（split 用 kernel Separator）。
- 测试：`tests/test_host.py`、`tests/test_focus.py`、`tests/test_frame.py:1080`、
  `tests/test_modal.py:316`、`tests/test_palette.py:328`。
- 稳定区（未触碰）：`widgets/**`、`keys/**`、`tests/golden/**`、`docs/CONTRACT.md`、
  `pyproject.toml`、`uv.lock`、kernel 禁触文件。

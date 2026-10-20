# W2 · driver 生命周期、坐标与 pane/dock（占位，JIT）
> 状态：待 W1 合并后补全「前置上下文」与详细工单。依赖 W1。

## 目标

把 driver 的作用域、生命周期和坐标统一：`read_event`/`exit`/`refresh`；`run`/`run_async`/`run_session`
可重复运行且可中断；`hit`/`hit_leaf`/`pane_at` 一套坐标；document 操作有明确 pane 作用域；`dock` 取代
`band`；修 `hit_test` inner-rect、`viewport_rows` top-pin、空 band 幽灵行；pane id 永不复用。

## 范围（草稿）

`src/motui/app.py`、`kernel/frame.py`、`kernel/viewport.py`、`kernel/screen.py`、相关测试与事件文档。

## 验收（草稿）

- 全量 pytest + golden + framebench + 两条 demo 入口
- 同一 TUI 连续两次 `run_session`
- `exit()` 能从 `read_event()` 的等待中返回
- `hit(-1, y)`/`hit(x, -1)`/超出宽高返回 `None`
- 有左/右 chrome 时 `Hit.col` 相对 inner rect 正确
- split 子 pane 的 document 可通过 driver 访问
- `dock` 空内容不留行；top-pin 的 `visible_range` 正确

## 不做

W3 的值语义、W4 的组件契约、W6 的 Host 协议与 overlay layer（W2 只做 driver/frame 的可用修复）。

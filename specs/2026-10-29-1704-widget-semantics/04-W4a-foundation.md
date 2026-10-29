# W4a · Foundation（目标占位，前置上下文合并 W1–W3 后补全）

> 分支 `w2.1.2-w4a-foundation`。依赖 W1–W3 合并。

## 目标

在 `widgets/base.py` 落三个基类和 `Keymap` 描述符：
`ResultWidget`（`_pending`/`take`/sentinel）、`ActionWidget`
（`disabled`/`hint`/`activate`/`toggle`/`on_action`）、`CursorWidget`
（`index`/`selected`/`select`/`move`/`home`/`end` + 四个钩子）；把
`strip.py` 的 `Keymap` 移到基类，`Widget.__slots__` 增加 `_keymap` 并在
`Widget.__init__` 初始化实例副本；焦点层 `app/focus.py` 增加 `space` 激活回退。

## 范围

- 迁移 `action.py` 的 Button/Checkbox/Link 到 `ActionWidget`（首个消费者）。
- 迁移 `tests/widgets/test_base.py`、`test_action.py`、`test_contracts.py`；
  `tests/app/test_focus.py` 增加 space 回退用例。
- 其他组件本波只做“能编译/能跑”的最小适配（例如删除重复的 Keymap slot），
  不做状态/动词迁移（留给 W4b/W4c）。

## 验收

- 全量门禁 + semantic 全绿；`api.py --check` 差异报告给 lead。
- `tests/widgets/test_contracts.py` 扩成基类契约矩阵（构造、能力、状态、动词、
  keymap、结果 sentinel）。

## 依赖

W1–W3 合并、`ref/interfaces.md` 更新到现实。

# W6 · Demo 集成（目标占位，JIT 补全）

> 分支 `w2.1.2-w6-demo`。依赖 W5。

## 目标

- splash：用 `Stack`/`Align` 组合像素背景与字标，接入真 `Button`（开始/跳过），
  保持闪烁与相位逻辑。
- components：用 `Stack` 合成 modal 内容，替换手写合成。
- 场景 IA 与键位提示同步更新；semantic goldens 重录。

## 范围

`demo/sections/splash/`、`demo/sections/components.py`、相关 `tests/demo/`、
`tests/golden/semantic/splash.txt`、`components.txt`。

## 验收

- 全量门禁全绿；splash/components 的 golden 重录并在 handoff 说明变化。
- splash 交互（任意键进入、按钮）在 demo 测试中覆盖。

## 依赖

W5 合并、`ref/interfaces.md` 更新。

# W2-a · PixelCanvas widget + octant 探测（占位，W1-a 合并后补前置上下文再派工）
> 分支 `dm-w2a-pixel-canvas`（派工时定）；前置 W1-a；写入范围 `src/motui/widgets/`（新文件）、`src/motui/widgets/__init__.py` 导出、`tests/`（新文件 ≤4 条）

## 目标
`PixelCanvas(Widget)`：持有 `Raster` + 图元便捷方法 + decay/set/unset + 多层（填充层 half / 线条层 braille）组织，`render(Constraints) -> Surface` 调 `kernel.quantize`。marker 由构造参数定层组织；octant 档与终端探测（发探针字符测宽，或先做显式配置项——方案在派工单拍板）。消费方：demo Motion 节（W3-b）与未来任何像素场景；**widget 之外不得出现第二套量化调用姿势**。

## 范围
kernel 不改（若 W1-a 契约暴露缺陷，报告说明并给最小补丁建议，lead 拍板）；demo 不动；公共 API 面板纯增。

## 验收
全量门禁绿；widget 直测（headless 渲染逐字断言）；`tests/test_api.py` 绿；性能：76×24 帧经 widget 全流程 ≤12ms。

## 前置上下文
- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md`（kernel 像素核心节 = 你的全部依赖）→ `handoff/W1-a-core.md`（B 节：调用方用法示例可直接照抄成骨架）→ 本工单。
- 基线命令（开工先跑，贴真实输出）：`uv run pytest -q`（**1646 passed**）。
- 稳定区（勿重读）：`src/motui/kernel/pixel.py` 已验收——只消费其公开签名，发现缺陷时报告并给最小补丁建议，不擅自改。
- 已知约束/坑：
  - 新 worktree 先确认 `uv run python --version` 是 3.13.x（`.python-version` 已钉；涉 api 登记册时版本漂移会翻车，见 interfaces 环境陷阱）。
  - 纯增导出必须走登记流程：`tools/api.py --update` + `tests/kernel/test_kernel_imports.py` 的 EXPECTED 集合（widgets 导出登记在 `tests/widgets/` 或对应登记册——开工先 grep 既有 widget 导出是怎么被钉的，照做）。
  - `ruff format --check` 全仓 47 文件基线即不合格，红线只有 `ruff check`。
  - 性能红线：76×24 帧经 widget 全流程 ≤12ms（kernel 量化本体 3.6–7.9ms，你的开销预算 ~4ms）。

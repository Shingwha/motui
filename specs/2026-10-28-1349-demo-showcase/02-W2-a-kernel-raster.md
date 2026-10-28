# W2-a · kernel 抽取：Raster + quantize（占位，W1-a 合并后补前置上下文再派工）
> 分支 `dm-w2a-kernel-raster`（派工时定）；前置 W1-a；写入范围 `src/motui/kernel/`（新模块）、`src/motui/kernel/__init__.py`、导出面、`tests/`（新文件 ≤4 条）

## 目标
把 `examples/pixel.py` 定型的 `Raster`（色索引+热度）与 `quantize`（逐格色对 + 分层混合 marker）抽取为 kernel 纯值/纯函数，成为 PixelCanvas（W3-a）与 demo 的共同底座。契约来源：`handoff/W1-a-*.md` A 节的精确签名；风格对齐 kernel 既有纪律（frozen、零 I/O、确定性测试）。

## 范围
新增 kernel 模块（命名派工时定）；导出面纯增（核对 `tools/api-2.0.txt` 机制与 `tests/test_api.py`）；examples/pixel.py 是否切换到 kernel 实现由 W1-a handoff B 节结论定。

## 验收
全量 pytest/ruff 绿；新模块确定性测试直测（量化纯函数逐字断言）；公共 API 面板测试绿。

## 前置上下文
（W1-a 合并后由 lead 填写）

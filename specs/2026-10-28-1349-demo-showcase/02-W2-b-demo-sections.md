# W2-b · demo sections：Components 游乐场 + Layout 实操（占位，W1-b 合并后补前置上下文再派工）
> 分支 `dm-w2b-sections`（派工时定）；前置 W1-b；写入范围 `src/motui/demo/sections/**`、golden 重录、新测试 ≤4 条

## 目标
把占位节替换为真内容。**Components**：左真实控件（Input/Choice/按钮→toast/modal、Table 排序）+ 右同步代码片段，tabs 分组 inputs/data/overlays。**Layout**：split 键盘调宽、dock 挪位、双轴滚动代码、wide_table 溢出——examples 三故事的可玩合并。

## 范围
只动 W1-b 建立的 sections 骨架内对应文件；每节 150–350 行；确定性动画纪律同全局红线。

## 验收
全量门禁绿；golden 更新；两节 headless 可逐字重放；test_demo_scenes 仍零修改绿。

## 前置上下文
（W1-b 合并后由 lead 填写）

# W4c · Text / Field / Form / Dialog / Content 迁移（目标占位，JIT 补全）

> 分支 `w2.1.2-w4c-text-form`。依赖 W4a；可与 W4b 并行。

## 目标

`text.py`、`textfield.py`、`form.py`、`dialog.py`、`collapsible.py`、
`decor.py`、`indicators.py` 迁到新契约：`Dialog(body, title=...)`、
`Collapsible(body, title=...)`、`ProgressBar(value, maximum=...)`、
`Slider.take` 删除、Input/Editor 尾部顺序、pending 清除规则、`Form`/`Dialog`
的 `index`/`select`/`move` 统一。

## 范围

上述源文件 + `tests/widgets/test_text_widget.py`、`test_editing.py`、
`test_form.py`、`test_dialog.py`、`test_containers.py`、`test_indicators.py`
+ 新文件 `tests/widgets/test_contract_text_form.py`。
不写 `test_contracts.py`（W4a 独占）。

## 验收

- 全量门禁 + semantic 全绿（字符零变化）。
- 构造签名符合 `ref/interfaces.md` §2；`take` 返回符合 §5。
- `api.py --check` 差异报告给 lead。

## 依赖

W4a 合并、`ref/interfaces.md` 更新。

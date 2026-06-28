# Analysis

`analysis/` 提供可验证的静态分析与本地质量证据，不负责预测运行时影响。

## Inspect 相关真源

- `review_observation.py`：组装 exact Git comparison 与四类 change partitions。
- `review_kernel.py`：从仓库 manifest 做精确核心文件分类，给出最低 review depth。
- `python_file_inspector.py`：解析单个 Python 文件的 content hash、声明范围和直接 imports。
- `symbol_reference_service.py`：规范化 provider 的 definition/reference 正向证据并校验源码范围。

这些模块通过 `analysis.__init__` 暴露受控公共接口。它们不输出 risk score、
impacted modules、dead-code verdict、调用树或 DAG 扩散。

## 其他分析能力

- `coverage_service.py`：coverage 数据整合。
- `git_diff_summary.py`：Git diff 摘要。
- `local_review_report.py`：本地 review 报告读取。
- `pre_push_scope.py`、`pre_push_test_selector.py`：保守的 pre-push 范围与测试策略。
- `structure_service.py`、`change_scope_service.py`：非 inspect 路径的结构与变更辅助。

外部访问必须通过 `clients/`；CLI 渲染位于 `commands/`。

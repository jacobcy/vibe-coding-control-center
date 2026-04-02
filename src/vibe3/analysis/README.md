# Analysis

代码智能层，提供 symbol 分析、结构快照、变更范围评估和依赖 DAG。

## 职责

- 基于 Serena 的符号引用分析
- 代码结构快照与 diff
- 变更范围评估（pre-push scope）
- 依赖 DAG 构建
- 测试选择器（pre-push test selector）
- coverage 数据整合

## 关键组件

| 文件 | 职责 |
|------|------|
| serena_service.py | Serena 符号分析服务 |
| snapshot_service.py | 代码结构快照 |
| snapshot_diff.py | 快照差异比较 |
| structure_service.py | AST 结构分析 |
| dag_service.py | 依赖 DAG |
| change_scope_service.py | 变更影响范围 |
| pre_push_scope.py | Pre-push 范围评估 |
| pre_push_test_selector.py | 变更驱动的测试选择 |
| coverage_service.py | Coverage 数据 |
| command_analyzer.py | CLI 命令静态分析 |

## 依赖关系

- 依赖: clients (SerenaClient, GitClient), models (snapshot/inspection models)
- 被依赖: commands/inspect, services/check_service, prompts (context builder)

# Analysis

代码智能层，提供符号分析、结构快照、变更范围评估和依赖 DAG。

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| snapshot_service.py | 410 | 代码结构快照服务、快照创建与持久化 |
| serena_service.py | 344 | Serena 符号分析服务、引用查询 |
| snapshot_diff.py | 262 | 快照差异比较、StructureDiff 生成 |
| pre_push_test_selector.py | 223 | 变更驱动的测试选择器 |
| coverage_service.py | 217 | Coverage 数据整合、覆盖率分析 |
| dag_service.py | 210 | 依赖 DAG 构建、符号依赖图 |
| command_analyzer.py | 201 | CLI 命令静态分析、命令拓扑分析 |
| inspect_query_service.py | 178 | Inspect 查询服务、统一分析入口 |
| command_analyzer_helpers.py | 175 | Command analyzer 辅助函数 |
| structure_service.py | 174 | AST 结构分析、模块结构解析 |
| local_review_report.py | 165 | Local review 报告生成 |
| change_scope_service.py | 159 | 变更影响范围评估 |
| serena_file_analyzer.py | 150 | Serena 文件级分析、符号提取 |
| dead_code_rules.py | 138 | 死代码检测规则 |
| pre_push_scope.py | 123 | Pre-push 范围评估 |
| snapshot_diff_section.py | 103 | 快照差异片段构建（用于 review prompt） |
| inspect_output_adapter.py | 62 | Inspect 输出适配器、格式转换 |
| __init__.py | 0 | 空文件（无公共导出） |

**总计**: 18 文件，3294 行代码

## 架构说明

Analysis 模块采用服务层架构，提供代码智能相关的核心能力。

### 服务层（Service Layer）

#### 核心服务
- **serena_service.py**: Serena 符号分析服务，提供符号引用查询、定义查找
- **snapshot_service.py**: 代码结构快照服务，管理快照创建、持久化、baseline 管理
- **dag_service.py**: 依赖 DAG 服务，构建符号依赖图
- **structure_service.py**: AST 结构分析，解析模块结构

#### 变更分析服务
- **change_scope_service.py**: 变更影响范围评估，分析哪些符号受影响
- **pre_push_scope.py**: Pre-push 范围评估
- **pre_push_test_selector.py**: 基于变更选择需要运行的测试

#### 其他服务
- **coverage_service.py**: Coverage 数据整合
- **inspect_query_service.py**: Inspect 查询服务，统一分析入口
- **command_analyzer.py**: CLI 命令静态分析

### 辅助层（Helper Layer）
- **serena_file_analyzer.py**: Serena 文件级分析
- **command_analyzer_helpers.py**: Command analyzer 辅助函数
- **snapshot_diff_section.py**: 快照差异片段构建（用于 review prompt）
- **inspect_output_adapter.py**: Inspect 输出适配器
- **local_review_report.py**: Local review 报告生成
- **dead_code_rules.py**: 死代码检测规则

### 设计原则

`__init__.py` 为空，表示 analysis 模块**不提供公共 API**。所有导入应来自具体服务：

```python
# ✅ 推荐
from vibe3.analysis.snapshot_service import SnapshotService
from vibe3.analysis.dag_service import build_dag

# ❌ 不推荐
from vibe3.analysis import SnapshotService  # 无公共导出
```

## 内部依赖

```
analysis/
├── 独立服务层（无内部依赖）
│   ├── dag_service.py
│   ├── structure_service.py
│   ├── coverage_service.py
│   ├── change_scope_service.py
│   ├── pre_push_scope.py
│   ├── serena_file_analyzer.py
│   ├── command_analyzer_helpers.py
│   ├── dead_code_rules.py
│   ├── snapshot_diff_section.py
│   ├── inspect_output_adapter.py
│   └── local_review_report.py
├── 依赖内部服务层
│   ├── snapshot_service.py → dag_service, structure_service
│   ├── serena_service.py → serena_file_analyzer
│   ├── inspect_query_service.py → dag_service, change_scope_service, serena_service
│   ├── pre_push_test_selector.py → change_scope_service
│   └── command_analyzer.py → command_analyzer_helpers
└── 依赖模型层
    └── snapshot_diff.py → snapshot_service (SnapshotError)
```

**循环依赖检查**: ✅ 无循环依赖

**依赖链说明**:
- `snapshot_service` 依赖 `dag_service` 和 `structure_service`（独立服务）
- `inspect_query_service` 组合了 `dag_service`、`change_scope_service`、`serena_service`
- 辅助文件（helpers、adapters）被对应服务使用

## 外部依赖

- **clients/**: SerenaClient, GitClient
- **models/**: StructureSnapshot, StructureDiff, CallNode 等
- **utils/**: path_helpers, git_helpers

## 被依赖

- **commands/**: inspect 命令使用 inspect_query_service、snapshot_service
- **services/**: check_service 使用 change_scope_service
- **agents/**: review_prompt 使用 snapshot_diff_section
- **prompts/**: context_builder 使用分析结果

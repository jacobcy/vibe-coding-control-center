# Plan: 将 Agent Orchestrator 从 `services/` 迁移到 `agents/` 模块

## 背景与动机

当前 `src/vibe3/services/` 目录混合了两类完全不同的职责：

1. **通用业务服务**（应留在 services/）：`flow_service.py`、`pr_service.py`、`task_service.py` 等
2. **Agent 任务编排器**（应迁移）：`run_usecase.py`、`plan_usecase.py`、`review_usecase.py`、`codeagent_execution_service.py`、`codeagent_models.py`

后者本质上是高层次的 AI Agent 执行控制器，负责驱动 codeagent-wrapper 完成 LLM 交互任务，与通用业务逻辑混放会导致：

- 模块职责不清晰，新开发者难以判断哪里该放新文件
- `prompts/` 等核心层被迫从 `services/` 中导入 Agent 专属模型
- `services/` 目录体积持续膨胀，信噪比下降

## 目标

创建 `src/vibe3/agents/` 顶层模块，将所有 Agent Orchestrator 迁入，让 `services/` 回归"通用业务逻辑"定位。

## 文件迁移清单

| 旧路径 | 新路径 | 说明 |
|---|---|---|
| `services/codeagent_models.py` | `agents/models.py` | CodeagentCommand, CodeagentResult, ExecutionRole |
| `services/codeagent_execution_service.py` | `agents/runner.py` | 核心执行引擎（231 行） |
| `services/agent_execution_service.py` | `agents/session_service.py` | Session 管理（59 行） |
| `services/run_usecase.py` | `agents/run_agent.py` | Run 编排器 |
| `services/plan_usecase.py` | `agents/plan_agent.py` | Plan 编排器 |
| `services/review_usecase.py` | `agents/review_agent.py` | Review 编排器 |
| `services/review_runner.py` | `agents/review_runner.py` | subprocess 层（218 行） |
| `services/review_parser.py` | `agents/review_parser.py` | 结果解析 |
| `services/execution_pipeline.py` | `agents/pipeline.py` | 执行管线（190 行） |

## 留在 `services/` 的文件

以下文件**不移动**：

- `context_builder.py`、`plan_context_builder.py`、`run_context_builder.py` — 命令-to-prompt 适配层
- `flow_service.py`、`pr_service.py`、`task_service.py` 等通用业务服务
- `snapshot_service.py`、`snapshot_diff.py`、`dag_service.py` 等分析工具

## 调用方需更新的 import

| 文件 | 旧 import | 新 import |
|---|---|---|
| `commands/plan.py` | `services.codeagent_execution_service`, `services.plan_usecase` | `agents.runner`, `agents.plan_agent` |
| `commands/run.py` | `services.codeagent_execution_service`, `services.run_usecase` | `agents.runner`, `agents.run_agent` |
| `commands/review.py` | `services.codeagent_execution_service`, `services.review_usecase` | `agents.runner`, `agents.review_agent` |
| `commands/plan_helpers.py` | `services.codeagent_execution_service` | `agents.runner` |
| `orchestra/services/governance_service.py` | `services.run_usecase` | `agents.run_agent` |
| `prompts/builtin_providers.py` | `services.run_usecase` | `agents.run_agent` |
| `prompts/validation.py` | `services.run_usecase` | `agents.run_agent` |

## 执行步骤

1. 创建 `src/vibe3/agents/__init__.py`，定义公共导出
2. 按清单逐文件移动（`git mv`），更新内部 import
3. 更新所有调用方 import（见上表）
4. 更新所有相关测试文件的 import 路径
5. 全量回归测试（`uv run pytest`）
6. （可选）为旧路径添加 deprecation shim，保持向后兼容

## 验收标准

- `uv run pytest` 全量通过
- `src/vibe3/services/` 不再包含 `codeagent_*`、`*_usecase.py`、`review_runner.py`、`review_parser.py`、`execution_pipeline.py`
- `src/vibe3/agents/` 模块可独立导入，无循环依赖
- `prompts/` 内部不再从 `services/` 导入 Agent 相关模型

## 影响评估

- **风险等级**：中（纯 import 路径变更，无逻辑改动）
- **测试覆盖**：现有测试全部有效，只需更新 import 路径
- **向后兼容**：可通过 shim 保持，但非必须（内部代码库）


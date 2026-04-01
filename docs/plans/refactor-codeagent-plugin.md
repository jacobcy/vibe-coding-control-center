# Plan: codeagent-wrapper 插件化

**状态**: Ready
**Issue**: #394
**目标**: 将 codeagent-wrapper 从 services 层抽离，建立 AgentBackend Protocol，使 plan/run/review 不再硬绑定 codeagent 二进制

---

## 背景

现有耦合链：

```
commands/plan|run|review
  -> codeagent_execution_service  (resolve AgentOptions)
  -> execution_pipeline           (run_execution_pipeline)
  -> agent_execution_service      (execute_agent)
  -> review_runner                (run_review_agent)
                                    |
                         ~/.claude/bin/codeagent-wrapper  <- 硬编码二进制路径
```

问题：
- `review_runner.py` 硬绑定 codeagent 二进制路径
- `services/` 混合了业务逻辑（flow/pr/task）和 agent 编排器
- 无法在不修改核心代码的情况下接入其他 agent framework

目标态：
- `agents/` 模块独立承载所有 agent 编排逻辑
- `AgentBackend` Protocol 定义统一接口
- `CodeagentBackend` 实现 Protocol（封装现有 subprocess 逻辑）
- `execution_pipeline` 依赖抽象接口，不依赖 codeagent

---

## 新增文件结构

```
src/vibe3/agents/
  __init__.py          - 公共导出
  base.py              - AgentBackend Protocol + 公共类型
  pipeline.py          - run_execution_pipeline（从 services/ 迁移）
  runner.py            - CodeagentExecutionService（从 services/ 迁移）
  session_service.py   - load_session_id（从 services/ 迁移）
  models.py            - CodeagentCommand, CodeagentResult（从 services/ 迁移）
  backends/
    __init__.py
    codeagent.py       - CodeagentBackend 实现 AgentBackend Protocol
```

---

## 关键设计：AgentBackend Protocol

```python
# agents/base.py
from typing import Protocol
from vibe3.models.review_runner import AgentOptions, AgentResult

class AgentBackend(Protocol):
    """可替换的 agent 执行后端接口。"""

    def run(
        self,
        prompt: str,
        options: AgentOptions,
        task: str | None,
        dry_run: bool,
        session_id: str | None,
    ) -> AgentResult: ...
```

`AgentOptions` 和 `AgentResult` 保持不变（已足够抽象）。
`session_id` 作为通用的 "continuation token"，各 backend 自行解释。

---

## 实施步骤

每步独立 commit，可单步 revert。

### Step 1: 创建 `agents/` 模块骨架

- 新建 `src/vibe3/agents/__init__.py`
- 新建 `src/vibe3/agents/base.py`（定义 `AgentBackend` Protocol）
- 新建 `src/vibe3/agents/backends/__init__.py`
- 验证：`from vibe3.agents.base import AgentBackend` 可正常导入

### Step 2: 提取 `CodeagentBackend`

- 新建 `src/vibe3/agents/backends/codeagent.py`
- 将 `services/review_runner.py::run_review_agent()` 的核心逻辑迁入 `CodeagentBackend.run()`
- 保留 `services/review_runner.py`，改为从 `agents/backends/codeagent` 导入并包装（向后兼容）
- 验证：现有测试 `test_review_runner.py` 全部通过

### Step 3: 迁移 `execution_pipeline`

- 新建 `src/vibe3/agents/pipeline.py`（内容从 `services/execution_pipeline.py` 迁移）
- `execute_agent()` 改为接受 `backend: AgentBackend` 参数（默认值 `CodeagentBackend()`）
- `services/execution_pipeline.py` 保留，改为 shim：从 `agents/pipeline` 再导出
- 验证：`test_execution_pipeline.py` 全部通过

### Step 4: 迁移 session_service

- 新建 `src/vibe3/agents/session_service.py`（内容从 `services/agent_execution_service.py`）
- `services/agent_execution_service.py` 改为 shim
- 验证：`test_agent_execution_service.py` 通过

### Step 5: 迁移 models

- 新建 `src/vibe3/agents/models.py`（内容从 `services/codeagent_models.py`）
- `services/codeagent_models.py` 改为 shim
- 验证：mypy 通过

### Step 6: 迁移编排器

- 新建 `src/vibe3/agents/runner.py`（内容从 `services/codeagent_execution_service.py`）
- 新建 `src/vibe3/agents/plan_agent.py`（内容从 `services/plan_usecase.py`）
- 新建 `src/vibe3/agents/run_agent.py`（内容从 `services/run_usecase.py`）
- 新建 `src/vibe3/agents/review_agent.py`（内容从 `services/review_usecase.py`）
- 新建 `src/vibe3/agents/review_runner.py`（内容从 `services/review_runner.py`）
- 新建 `src/vibe3/agents/review_parser.py`（内容从 `services/review_parser.py`）
- 所有旧 services 文件改为 shim
- 验证：全量 smoke 测试通过

### Step 7: 更新 commands 层 import

- `commands/plan.py`、`commands/run.py`、`commands/review.py`、`commands/plan_helpers.py`
  改为从 `vibe3.agents.*` 导入（不再绕道 services shim）
- `orchestra/services/governance_service.py`、`prompts/builtin_providers.py` 同步更新
- 验证：mypy + 全量测试通过

### Step 8: 删除 services shim 和原始文件

- 删除 `services/codeagent_execution_service.py`
- 删除 `services/codeagent_models.py`
- 删除 `services/agent_execution_service.py`
- 删除 `services/execution_pipeline.py`
- 删除 `services/review_runner.py`
- 删除 `services/review_parser.py`
- 删除 `services/plan_usecase.py`、`services/run_usecase.py`、`services/review_usecase.py`
- 同步删除对应测试文件或更新 import
- 验证：`uv run mypy src/vibe3`、smoke 测试全过

---

## 保留在 `services/` 不动的文件

- `flow_service.py`、`pr_service.py`、`task_service.py` — 业务服务
- `check_service.py`、`check_*.py` — 一致性检查
- `handoff_service.py`、`handoff_recorder_unified.py` — handoff 记录
- `snapshot_service.py`、`dag_service.py` — 代码分析工具
- `context_builder.py`、`*_context_builder.py` — prompt 上下文适配器（紧耦合 plan/run/review 业务）
- `label_service.py`、`signature_service.py` 等通用工具

---

## 调用方 import 更新表

| 文件 | 旧 import | 新 import |
|------|-----------|-----------|
| `commands/plan.py` | `services.codeagent_execution_service` | `agents.runner` |
| `commands/run.py` | `services.codeagent_execution_service` | `agents.runner` |
| `commands/review.py` | `services.codeagent_execution_service` | `agents.runner` |
| `commands/plan_helpers.py` | `services.codeagent_execution_service` | `agents.runner` |
| `orchestra/governance_service.py` | `services.run_usecase` | `agents.run_agent` |
| `prompts/builtin_providers.py` | `services.run_usecase` | `agents.run_agent` |

---

## 验收标准

- `uv run mypy src/vibe3` 零错误
- `uv run pytest` smoke 测试全过
- `src/vibe3/services/` 不再包含 `codeagent*`、`*_usecase.py`、`review_runner.py`、`review_parser.py`、`execution_pipeline.py`
- `src/vibe3/agents/` 可独立导入，无循环依赖
- `plan`/`run`/`review` 命令 dry-run 正常工作

---

## 风险评估

| 维度 | 评估 |
|------|------|
| 风险等级 | 低（纯结构重组 + 接口封装，无逻辑改动） |
| 影响范围 | `services/` 8 个文件 → `agents/` 8 个文件 + 1 个新文件 |
| 向后兼容 | Step 2-7 期间 shim 保持兼容；Step 8 清理 |
| 测试策略 | 每步 smoke 测试；shim 确保中间状态不破坏主干 |

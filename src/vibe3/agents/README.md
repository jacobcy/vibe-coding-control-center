# Agents

Agent backend 实现层，提供具体的 agent 执行能力和 prompt 构建。

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| backends/async_launcher.py | 402 | 异步 agent 启动器、执行管理 |
| backends/codeagent.py | 359 | Codeagent backend 实现 |
| review_prompt.py | 313 | Review prompt body / context builder |
| run_prompt.py | 252 | Run prompt body / context builder |
| plan_prompt.py | 250 | Plan prompt body / context builder |
| backends/codeagent_config.py | 246 | Codeagent 配置解析、环境准备 |
| models.py | 147 | AgentOptions / AgentResult / CodeagentCommand |
| backends/session_manager.py | 71 | Agent 会话管理、状态持久化 |
| base.py | 38 | AgentBackend 协议定义 |
| __init__.py | 76 | 公共导出：协议、模型、后端、prompt 构建器 |
| backends/__init__.py | 27 | 后端公共导出：CodeagentBackend、异步执行、配置解析 |

**总计**: 11 文件，2181 行代码

## 架构说明

### Backend 协议与实现

Agents 模块采用协议导向设计：

- **base.py**: 定义 `AgentBackend` 协议，规范 backend 必须实现的接口
- **backends/**: 提供具体 backend 实现（目前只有 codeagent）

### Prompt 构建器

三种 agent 对应不同的 prompt 构建策略：

- **plan_prompt.py**: Plan agent 的 prompt body 和 context builder
- **run_prompt.py**: Run agent 的 prompt body 和 context builder
- **review_prompt.py**: Review agent 的 prompt body 和 context builder

所有 prompt 构建器都依赖 `prompts/context_builder.py` 提供的上下文拼接能力。

### 设计意图

`__init__.py` 提供明确的公共 API，支持包级导入，同时保留深层路径导入的向后兼容：

```python
# ✅ 推荐 — 通过包级公共 API 导入
from vibe3.agents import (
    AgentBackend,
    CodeagentBackend,
    CodeagentCommand,
    CodeagentResult,
    make_plan_context_builder,
    make_run_context_builder,
    make_review_context_builder,
)

# ✅ 也可 — 通过子包导入
from vibe3.agents.backends import CodeagentBackend

# ⚠️ 可用但不再推荐 — 深层路径，保留向后兼容
from vibe3.agents.backends.codeagent import CodeagentBackend
```

## 内部依赖

```
agents/
├── 协议层（无依赖）
│   └── base.py (AgentBackend 协议)
├── Backend 实现层
│   ├── codeagent.py → async_launcher, codeagent_config, session_manager
│   ├── async_launcher.py (独立)
│   ├── codeagent_config.py (独立)
│   └── session_manager.py (独立)
├── Prompt 层（无内部依赖）
│   ├── plan_prompt.py (依赖 prompts/, config/, models/)
│   ├── run_prompt.py (依赖 prompts/, config/, models/)
│   └── review_prompt.py (依赖 prompts/, config/, models/, analysis/)
└── 数据模型层（无依赖）
    └── models.py (数据模型定义)
```

**循环依赖检查**: ✅ 无循环依赖

**依赖说明**:
- `codeagent.py` 是唯一有内部依赖的文件，组合了 async_launcher、codeagent_config、session_manager
- prompt 文件之间无相互依赖，各自独立使用 `prompts/context_builder`

## 外部依赖

- **models/**: AgentOptions, AgentResult, PlanRequest, ReviewRequest, PromptContextMode
- **prompts/**: PromptContextBuilder, PromptManifest
- **config/**: VibeConfig
- **analysis/**: build_snapshot_diff_section (review_prompt only)

## 被依赖

- **execution/**: 使用 CodeagentBackend (codeagent_runner, coordinator), CodeagentResult, ExecutionRole (noop_gate), sync_models_json (execution_role_policy), start_async_command (coordinator)
- **commands/**: 使用 plan_prompt, run_prompt, review_prompt
- **roles/**: 使用 agents.backends 执行 agent 任务
- **domain/handlers/**: 使用 ExecutionRole

## 公开 APIs

| 符号 | 类型 | 消费位置 |
|------|------|---------|
| **Protocols & Models** | | |
| AgentBackend | 协议 | execution/, agents/backends/ |
| CodeagentCommand | 数据模型 | execution/, agents/backends/ |
| CodeagentResult | 数据模型 | execution/, domain/handlers/ |
| ExecutionRole | 类型字面量 | execution/, domain/handlers/, roles/ |
| create_codeagent_command | 工厂函数 | roles/ |
| **Backends** | | |
| CodeagentBackend | 后端实现 | execution/ |
| start_async_command | 执行函数 | execution/ |
| sync_models_json | 配置同步 | execution/ |
| **Prompt Builders** | | |
| build_plan_prompt_body | 构建函数 | commands/ |
| make_plan_context_builder | 工厂函数 | commands/ |
| build_run_prompt_body | 构建函数 | commands/ |
| make_run_context_builder | 工厂函数 | commands/ |
| make_skill_context_builder | 工厂函数 | commands/ |
| make_publish_context_builder | 工厂函数 | commands/ |
| build_review_prompt_body | 构建函数 | commands/ |
| make_review_context_builder | 工厂函数 | commands/ |
| **Section Inspectors** | | |
| describe_plan_sections | 检查函数 | commands/, roles/ |
| describe_run_plan_sections | 检查函数 | commands/, roles/ |
| describe_review_sections | 检查函数 | commands/, roles/ |
| **Types** | | |
| RunPromptMode | 类型字面量 | agents/run_prompt |

## execution 层接口

execution 层是 agents 的主要消费者：

- **execution/codeagent_runner**: 导入 `CodeagentBackend`, `CodeagentCommand`, `CodeagentResult`
- **execution/coordinator**: 导入 `start_async_command`, `CodeagentBackend`
- **execution/execution_role_policy**: 导入 `sync_models_json`
- **execution/noop_gate**: 导入 `ExecutionRole`

agents 为 execution 层提供 agent 执行能力，是 execution → roles → commands 链路的执行提供者。

## 三层协作关系

```
runtime (事件循环驱动)
  └─ HeartbeatServer.on_tick()
       ├─ domain.OrchestrationFacade.on_tick() → 发布 domain events
       │    └─ execution.ExecutionCoordinator → 调度 agent 执行
       │         └─ agents.CodeagentBackend.run(prompt)
       │              └─ prompts.PromptAssembler.assemble() → 装配 prompt 上下文
       └─ runtime.execute_periodic_check() → 一致性检查 & 资源清理
```

agents 模块处于三层架构的中间层：
- **上层消费者**: execution 层通过 agents 执行 agent 任务
- **下层依赖**: agents 通过 prompts 模块构建 prompt 上下文
- **执行角色**: 为 roles → commands 链路提供具体的 agent 执行能力

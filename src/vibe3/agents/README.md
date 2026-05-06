# Agents

Agent backend 实现层，提供具体的 agent 执行能力和 prompt 构建。

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| backends/async_launcher.py | 402 | 异步 agent 启动器、执行管理 |
| backends/codeagent.py | 358 | Codeagent backend 实现 |
| review_prompt.py | 284 | Review prompt body / context builder |
| run_prompt.py | 250 | Run prompt body / context builder |
| plan_prompt.py | 245 | Plan prompt body / context builder |
| backends/codeagent_config.py | 236 | Codeagent 配置解析、环境准备 |
| models.py | 143 | AgentOptions / AgentResult / CodeagentCommand |
| backends/session_manager.py | 71 | Agent 会话管理、状态持久化 |
| review_pipeline_helpers.py | 66 | Review 分析辅助函数 |
| base.py | 38 | AgentBackend 协议定义 |
| __init__.py | 5 | 无公共导出（仅有文档说明） |
| backends/__init__.py | 0 | 空文件 |

**总计**: 12 文件，2098 行代码

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

`__init__.py` 为空，表示 agents 模块**不提供公共 API**。所有导入应来自具体模块：

```python
# ✅ 推荐
from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.agents.plan_prompt import PlanPromptBuilder

# ❌ 不推荐
from vibe3.agents import CodeagentBackend  # 无公共导出
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
└── 辅助层（无依赖）
    ├── models.py (数据模型定义)
    └── review_pipeline_helpers.py (辅助函数)
```

**循环依赖检查**: ✅ 无循环依赖

**依赖说明**:
- `codeagent.py` 是唯一有内部依赖的文件，组合了 async_launcher、codeagent_config、session_manager
- prompt 文件之间无相互依赖，各自独立使用 `prompts/context_builder`

## 外部依赖

- **models/**: AgentOptions, AgentResult, PlanRequest, ReviewRequest
- **prompts/**: PromptContextBuilder, PromptManifest
- **config/**: VibeConfig
- **execution/**: PromptContextMode
- **analysis/**: build_snapshot_diff_section (review_prompt only)

## 被依赖

- **commands/**: 使用 plan_prompt, run_prompt, review_prompt
- **roles/**: 使用 agents.backends 执行 agent 任务

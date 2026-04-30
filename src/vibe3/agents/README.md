# Agents

`agents/` 现在只保留与 agent backend 本身直接相关的能力，不再承担执行控制面。

## 当前职责

- 定义 backend 协议
- 提供具体 backend 实现
- 保留 prompt body / context builder
- 保留 review 辅助分析逻辑

## 关键组件

| 文件 | 职责 |
|------|------|
| `base.py` | Agent backend 协议 |
| `backends/codeagent.py` | Codeagent backend 实现 |
| `backends/codeagent_config.py` | backend 配置解析 |
| `models.py` | AgentOptions / AgentResult / CodeagentCommand |
| `plan_prompt.py` | plan prompt body / context builder |
| `run_prompt.py` | run prompt body / context builder |
| `review_prompt.py` | review prompt body / context builder |
| `review_pipeline_helpers.py` | review 分析辅助 |

## 不再属于 agents 的内容

以下能力已经迁出到统一架构层：

- 执行生命周期 → `src/vibe3/execution/`
- session 恢复 / actor 格式化 → `src/vibe3/execution/`
- sync / async 执行调度 → `src/vibe3/execution/`
- issue role request / gate / post-sync hook → `src/vibe3/roles/`

## 依赖关系

- `agents/` 依赖 `models/`、`prompts/` 等基础能力
- `execution/` 可以调用 backend
- `roles/` 可以调用 prompt builder / parser
- `agents/` 不再反向拥有 execution-era 框架职责

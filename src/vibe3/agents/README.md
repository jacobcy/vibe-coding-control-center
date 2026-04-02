# Agents

AI Agent 调用层，提供 plan/review/run 三条执行 pipeline 和可插拔 backend。

## 职责

- 定义 AgentBackend 协议（pluggable agent 接口）
- 实现 plan agent（生成实现计划）
- 实现 review agent（代码审查）
- 实现 run agent（通用任务执行）
- 管理 agent session 生命周期

## 关键组件

| 文件 | 职责 |
|------|------|
| base.py | AgentBackend 协议定义 |
| backends/ | 具体 backend 实现（CodeagentBackend） |
| pipeline.py | 执行 pipeline 抽象 |
| plan_agent.py | Plan 生成 agent |
| review_agent.py | Code review agent |
| run_agent.py | 通用执行 agent |
| runner.py | Agent 执行器（统一调度入口） |
| session_service.py | Session 持久化 |

## 依赖关系

- 依赖: models (AgentOptions/AgentResult), prompts (模板组装), clients (AI client)
- 被依赖: commands/run, commands/review, commands/plan, manager

# Orchestra Follow-up Issue Drafts

> 用途：把“本版不做但必须做”的能力拆成可执行 issue。
> 标签建议：`orchestra`, `enhancement`, `priority/medium`（按实际调整）。

## Draft 1: Orchestrator 决策循环（候选列表 + 优先级 + 依赖）

### Title
`feat(orchestra): add orchestrator decision loop for candidate queue and dependency-aware prioritization`

### Problem
当前 heartbeat 只具备最小兜底，缺少稳定的“候选列表 + 优先级 + 依赖决策”输出，难以支撑无人值守扩展。

### Scope
- 构建候选 issue 列表（assigned to manager）
- 计算优先级（label/规则）
- 依赖状态聚合（resolved/blocked）
- 形成决策输出（可追踪）

### Acceptance
- 可稳定输出“ready/blocked/candidate”列表
- 决策逻辑有测试覆盖
- 不引入新的共享真源

## Draft 2: Manager 多阶段编排（plan/run/review 子 agent）

### Title
`feat(orchestra): implement manager pipeline orchestration across plan/run/review subagents`

### Problem
当前 manager 以最小触发为主，缺少可恢复的多阶段编排，不满足完整无人值守流程需求。

### Scope
- manager pipeline：plan -> run -> review
- 子 agent 调用链编排
- 失败重试与中断恢复（最小可用）
- 与 flow/handoff 生命周期对齐

### Acceptance
- 同一个 flow 内能按阶段推进
- 阶段状态可追踪
- 失败后可重试并收敛

## Draft 3: Orchestra 可观测性与运行治理

### Title
`feat(orchestra): add observability for scheduler decisions and manager execution lifecycle`

### Problem
当前缺少统一可观测面，定位漏调度、重复调度和失败根因成本高。

### Scope
- 决策日志结构化
- 执行生命周期指标（触发、成功、失败、耗时）
- 最小状态面板/命令输出增强

### Acceptance
- 关键决策和执行可追踪
- 支持快速定位失败原因
- 文档覆盖排障流程

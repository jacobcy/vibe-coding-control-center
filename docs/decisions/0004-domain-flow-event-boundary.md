---
document_type: decision
title: DomainEvent 与 FlowEvent 分层边界及投影关系
adr_id: 0004
status: accepted
decides: "DomainEvent 是因果事件（runtime orchestration / dispatch），FlowEvent 是 flow-local 审计投影；二者单向投影，domain handler 不得重新承担 flow 状态机判断。"
scope:
  - src/vibe3/models/domain_events.py
  - src/vibe3/models/flow.py
  - src/vibe3/domain/**
  - src/vibe3/services/flow/event_projection.py
  - tests/vibe3/services/test_event_projection.py
  - docs/standards/v3/event-driven-standard.md
  - docs/standards/v3/database-schema-standard.md
date: 2026-06-12
supersedes: null
superseded_by: null
related_docs:
  - docs/standards/v3/event-driven-standard.md
  - docs/standards/v3/command-standard.md
  - docs/standards/v3/serve-debugging-guide.md
  - docs/standards/v3/database-schema-standard.md
issues:
  - 2745
  - 2746
  - 2747
  - 2748
  - 2749
---

# DomainEvent 与 FlowEvent 分层边界及投影关系

## Context

Vibe3 当前存在两类都被称为 event 的机制：

- `DomainEvent`：通过 runtime event bus 发布，由 domain handlers 消费，用于表达调度意图、运行时观察和业务状态变迁。
- `FlowEvent` / `flow_events`：写入 SQLite，用于呈现单个 flow 的本地 timeline/audit。

这两个机制的重叠点已经造成语义歧义：

- `flow blocked` 同时涉及 blocked state、flow timeline 和 `FlowBlocked` domain event。
- `serve status`、`flow show`、`task status` 的观察对象容易混淆。
- 如果把 `DomainEvent` 和 `FlowEvent` 当成同一套事件系统，domain handler 可能重新承担业务判断，形成第二套状态机。
- 如果完全隔离两套事件，又会导致同一业务事实无法在 flow timeline 中被稳定审计。

约束条件：

- `DomainEvent` 仍需服务 runtime orchestration，不应被 SQLite timeline 的展示结构限制。
- `FlowEvent` 仍需保持轻量、可读、可持久化，不应承载复杂调度语义。
- `task status` 是任务池聚合视图，不应变成 event log。
- blocked / failed / warning 等语义必须保持区分，避免状态、诊断、调度互相污染。

## Decision

保留两套 event，但明确它们处于不同层级：

- **DomainEvent 是因果事件**：表达 runtime observation、dispatch intent、业务状态变迁和 handler 驱动入口。
- **FlowEvent 是 flow-local audit projection**：表达单个 flow scene 中值得人类查看和追溯的时间线记录。

二者通过单向投影关系打通：

```yaml
DomainEvent -> Projection Rule -> FlowEvent
```

投影不是默认行为。只有对 flow scene 有审计价值的 `DomainEvent` 才应投影为 `FlowEvent`。不改变具体 flow scene 的 runtime/system events 应留在 serve/runtime observation 面。

观察入口按职责分离：

- `vibe3 serve status`：服务健康、event bus/handler、FailedGate、runtime errors、recent orchestration activity。
- `vibe3 flow show`：单个 flow 的状态、refs、handoff、timeline、blocked reason。
- `vibe3 task status`：issue/flow/orchestra/worktree 的任务池聚合状态。

`flow blocked` 的权威解释分三层：

- blocked state：flow 当前结果状态，写入 flow store / remote projection。
- flow timeline：人类审计记录，写入 `flow_events` 并由 `flow show` 展示。
- domain event：运行时因果信号，发布 `FlowBlocked` 供 handler / observation 消费。

关键权衡：

- 正向：不合并模型，避免 `FlowEvent` 被迫承载 runtime orchestration 语义。
- 正向：不完全隔离，避免重要业务事实无法进入 flow timeline。
- 正向：单向投影让因果链和审计链可测试、可演进。
- 代价：需要维护一份明确的投影规则表，防止事件新增后语义漂移。

## Consequences

正面影响：

- event 语义从“两个同名系统”收敛为“因果事件 + 审计投影”。
- `serve status` / `flow show` / `task status` 的职责边界清晰。
- `DomainEvent` handler 不应重新实现 flow 状态机，降低重复业务逻辑风险。
- blocked/failure/warning 可以沿各自观察面保留差异，不再被统一 timeline 名称抹平。

负面影响：

- 新增或修改 domain event 时，需要判断是否需要 flow projection。
- 当前已有写路径可能同时手写 timeline 与发布 domain event，需要逐步整理为明确契约。
- 文档和测试需要补足，否则边界会再次漂移。

风险：

- 如果投影规则过宽，`flow show` 会被 runtime 噪音污染。
- 如果投影规则过窄，关键 flow 事实会缺少审计证据。
- 如果 handler 继续承担状态判断，会回到第二套业务真源问题。

## How

**硬约束：本段只放链接，禁止复制实现细节。**

相关实现、标准与操作流程见：

- [docs/standards/v3/event-driven-standard.md](../standards/v3/event-driven-standard.md) — DomainEvent 发布、处理器和 runtime chain 标准
- [docs/standards/v3/command-standard.md](../standards/v3/command-standard.md) — `serve status` / `flow show` / `task status` 命令职责边界
- [docs/standards/v3/serve-debugging-guide.md](../standards/v3/serve-debugging-guide.md) — runtime observation 与真源交叉验证
- [docs/standards/v3/database-schema-standard.md](../standards/v3/database-schema-standard.md) — `flow_events` 持久化结构
- [src/vibe3/models/domain_events.py](../../src/vibe3/models/domain_events.py) — 当前 DomainEvent 模型定义
- [src/vibe3/models/flow.py](../../src/vibe3/models/flow.py) — 当前 FlowEvent 模型定义

---
document_type: decision
title: Protocol-based Dependency Injection
adr_id: 0002
status: accepted
decides: "services 层禁止直接依赖 agents 具体实现，必须通过 clients 层 Protocol（BackendProtocol）依赖注入；新增 backend 只许实现 Protocol。"
scope:
  - src/vibe3/clients/protocols.py
  - src/vibe3/services/**
  - src/vibe3/agents/backends/**
date: 2026-06-04
supersedes: null
superseded_by: null
related_docs:
  - docs/standards/v3/architecture-convergence-standard.md
  - src/vibe3/clients/protocols.py
issues:
  - 1884
---

# Protocol-based Dependency Injection

## Context

多个 service 直接 import `vibe3.agents.backends.codeagent.CodeagentBackend`，造成 services → agents 层级违规。具体包括：

- `CheckCleanupService` - 检查 tmux 会话状态
- `ExpiredResourceCleanupService` - 清理过期 tmux 会话
- `FlowCleanupService` - 终止 flow 相关的 tmux 会话
- `HandoffStatusService` - 查询活跃会话状态
- `TaskResumeOperations` - 恢复任务时检查会话状态

架构收敛标准要求：
- services → clients ✅（允许）
- services → agents ❌（禁止，违反依赖倒置原则）

问题本质：services 需要后端能力（tmux 会话管理），但不应依赖具体实现（CodeagentBackend）。

## Decision

引入 Protocol-based DI（依赖注入）：

1. **定义 Protocol**：在 clients 层定义 `BackendProtocol`（`src/vibe3/clients/protocols.py`）
   - 声明 services 需要的接口：`has_tmux_session()`, `run()`, `run_async()` 等
   - 不包含具体实现，只定义契约

2. **注入实现**：在 handler/orchestration 层注入具体实现
   - 服务初始化时接收 `backend: BackendProtocol` 参数
   - 具体实现 `CodeagentBackend` 保持在 agents 层不变

3. **依赖方向**：
   - services → clients（依赖 Protocol 抽象）✅
   - agents → clients（实现 Protocol）✅
   - handler/orchestration → agents（注入具体实现）✅
   - services ↛ agents（不再直接依赖）✅

核心权衡：
- ✅ 符合依赖倒置原则（DIP）
- ✅ services 可独立测试（mock Protocol）
- ✅ 新增 backend 只需实现 Protocol
- ❌ 增加间接层，注入复杂度上升

## Consequences

正面影响：
- services 不再直接依赖 agents，架构层级合规
- 服务可独立测试（注入 mock Protocol，无需真实 backend）
- 扩展性好：新增 backend 类型只需实现 Protocol，无需修改 services
- 代码更清晰：services 只关心"需要什么能力"，不关心"谁提供能力"

负面影响：
- 增加了间接层：服务初始化需要传递 backend 参数
- 注入链路增长：handler → service → sub-service 需要逐层传递

风险：
- 注入链路可能漏传（已通过类型检查和测试覆盖缓解）
- 新 contributor 需要理解 DI 模式（已通过文档和示例缓解）

## How

**硬约束：本段只放链接，禁止复制实现细节。**

相关实现和操作流程见：

- [src/vibe3/clients/protocols.py](../../src/vibe3/clients/protocols.py) — BackendProtocol 定义
- [docs/standards/v3/architecture-convergence-standard.md](../standards/v3/architecture-convergence-standard.md) — 架构收敛标准和层级规则
- [PR #2014](https://github.com/jacobcy/vibe-coding-control-center/pull/2014) — 重构实现：services 层 Protocol 注入
- [Issue #1884](https://github.com/jacobcy/vibe-coding-control-center/issues/1884) — 原始问题：services → agents 依赖解耦

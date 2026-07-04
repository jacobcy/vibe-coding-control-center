# Example: semantic-only candidate

> 场景：计划新增 `src/vibe3/services/observability/tracing.py`。路径是新的，不直接命中任何 ADR scope；但 issue 语义（“给 services 层加 backend 调用”）命中 ADR-0002 的决策对象（services 禁止直接依赖 agents）。semantic 单独命中即候选。

假设 issue：为 services 层增加 tracing，需要调用 backend 能力。

## ADR Consideration

**Stage**: plan
**Baseline**: branch=dev/issue-3310, commit=abc1234
**Accepted snapshot**: ADR-0001, ADR-0002, ADR-0003, ADR-0004
**Planned paths**:
- src/vibe3/services/observability/tracing.py (new file)

### Candidates
- ADR-0002 — trigger: semantic; evidence: issue 描述 services 层需调用 backend 能力，触及 “services 禁止直接依赖 agents、须经 Protocol DI” 的决策对象。planned path 未命中 scope（新文件；ADR-0002 scope 列既有 `clients/protocols.py`、`services/**`、`agents/backends/**`），但 semantic 单独命中即候选。

### Applicable constraints
- ADR-0002 — constraint: services 不得直接 import agents 具体实现，须经 `BackendProtocol` 注入; compliance: tracing service 将声明 `backend: BackendProtocol` 参数，由 handler/orchestration 注入，不 import `CodeagentBackend`。

### Dismissed candidates
- （无；ADR-0001/0003/0004 未进入候选集，按 FR-009 无需逐条 dismissal）

### Metadata flags
- none

### ADR change proposals
- none

### Open conflicts
- none

### Review reconciliation
（plan 阶段留空；review 阶段追加 actual diff 证据）

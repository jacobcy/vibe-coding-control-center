# Example: semantic-only candidate

> 场景：计划把一个 service-layer tracing capability 迁移到新的 `src/vibe3/use_cases/tracing.py`。该新目录尚未进入 ADR-0002 scope；但 issue 语义（“迁移后继续直接调用 backend”）命中 ADR-0002 的决策对象（service capability 禁止直接依赖 agents）。semantic 单独命中即候选。

假设 issue：把 tracing service 迁移到新的 use-cases 层，并继续调用 backend 能力。

## ADR Consideration

**Stage**: plan
**Baseline**: branch=dev/issue-3310, commit=abc1234
**Accepted snapshot**: ADR-0001, ADR-0002, ADR-0003, ADR-0004
**Planned paths**:
- src/vibe3/use_cases/tracing.py (new file)

### Candidates
- ADR-0002 — trigger: semantic; evidence: issue 描述迁移后的 service capability 仍需调用 backend，触及 “services 禁止直接依赖 agents、须经 Protocol DI” 的决策对象。planned path `src/vibe3/use_cases/tracing.py` 不命中 ADR-0002 的 `clients/protocols/**`、`services/**`、`agents/backends/**` scope，但 semantic 单独命中即候选。

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

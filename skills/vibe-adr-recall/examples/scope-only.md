# Example: scope-only candidate caught at review

> 场景：plan 阶段 planned paths 只声明了 service 文件，未触及 domain event；review 阶段 actual merge-base diff 实际改动了 `src/vibe3/models/domain_events.py`（命中 ADR-0004 scope）。review reconciliation 补上 ADR-0004 并评估实际改动。

## ADR Consideration

**Stage**: review (reconciliation appended)
**Baseline**: branch=dev/issue-3311, commit=def5678; review head=def5678, merge base=main@9abc
**Accepted snapshot**: ADR-0001, ADR-0002, ADR-0003, ADR-0004
**Planned paths**:
- src/vibe3/services/orchestra/refresh.py

### Candidates
- (plan stage) 基于 planned paths 未命中 ADR-0004 scope，无 domain-event 相关候选。

### Applicable constraints
- (plan stage) 无

### Dismissed candidates
- (plan stage) 无

### Metadata flags
- none

### ADR change proposals
- none

### Open conflicts
- ADR-0004 — review 阶段发现 actual diff 命中其 scope，但 plan artifact 未评估（见 reconciliation）。

### Review reconciliation
**Actual merge base/head**: 9abc...def5678
**Actual changed paths**:
- src/vibe3/services/orchestra/refresh.py
- src/vibe3/models/domain_events.py  ← 命中 ADR-0004 scope

**Changes from plan assessment**:
- 新增候选 ADR-0004（trigger: scope；actual diff 改动 `domain_events.py`）。
- 读取 ADR-0004 body：DomainEvent 是因果事件，FlowEvent 是审计投影，handler 不得重承担 flow 状态机。
- 实际改动为新增一条投影规则，未让 handler 重承担状态机 → compliant，但 plan artifact 缺该评估。

**Review conclusion**: blocking finding — scope-relevant accepted ADR（ADR-0004）在 plan artifact 中遗漏。要求 plan 补 ADR-0004 评估后再放行。未激活 FailedGate、未打 label；以 reviewer 正常 verdict/state 表达阻塞。

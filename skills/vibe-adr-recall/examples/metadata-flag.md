# Example: metadata-flag fallback candidate

> 场景：accepted snapshot 中存在一个 metadata 偏弱的 ADR（hypothetical ADR-0099，decides 措辞模糊、scope 全通配）。无法据 metadata 判定相关性 → 保守纳入候选并读 body，同时记 metadata flag。
>
> 注：本仓当前 accepted ADR（0001-0004）metadata 均完整，本例用 hypothetical ADR-0099 演示 conservative fallback 行为。

## ADR Consideration

**Stage**: plan
**Baseline**: branch=dev/issue-3313, commit=jkl3456
**Accepted snapshot**: ADR-0001, ADR-0002, ADR-0003, ADR-0004, ADR-0099 (hypothetical)
**Planned paths**:
- src/vibe3/execution/coordinator.py

### Candidates
- ADR-0099 — trigger: metadata-fallback; evidence: `decides` 缺乏 must / must not / only 或语义等价的绑定措辞，`scope` 为 `**` 通配，无法据 metadata 判定相关/不相关 → 保守纳入并读 body。
- （ADR-0001..0004 按 semantic/scope 正常判定）

### Applicable constraints
- (取决于读 body 后的判定)

### Dismissed candidates
- (取决于读 body 后的判定)

### Metadata flags
- ADR-0099 — field: decides; problem: 无绑定约束措辞（must / must not / only 或语义等价措辞缺失）; consequence: 无法据 metadata 判定相关性，已触发 metadata-fallback 候选。
- ADR-0099 — field: scope; problem: 全为 `**` 通配，无仓库相对路径; consequence: scope 信号失效，相关性判定降级为 semantic + body 阅读。

### ADR change proposals
- ADR-0099 metadata 应在后续 PR 补强（decides 绑定措辞 + 具体 scope）；本 plan 不在 scope 内自动修正。

### Open conflicts
- none

### Review reconciliation
（plan 阶段留空）

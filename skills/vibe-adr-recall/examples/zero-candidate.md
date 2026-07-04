# Example: zero candidates

> 场景：修正 README 拼写。扫描 accepted ADR 的 decides/scope，无任何 semantic/scope 命中。记录 scan 信号 + zero candidate，**不**为每个 ADR 编造 dismissal 段落（spec FR-009）。

## ADR Consideration

**Stage**: plan
**Baseline**: branch=dev/issue-3312, commit=ghi9012
**Accepted snapshot**: ADR-0001, ADR-0002, ADR-0003, ADR-0004
**Planned paths**:
- README.md

### Candidates
- none

### Applicable constraints
- none

### Dismissed candidates
- none（无候选进入集合，无需 dismissal reason）

### Metadata flags
- none

### ADR change proposals
- none

### Open conflicts
- none

### Review reconciliation
（plan 阶段留空）

### Scan evidence（zero-candidate 证据）
- 扫描 ADR-0001..0004 frontmatter：decides/scope 均完整。
- planned path `README.md` 不命中任何 ADR scope；issue 语义（文档拼写）不触及任何决策对象。
- 结论：zero candidates，无 exhaustive dismissal 列表。

# Contract: ADR Consideration Artifact

The artifact is embedded in the spec-kit plan.

```markdown
## ADR Consideration

**Stage**: plan
**Baseline**: branch=<branch>, commit=<sha>
**Accepted snapshot**: ADR-0001, ADR-0002, ...
**Planned paths**:
- <repo-relative path or glob>

### Candidates
- ADR-NNNN — trigger: semantic | scope | metadata-fallback; evidence: <signal>

### Applicable constraints
- ADR-NNNN — constraint: <binding rule>; compliance: <plan evidence>

### Dismissed candidates
- ADR-NNNN — reason: <specific reason after reading candidate body>

### Metadata flags
- none | <ADR, field, problem, consequence>

### Scan evidence
- <accepted metadata source and semantic/scope signals checked; required for zero-candidate results>

### ADR change proposals
- none | <RFC/ADR link or planned proposal, with carry/replace/retire disposition>

### Open conflicts
- none | <accepted constraint not yet resolved>

### Review reconciliation
**Actual merge base/head**: <sha>...<sha>
**Actual changed paths**: <paths>
**Changes from plan assessment**: <added/removed candidates and why>
**Review conclusion**: compliant | blocking finding <reference>
```

## Rules

- Plan stage uses planned paths and leaves review reconciliation empty.
- Review appends actual diff evidence.
- Only candidates require an applicable/dismissed decision.
- Every applicable constraint has compliance evidence or an open conflict.
- Proposed ADRs can appear in narrative context but not in `Accepted snapshot`.
- An unresolved accepted-ADR conflict prevents a passing review.
- A zero-candidate result records scan signals and metadata quality flags without exhaustive dismissal prose.

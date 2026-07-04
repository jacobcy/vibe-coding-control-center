# Implementation Plan: Low-Code ADR Recall

**Branch**: `dev/issue-3299` | **Date**: 2026-07-04 | **Spec**: [spec.md](./spec.md)

**Implementation issue**: [#3308](https://github.com/jacobcy/vibe-coding-control-center/issues/3308)

## Summary

Implement ADR recall as a project skill plus structured spec-kit plan/review prompts. The planner records intended paths and accepted constraints; the reviewer reconciles them against the actual diff. No Python/runtime service is introduced.

## Technical Context

**Language**: Markdown and YAML frontmatter
**Integration**: spec-kit plan template/workflow, project `vibe-*` skill distribution, supervisor plan/review policy
**Storage**: existing ADR Markdown and generated plan Markdown
**Verification**: fixture plans, deterministic metadata/path checks performed by the agent, and review scenarios
**Scale boundary**: agent-only until `accepted ADRs > 20` or measured errors exist in at least 10 reviewed plans

## Design

### 1. ADR metadata

Add `decides` and `scope` to `_template.md` and accepted ADR files. Read metadata from the ADR files; keep `INDEX.md` as an index and remove invalid placeholder accepted rows. Do not add a duplicated `decides` column.

### 2. Canonical recall skill

Create `skills/vibe-adr-recall/SKILL.md`. The skill:

1. captures branch/commit, issue/spec semantics, and planned paths;
2. discovers accepted ADR files from frontmatter;
3. forms candidates on semantic OR scope relevance;
4. flags missing/weak metadata conservatively;
5. reads candidate bodies;
6. writes the artifact defined in `contracts/artifact.md`.

### 3. spec-kit plan visibility

Add `ADR Consideration` to `.specify/templates/plan-template.md`. Update the spec-kit workflow's `review-plan` message to require artifact/conflict review. Update planner policy to invoke the canonical skill instead of a vague “read INDEX” instruction.

### 4. review constraint

Update reviewer policy and `skills/vibe-review-code/SKILL.md` to compare planned paths with the actual merge-base diff and current accepted ADRs. Violations produce normal findings/verdicts. The reviewer does not activate FailedGate or apply labels; unchanged state is handled by the existing no-op gate.

## File scope for the future implementation issue

- `docs/decisions/_template.md`
- `docs/decisions/0001-*.md` through current accepted ADRs
- `docs/decisions/INDEX.md`
- `skills/vibe-adr-recall/SKILL.md` (new)
- `.specify/templates/plan-template.md`
- `.specify/workflows/speckit/workflow.yml`
- `supervisor/policies/plan.md`
- `supervisor/policies/review.md`
- `skills/vibe-review-code/SKILL.md`

No file below `src/vibe3/` is in scope.

## Verification strategy

1. Happy path: planned path and semantic signal select an accepted ADR; plan states compliance.
2. Semantic-only path: new/renamed file has no scope hit but issue semantics select the ADR.
3. Scope-only path: actual review diff selects an ADR omitted at plan time; reviewer blocks until reconciled.
4. Proposed ADR: visible as optional context but not a constraint.
5. Zero candidates: artifact records scan and flags without exhaustive dismissals.
6. Supersede: proposal records carry/replace/retire for affected scopes.
7. Enforcement: an unresolved conflict yields a blocking review verdict and no state advancement; no FailedGate mutation occurs.

## Complexity tracking

No complexity exception is required. The implementation deliberately uses existing agent/spec-kit/review surfaces.

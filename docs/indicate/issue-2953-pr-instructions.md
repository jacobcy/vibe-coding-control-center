# PR Creation Instructions for Issue #2953

## Branch
- `task/issue-2953`
- Commit: `b76d83f13` - feat(governance): add decision layer for audit feedback loop

## PR Description
Title: `feat(governance): add decision layer for audit feedback loop (Fixes #2953)`

Body should include:
- **Summary**: Adds AuditDecision model, audit-decision.md governance material, and bounded-edit/gate contracts for the audit feedback loop (ADR-0005 layer 4)
- **Changes**: 8 files (4 new, 4 modified)
  - New: AuditDecision Pydantic model, governance material, 2 test files
  - Modified: __init__.py exports, governance routing, context builder, prompt-recipes.yaml
- **Key design decisions**:
  - `auto_apply=False` hard default (no auto prompt rewrite)
  - bounded_edit_scope/gate_conditions for structured follow-up issues
  - Evidence strength evaluation (strong/medium/weak/inconclusive)
- **Dependencies**: #2957 (Suggestion Ledger) — DONE; #2952 (Failure Clustering) — blocked-close, handled via evidence strength fallback
- **Related**: ADR-0005 (proposed — new layer implements final segment)

## Verification Checklist
- [ ] CI passes
- [ ] 33/33 tests pass
- [ ] No scope violations (verified by audit)
- [ ] Label as `state/merge-ready` (already set)

## Notes
- ADR-0005 is still 'proposed' — note in PR description
- This is the 8th material in governance.scan rotation
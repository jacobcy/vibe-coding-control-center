# Tasks: Low-Code ADR Recall

## Phase 1 - ADR metadata truth

- [ ] Add `decides` and `scope` guidance to `docs/decisions/_template.md`.
- [ ] Backfill those fields in each accepted ADR file.
- [ ] Remove invalid placeholder accepted rows from `docs/decisions/INDEX.md`; keep INDEX as discovery only.
- [ ] Verify ADR-0005 remains proposed and does not enter the accepted snapshot.

## Phase 2 - Canonical agent procedure

- [ ] Create `skills/vibe-adr-recall/SKILL.md` using `contracts/recall-checklist.md`.
- [ ] Verify the existing project init path exposes the `vibe-*` skill to supported runtimes.
- [ ] Add fixture examples for semantic-only, scope-only, zero-candidate, and metadata-flag cases.

## Phase 3 - spec-kit plan integration

- [ ] Add the artifact skeleton to `.specify/templates/plan-template.md`.
- [ ] Update `.specify/workflows/speckit/workflow.yml` `review-plan` message to check artifact completeness and open conflicts.
- [ ] Replace vague ADR-index wording in `supervisor/policies/plan.md` with the canonical skill invocation.

## Phase 4 - review constraint

- [ ] Add actual-diff reconciliation rules to `supervisor/policies/review.md`.
- [ ] Add the corresponding review step to `skills/vibe-review-code/SKILL.md`.
- [ ] State explicitly that reviewer verdict/state handling is used; FailedGate and automatic labeling are out of scope.

## Phase 5 - verification

- [ ] Run all seven quickstart scenarios.
- [ ] Confirm no `src/vibe3/` files changed.
- [ ] Confirm only accepted ADR files constrain the plan.
- [ ] Confirm the implementation documents the `>20 accepted ADRs` or `10 reviewed plans with measured errors` threshold.

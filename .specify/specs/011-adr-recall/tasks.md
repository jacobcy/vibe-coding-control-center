# Tasks: Low-Code ADR Recall

## Phase 1 - ADR metadata truth

- [x] Add `decides` and `scope` guidance to `docs/decisions/_template.md`.
- [x] Backfill those fields in each accepted ADR file.
- [x] Remove invalid placeholder accepted rows from `docs/decisions/INDEX.md`; keep INDEX as discovery only.
- [x] Verify ADR-0005 remains proposed and does not enter the accepted snapshot.

## Phase 2 - Canonical agent procedure

- [x] Create `skills/vibe-adr-recall/SKILL.md` using `contracts/recall-checklist.md`.
- [x] Verify the existing project init path exposes the `vibe-*` skill to supported runtimes.
- [x] Add fixture examples for semantic-only, scope-only, zero-candidate, and metadata-flag cases.

## Phase 3 - spec-kit plan integration

- [x] Add the artifact skeleton to `.specify/templates/plan-template.md`.
- [x] Update `.specify/workflows/speckit/workflow.yml` `review-plan` message to check artifact completeness and open conflicts.
- [x] Replace vague ADR-index wording in `supervisor/policies/plan.md` with the canonical skill invocation.

## Phase 4 - review constraint

- [x] Add actual-diff reconciliation rules to `supervisor/policies/review.md`.
- [x] Add the corresponding review step to `skills/vibe-review-code/SKILL.md`.
- [x] State explicitly that reviewer verdict/state handling is used; FailedGate and automatic labeling are out of scope.

## Phase 5 - verification

- [x] Run all seven quickstart scenarios.
- [x] Confirm no `src/vibe3/` files changed.
- [x] Confirm only accepted ADR files constrain the plan.
- [x] Confirm the implementation documents the `>20 accepted ADRs` or `10 reviewed plans with measured errors` threshold.

## Phase 6 - review follow-up

- [x] Correct accepted ADR metadata paths/scopes and loading-mode summary found during PR review.
- [x] Replace the invalid semantic-only fixture with a path that does not match ADR-0002 scope.
- [x] Align blocking/reconciliation policy and add zero-candidate scan evidence to the artifact schema.
- [x] Require planner material to consume a recorded spec and treat long-term memory as advisory evidence.
- [x] Record the runtime spec/handoff architecture gap in proposed ADR-0006, Spec 012, and follow-up issue #3310.

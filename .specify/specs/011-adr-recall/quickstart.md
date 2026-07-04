# Quickstart: ADR Recall Acceptance Scenarios

## 1. Plan-stage happy path

1. Use an issue that plans to modify `src/vibe3/domain/handlers/`.
2. Run `vibe-adr-recall` while generating the spec-kit plan.
3. Confirm the artifact records planned paths, accepted snapshot, and ADR-0004 as a candidate/applicable constraint.
4. Confirm no implementation diff is claimed at this stage.

## 2. Semantic-only candidate

1. Plan a new file whose path does not yet match an ADR scope.
2. State issue semantics that clearly affect the ADR's decision object.
3. Confirm semantic relevance alone includes the ADR candidate.

## 3. Proposed ADR is not a gate

1. Use ADR-0005 as context.
2. Confirm it is labeled proposed/context and excluded from `accepted_snapshot`.
3. Confirm review does not block solely for divergence from ADR-0005.

## 4. Review catches actual scope

1. Make the actual merge-base diff touch an accepted ADR's scope that was absent from planned paths.
2. Run repository review.
3. Confirm `review_reconciliation` adds the ADR and evaluates the actual change.
4. Leave an unresolved violation and confirm the verdict blocks progression without activating FailedGate.

## 5. Zero candidates

1. Use a trivial documentation correction unrelated to ADR decision objects/scopes.
2. Confirm the artifact records metadata sources and zero candidates.
3. Confirm it does not contain one dismissal paragraph per accepted ADR.

## 6. Supersede disposition

1. Propose replacing an accepted ADR.
2. List each affected predecessor scope as `carry`, `replace`, or `retire` with rationale.
3. Confirm no strict scope-superset assertion is required.

## 7. Low-code boundary

Verify the implementation diff contains no `src/vibe3/` change and no new database, scoring, embeddings, RAG, or CLI surface.

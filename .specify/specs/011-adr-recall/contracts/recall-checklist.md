# Contract: `vibe-adr-recall` Procedure

## Plan stage

1. Record branch, commit, issue/spec semantics, and planned repository-relative paths.
2. Discover ADR files under `docs/decisions/` and read frontmatter.
3. Build the accepted snapshot from files whose status is exactly `accepted`; ignore template and placeholder index rows.
4. For each accepted ADR, inspect `decides` and `scope` metadata.
5. Include a candidate when semantic relevance OR path-scope relevance is present. Missing/weak metadata includes the ADR conservatively and adds a flag.
6. Read candidate bodies only.
7. Resolve each candidate as applicable or dismissed with a concrete reason.
8. Record compliance, open conflicts, and any ADR change proposal.
9. Write the artifact into the generated plan before the spec-kit `review-plan` gate.

## Review stage

1. Compute/inspect the actual merge-base diff through existing review evidence tools.
2. Refresh the accepted ADR snapshot from the review baseline.
3. Re-run semantic/scope candidate selection against actual paths.
4. Compare review candidates and constraints with the plan artifact.
5. Append reconciliation evidence.
6. Produce a normal review finding and blocking verdict for unresolved accepted-ADR violations, missing artifact evidence, or unsupported dismissals.
7. Do not activate FailedGate, apply labels, or mutate flow state directly. Existing role output/state/no-op behavior remains authoritative.

## Complexity and failure behavior

- Metadata scanning is linear in ADR count.
- Full-body reads are limited to candidates.
- Missing/unreadable ADR metadata fails conservatively by flagging a candidate; it does not silently pass.
- Code-assisted retrieval is outside this procedure until the explicit scale/quality threshold is met and an RFC approves it.

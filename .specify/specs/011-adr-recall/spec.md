# Feature Specification: Low-Code ADR Recall

**Feature Branch**: `dev/issue-3299`
**Created**: 2026-07-03
**Corrected**: 2026-07-04
**Status**: Proposed Feature

**Implementation issue**: [#3308](https://github.com/jacobcy/vibe-coding-control-center/issues/3308)

## Problem

Plans currently contain only a general instruction to read relevant ADRs. That leaves relevance, evidence, and reviewability implicit. The feature makes ADR consideration a structured agent responsibility inside the existing spec-kit plan and repository review flow without adding runtime code.

## User Scenarios & Testing

### User Story 1 - ADR constraints are visible in the spec-kit plan (P1)

When spec-kit creates a non-trivial implementation plan, the planner runs the canonical `vibe-adr-recall` skill and fills a required `ADR Consideration` section. The section records the accepted ADR snapshot, planned paths, relevant candidates, applicable constraints, bounded dismissals, and unresolved conflicts.

**Acceptance scenarios**:

1. A plan that touches a cross-cutting decision includes the applicable accepted ADR and states how the plan complies.
2. A new-file plan uses intended repository-relative paths; it does not pretend an implementation diff already exists.
3. A plan with no candidates records the metadata/signals scanned and “no candidate” outcome; it does not manufacture one dismissal reason per unrelated ADR.
4. A proposed ADR may be listed as context but cannot block the plan as an accepted constraint.

### User Story 2 - Review reconciles intent with actual changes (P1)

During review, the reviewer compares the plan artifact with the actual merge-base diff and current accepted ADR set. Missing coverage, unsupported dismissal, stale scope metadata, or an unhandled conflict becomes an actionable finding.

**Acceptance scenarios**:

1. A scope-relevant accepted ADR omitted from the artifact causes a blocking review finding.
2. A plan path differs from the actual diff; the reviewer evaluates the actual changed path and updates the finding accordingly.
3. An intentional departure from an accepted ADR requires an ADR/RFC proposal with explicit carry/replace/retire disposition; silent departure blocks review.
4. Reviewer enforcement uses the normal verdict/state transition contract. If the reviewer does not advance the issue, the existing post-execution no-op gate supplies the block. FailedGate is not part of this path.

### User Story 3 - ADR metadata remains agent-readable (P2)

ADR authors maintain concise `decides` and `scope` frontmatter. The agent scans accepted ADR metadata linearly, then reads only candidate bodies. The goal is fewer full-body reads, not a false claim that total recall cost is sub-linear.

## Requirements

### Data and source of truth

- **FR-001**: `docs/decisions/*.md` frontmatter MUST be the source of `status`, `decides`, and `scope`; `INDEX.md` is a human discovery index and MUST NOT duplicate `decides` as a second truth source.
- **FR-002**: only ADR files with `status: accepted` MUST act as constraints. Placeholder index rows without ADR files and `proposed` ADRs MUST NOT enter the accepted snapshot.
- **FR-003**: accepted ADRs and the template MUST contain a concise `decides` statement and repository-relative `scope` patterns.

### Plan integration

- **FR-004**: the canonical procedure MUST be a project-owned skill at `skills/vibe-adr-recall/SKILL.md`; init/runtime adapters expose the `vibe-*` skill to supported agents.
- **FR-005**: `.specify/templates/plan-template.md` MUST include a required `ADR Consideration` section for non-trivial plans.
- **FR-006**: the plan-stage skill MUST use issue/spec semantics and **planned paths**. It MUST NOT use `vibe3 inspect base` as proof of future files before implementation.
- **FR-007**: an ADR becomes a candidate when semantic relevance **OR** scope relevance is present. Missing/low-quality metadata is handled conservatively as a candidate flag.
- **FR-008**: the artifact MUST contain baseline branch/commit, accepted snapshot, planned paths, candidates and trigger, applicable constraints/compliance, dismissed candidates with reasons, metadata flags, and ADR-change proposals.
- **FR-009**: dismissal reasons are required only for ADRs that entered the candidate set. A zero-candidate result records the scan signals and quality flags rather than explaining every unrelated ADR.

### Review integration

- **FR-010**: the spec-kit `review-plan` gate MUST ask the human/agent to verify that `ADR Consideration` is present and conflicts are resolved before task generation.
- **FR-011**: repository review policy and `vibe-review-code` MUST reconcile planned paths against the actual merge-base diff and current accepted ADR snapshot.
- **FR-012**: an unresolved accepted-ADR violation MUST produce a normal blocking review finding/verdict. Enforcement MUST NOT be described as a FailedGate input or as automatic `roadmap/rfc` labeling.
- **FR-013**: a replacement ADR MUST classify affected predecessor scopes as `carry`, `replace`, or `retire`; successor scope is not required to be a strict superset.

### Low-code boundary and threshold

- **FR-014**: the initial implementation MUST be Markdown/YAML, spec-kit template/workflow text, project skill, and review-policy text only. It MUST NOT add Python, a database, a score service, embeddings, RAG, or a `vibe3 adr` command.
- **FR-015**: code-assisted retrieval may be proposed only through a later RFC after either more than **20 accepted ADRs** exist or at least **10 reviewed plans** provide measured false-positive/false-negative evidence that the agent procedure is unreliable.

## ADR Consideration artifact

The normative schema is [contracts/artifact.md](./contracts/artifact.md). Plan time records intent; review time appends reconciliation evidence rather than rewriting history.

## Success Criteria

- **SC-001**: every non-trivial spec-kit plan contains the structured artifact before `review-plan` approval.
- **SC-002**: review checks actual changed paths and produces a blocking finding for an unresolved accepted-ADR conflict.
- **SC-003**: only accepted ADR files constrain delivery; proposed and placeholder index entries do not.
- **SC-004**: candidate ADR bodies are read selectively while metadata scanning remains explicit and linear.
- **SC-005**: the initial delivery contains no runtime code and names the measurable threshold for reconsidering that choice.

## Non-goals

- Automatic semantic scoring or retrieval.
- Automatic issue labels or direct flow mutation by the skill.
- Treating ADRs as replacements for feature specs, standards, or repository principles.

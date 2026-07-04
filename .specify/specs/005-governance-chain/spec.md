# Feature Specification: Governance Chain Baseline

**Feature Branch**: `dev/issue-3299`
**Created**: 2026-07-03
**Corrected**: 2026-07-04
**Status**: Baseline / Reverse Specification

## Purpose and truth sources

Governance behavior is distributed across `supervisor/governance/`, `supervisor/policies/`, project overlays under `.vibe/`, role/prompt composition code, and audit material files. ADR-0005 is currently **proposed**, so it is design context rather than an accepted baseline authority.

## User Scenarios & Testing

### Scenario 1 - Layered prompt material

Base governance/policy material is composed with project overlays and active rules. Provenance and dry-run support make the assembled sections inspectable. The exact active layers depend on the role and command path.

### Scenario 2 - Governance material rotation

Governance scans select material according to the configured catalog/rotation state. Roadmap intake, assignee pool, audit observation, audit suggestion, audit report, and audit decision are separate material responsibilities; not every scan runs every material.

### Scenario 3 - Audit evidence flow

The implemented audit chain contains raw/mechanical evidence, observations, suggestions, reports, and decisions in different files and models. ADR-0005 proposes the normalized four-layer relationship `raw evidence -> observation -> suggestion -> decision`; the current archive MUST NOT present `observation -> suggestion -> report -> decision` as an accepted architecture.

### Scenario 4 - Execution isolation

Governance/supervisor orchestration may use an asynchronous outer launch while individual child agent execution is synchronous within its allocated temporary worktree. Statements such as “governance is entirely synchronous,” “never uses a worktree,” or “cannot write” are not accurate global contracts.

## Requirements

- **FR-001**: prompt composition MUST preserve source provenance for active base and overlay sections where the current composition path supports it.
- **FR-002**: governance materials MUST retain distinct intake, pool, observation, suggestion, report, and decision responsibilities.
- **FR-003**: material rotation MUST be driven by the configured catalog/state rather than assuming a fixed all-material sequence each tick.
- **FR-004**: project overlays MUST extend the corresponding base layer without being described as a second independent truth system.
- **FR-005**: ADR-0005 MUST be labeled `proposed` in this baseline; its target model is not an implemented or accepted invariant.
- **FR-006**: current implementation MAY persist YAML/Markdown audit artifacts and create routed issues; `AuditLogger` is not the transport for this chain (see spec 009).
- **FR-007**: governance isolation MUST use the actual execution/worktree configuration of the path being described; no universal “no worktree/no write” claim is allowed.
- **FR-008**: prompt/policy improvement effectiveness is not yet a closed feedback loop and MUST remain linked to its RFCs.

## Key implementation PRs

| PR | Contribution |
|---|---|
| [#3156](https://github.com/jacobcy/vibe-coding-control-center/pull/3156) | Added the audit decision layer and decision-issue routing. |
| [#3130](https://github.com/jacobcy/vibe-coding-control-center/pull/3130) | Added YAML-ledger audit reporting. |
| [#3125](https://github.com/jacobcy/vibe-coding-control-center/pull/3125) | Added `AuditSuggestion` and suggestion material. |
| [#3103](https://github.com/jacobcy/vibe-coding-control-center/pull/3103) | Extended prompt-section annotation and dry-run composition to manager/scan/supervisor paths. |
| [#3291](https://github.com/jacobcy/vibe-coding-control-center/pull/3291) | Removed misleading dry-run conditional instructions from governance prompts. |

## Known gaps and tracking

| Gap | Coverage |
|---|---|
| Prompt/policy feedback needs an agreed evidence-driven improvement loop. | [#2946](https://github.com/jacobcy/vibe-coding-control-center/issues/2946) |
| Accepted changes need post-change effectiveness measurement and iteration. | [#2954](https://github.com/jacobcy/vibe-coding-control-center/issues/2954) |
| Roadmap-intake and assignee-pool material handoff/rotation has an open correctness bug. | [#3264](https://github.com/jacobcy/vibe-coding-control-center/issues/3264) |

## Success Criteria

- Proposed ADR content is separated from implemented baseline behavior.
- The evidence-chain vocabulary matches the real files and models.
- Execution mode and worktree claims reflect the actual outer/inner launch paths.

## Non-goals

- Accepting ADR-0005.
- Implementing the feedback-loop RFCs.
- Changing governance materials during this archive correction.

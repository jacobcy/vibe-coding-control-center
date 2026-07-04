# Feature Specification: Handoff Protocol Baseline

**Feature Branch**: `dev/issue-3299`
**Created**: 2026-07-03
**Corrected**: 2026-07-04
**Status**: Baseline / Reverse Specification

## Purpose and truth sources

This baseline covers `src/vibe3/services/handoff/`, handoff commands, flow-event persistence, and branch-scoped handoff files. It describes data ownership and resolution behavior; it does not claim operating-system permissions that the repository does not enforce.

## User Scenarios & Testing

### Scenario 1 - Record and read a role artifact

`HandoffService` records plan/run/review refs in flow state and adds explicit handoff/timeline events. Canonical kinds are `plan`, `run`, and `review`; legacy `report` and `audit` aliases normalize to `run` and `review`.

### Scenario 2 - Branch-scoped lightweight handoff

`HandoffStorage` maintains `.git/vibe3/handoff/<branch-safe>/current.md`. The file is a lightweight append-only collaboration surface. SQLite flow/event data is the authoritative runtime record; `current.md` explicitly says it is not a source of truth.

### Scenario 3 - Resolve a handoff target

Resolution supports `@vibe/<path>`, shared aliases such as `@current`/`@plan`/`@report`/`@audit`, repository-relative worktree paths, and absolute debug fallback paths. Branch and shared-directory validation prevent traversal outside intended namespaces.

### Scenario 4 - Repository policy versus filesystem enforcement

Agents are instructed to exchange shared state through handoff commands/artifacts. The Python repository does not install a general filesystem sandbox that prevents `cat` or direct reads. The baseline therefore records the handoff protocol as the supported coordination contract, not as an OS-enforced denial mechanism.

## Requirements

- **FR-001**: handoff event/ref history in SQLite MUST be treated as authoritative runtime state; `current.md` is a convenience projection.
- **FR-002**: canonical kind mappings MUST remain `plan -> plan_ref`, `run -> report_ref`, and `review -> audit_ref` with supported legacy aliases.
- **FR-003**: handoff queries MUST filter to explicit handoff/artifact/verdict event types rather than mixing all flow lifecycle events into the handoff view.
- **FR-004**: branch handoff files MUST live below the git common directory so linked worktrees share the same branch-scoped collaboration surface.
- **FR-005**: relative artifact refs MUST be validated against the resolved worktree root; accepted authoritative refs MUST not silently escape that root.
- **FR-006**: `@vibe/` references MUST resolve through the installation/runtime-material root with traversal validation.
- **FR-007**: the public handoff package contract MUST expose only its documented service/storage/resolution symbols; internal validators and event recorders remain internal.
- **FR-008**: this spec MUST NOT claim that direct filesystem access is technically denied. Enforcement is by agent policy and review unless a separate sandbox is introduced.

## Key implementation PRs

| PR | Contribution |
|---|---|
| [#3142](https://github.com/jacobcy/vibe-coding-control-center/pull/3142) | Corrected handoff status ordering and flow/bootstrap integration. |
| [#3129](https://github.com/jacobcy/vibe-coding-control-center/pull/3129) | Initialized handoff context during flow bootstrap. |
| [#3106](https://github.com/jacobcy/vibe-coding-control-center/pull/3106) | Unified installation-root detection used by handoff resolution. |
| [#2922](https://github.com/jacobcy/vibe-coding-control-center/pull/2922) | Standardized stable handoff aliases and publish exit behavior. |

## Known gaps and tracking

No code gap is opened for “deny direct filesystem access”: that statement was an inaccurate enforcement claim, not an implemented handoff feature. A future filesystem sandbox would require a separate direction decision rather than being smuggled into this baseline.

## Success Criteria

- Authoritative SQLite state and lightweight file projection are not reversed.
- Namespace/path behavior matches `resolution.py` and `storage.py`.
- Policy guidance is not presented as repository-enforced filesystem permissions.

## Non-goals

- Adding a filesystem sandbox.
- Changing handoff storage formats.
- Redesigning flow artifact refs.

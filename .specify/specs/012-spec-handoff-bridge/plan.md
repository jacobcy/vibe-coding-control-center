# Implementation Plan: Spec Artifact Handoff Bridge

**Branch**: `dev/issue-3312` | **Date**: 2026-07-06 | **Spec**: [spec.md](./spec.md)

**Implementation issue**: [#3312](https://github.com/jacobcy/vibe-coding-control-center/issues/3312)

## Summary

Deliver spec 012 P1 follow-ups without weakening existing compatibility:
missing file artifacts become non-destructive repair blockers, project-owned
spec-kit hooks publish through public Handoff commands, and `plan --spec` is a
read-only invocation override. Historical issue-valued `spec_ref` records remain
read-compatible; extension discovery and adapter behavior are verified through
their real command surfaces.

## Technical Context

**Language**: Python 3.12, Bash, Markdown, YAML
**Primary dependencies**: Typer, spec-kit `specify` CLI, existing Vibe services
**Storage**: existing SQLite flow state and spec-kit extension registry
**Testing**: `uv run pytest`, executable shell fixtures, Ruff, MyPy, `bash -n`
**Constraints**: no direct `.git/vibe3` writes; no external extension changes;
no automatic rebuild for a missing artifact; all Python commands use `uv run`

## Design

### Recovery compatibility

The consistency loop checks physical existence only for file artifacts. A
legacy issue-valued `spec_ref` remains readable and is not treated as a missing
file. New writes remain canonical file paths through `HandoffService.record_spec`.

### Read-only planning override

`resolve_spec_plan_input` accepts an explicit `spec_ref` override in addition to
an explicit file. The command passes `#<issue>` directly to that resolver, so
the selected issue enters the generated request without mutating flow state.

### Extension registration and adapter resolution

`.specify/extensions.yml` declares `vibe-spec-bridge` and its hooks. Because
spec-kit's runtime discovery uses the gitignored extension registry,
`scripts/init.sh` materializes a tracked local extension by copying it to a
temporary source and invoking `specify extension add --dev --force`. The adapter
handles an explicit artifact without requiring a spec directory; otherwise it
selects the lexicographically greatest spec directory, matching its documented
number/name ordering.

## Planned Paths

- `.specify/extensions.yml`
- `.specify/extensions/vibe-spec-bridge/**`
- `.specify/specs/012-spec-handoff-bridge/{plan.md,progress.yml,tasks.md}`
- `.gitignore`
- `config/v3/loc_limits.yaml`
- `scripts/init.sh`
- `src/vibe3/commands/plan.py`
- `src/vibe3/roles/plan.py`
- `src/vibe3/services/check/rule_checks.py`
- `src/vibe3/services/flow/consistency.py`
- `src/vibe3/services/flow/recovery.py`
- `src/vibe3/services/flow/write_mixin.py`
- `tests/vibe2/integration/test_install.bats`
- `tests/vibe3/commands/test_plan.py`
- `tests/vibe3/execution/test_noop_gate_artifact_boundary.py`
- `tests/vibe3/extensions/test_spec_kit_bridge.py`
- `tests/vibe3/orchestra/test_failed_gate_artifact_boundary.py`
- `tests/vibe3/roles/test_plan.py`
- `tests/vibe3/services/test_check_verify.py`
- `tests/vibe3/services/test_flow_consistency_check.py`
- `tests/vibe3/services/test_flow_recovery_service.py`

## Implementation Steps

1. Add failing consistency tests for legacy issue refs, then classify only
   file-valued refs through `check_ref_exists`.
2. Add failing planner tests proving the explicit issue body reaches
   `PlanRequest`, then extend `resolve_spec_plan_input` with a read-only ref.
3. Add failing real-shell adapter tests for deterministic directory selection
   and explicit artifact handling, then update the adapter.
4. Add failing extension discovery/init tests, then declare hooks in
   `.specify/extensions.yml` and teach `scripts/init.sh` to install tracked local
   extensions through spec-kit's supported `--dev` surface.
5. Run targeted tests, static checks, extension CLI probes, and re-review the
   original Blocking/Major findings.

## ADR Consideration

**Stage**: plan (backfilled during PR #3314 review)
**Baseline**: branch=`dev/issue-3312`, commit=`c97cb94c30bf755ad767b9113287eca74ae2d4d8`
**Accepted snapshot**: ADR-0001, ADR-0002, ADR-0003, ADR-0004
**Planned paths**: listed in `Planned Paths` above

### Candidates

- ADR-0002 — trigger: scope; `src/vibe3/services/**` includes the consistency change.

### Applicable constraints

- ADR-0002 — services must not depend on concrete agent backends; compliance:
  the change uses existing shared utilities and introduces no `services -> agents`
  import.

### Dismissed candidates

- none

### Metadata flags

- none

### Scan evidence

- Scanned frontmatter for accepted ADR-0001 through ADR-0004. ADR-0001,
  ADR-0003, and ADR-0004 have no semantic or scope match to the planned change.
  Proposed ADR-0006 informs the feature design but is not an accepted constraint.

### ADR change proposals

- none in this P1 fix; ADR-0006 acceptance remains Phase 7 work.

### Open conflicts

- none

### Review reconciliation

**Actual merge base/head**: `60753c4222b338cf7461f8294ed14b965bcd8cfa...c97cb94c30bf755ad767b9113287eca74ae2d4d8`, plus the reviewed corrective working-tree diff
**Actual changed paths**:
- `.gitignore`
- `.specify/extensions.yml`
- `.specify/extensions/vibe-spec-bridge/**`
- `.specify/specs/012-spec-handoff-bridge/{plan.md,progress.yml,tasks.md}`
- `config/v3/loc_limits.yaml`
- `scripts/init.sh`
- `src/vibe3/commands/plan.py`
- `src/vibe3/roles/plan.py`
- `src/vibe3/services/check/rule_checks.py`
- `src/vibe3/services/flow/{consistency.py,recovery.py,write_mixin.py}`
- `tests/vibe2/integration/test_install.bats`
- `tests/vibe3/commands/test_plan.py`
- `tests/vibe3/execution/test_noop_gate_artifact_boundary.py`
- `tests/vibe3/extensions/test_spec_kit_bridge.py`
- `tests/vibe3/orchestra/test_failed_gate_artifact_boundary.py`
- `tests/vibe3/roles/test_plan.py`
- `tests/vibe3/services/{test_check_verify.py,test_flow_consistency_check.py,test_flow_recovery_service.py}`
**Changes from plan assessment**: ADR-0002 remains the only accepted candidate;
the corrective diff adds no concrete backend dependency.
**Review conclusion**: compliant; the PR #3314 Blocking/Major findings were
resolved in the corrective working-tree diff and re-verified with 192 targeted
Python tests, 3 Bats tests, real spec-kit discovery, Ruff, Black, and MyPy.

## Verification Strategy

1. A healthy flow with `spec_ref=#3310` remains consistent.
2. `plan --spec #123` builds its request from issue 123 and leaves stored
   `spec_ref` untouched.
3. A clean project bootstrap registers `vibe-spec-bridge`; `specify extension
   info vibe-spec-bridge` succeeds and exposes all four hooks.
4. Explicit report/audit publication works without `.specify/specs/`; implicit
   spec/plan publication chooses the greatest spec directory by name.
5. Existing US2/US3/GP-1 targeted suites, Ruff, MyPy, Bash syntax, and diff
   whitespace checks pass.

## Complexity Tracking

No architecture or LOC exception is introduced. The implementation reuses
existing resolver, Handoff, and spec-kit extension surfaces.

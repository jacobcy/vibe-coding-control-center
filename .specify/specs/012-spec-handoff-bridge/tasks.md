# Tasks: Spec Artifact Handoff Bridge

**Input**: `spec.md` (012-spec-handoff-bridge), [ADR-0006](../../../docs/decisions/0006-spec-artifact-handoff-contract.md) (`proposed`), parent [issue #3310](https://github.com/jacobcy/vibe-coding-control-center/issues/3310), implementation [issue #3312](https://github.com/jacobcy/vibe-coding-control-center/issues/3312)

> **Plan provenance**: [`plan.md`](./plan.md) was backfilled during PR #3314 review from `spec.md`, ADR-0006, issue #3312, and this task decomposition. Its ADR Consideration records the accepted snapshot and actual-diff reconciliation. File paths and line anchors below originated at explored baseline `306ef3b4` and must be re-anchored against the implementation diff.

**Prerequisites**: spec.md ✓, ADR-0006 ✓ (proposed), plan.md ✓, constitution ✓ (`.specify/memory/constitution.md`)

**Tests**: This feature changes shared-state write/validation/recovery contracts — tests are **mandatory** (spec SC-006, constitution principle III). Every implementation task is `[TDD]`.

**Organization**: Tasks grouped by user story; each story independently testable per spec acceptance scenarios.

## Format: `[ID] [Markers] [Story] Description`

- **[P]**: parallel-safe (different files, no shared-state write conflict)
- **[TDD]**: RED-GREEN-REFACTOR (constitution principle III — mandatory in implement phase)
- **[REVIEW]**: pause for human code review before proceeding
- **[SUBAGENT]**: dispatchable to a parallel subagent
- **[Story]**: US1/US2/US3/US4 traceability to spec.md

## Global Constraints

Verbatim from spec.md / ADR-0006 / CLAUDE.md HARD RULES — every task inherits these:

- **G1** (write contract): an authoritative `spec_ref` write MUST store `unset` OR a repository-relative path matching `.specify/specs/<NNN-slug>/spec.md` (FR-001/002). Issue IDs, issue URLs, absolute paths, directories, missing files MUST be rejected **on write** (FR-002). Legacy `#nnn` values already in storage stay READ-compatible (T013a) — the read path is outside G1 scope.
- **G2**: Task issue identity stays in `task_issue_number` / issue link; MUST NOT be copied into `spec_ref` (FR-003).
- **G3**: Authoritative ref validation MUST run **before** any flow-state mutation and raise `UserError` on failure with **zero partial mutation** (FR-007/008).
- **G4**: Repeated publication of the same ref MUST be idempotent (FR-009/018).
- **G5**: Cross-module imports via public `__init__` API only; new symbols also added to `__all__` + `_LAZY_IMPORTS` (`.claude/rules/modularity-standards.md`).
- **G6**: `uv run` only — no `python`/`pip` (HARD RULE #10). Local targeted tests, full suite to CI (HARD RULE #14).
- **G7**: Adapters MUST NOT write `.git/vibe3` directly or redefine label/state transitions (FR-016). External spec-kit/superspec/Superpowers sources MUST NOT be modified (FR-014).
- **G8**: `dev/*` human workflow choice stays independent from `task/*` automated label lifecycle (FR-023).

---

## Phase 1: Setup (Baseline Confirmation & Migration Plan)

**Purpose**: Lock the explored baseline and decide the `spec_ref=#issue` migration stance before touching shared-state contracts.

- [x] T001 [P] [REVIEW] Confirm baseline anchors match explored snapshot
  - Verify `src/vibe3/services/handoff/service.py:31-35` (`_KIND_TO_REF_FIELD` lacks `spec`), `src/vibe3/services/shared/spec_ref.py` (`_try_parse_issue_number` accepts issue IDs), `src/vibe3/services/flow/consistency.py:81` (excludes `spec_ref`).
  - Output: a one-block comment in the migration note (T003) listing any drift vs. this file.
- [x] T002 [REVIEW] Audit current `spec_ref` population in shared state
  - Query `.git/vibe3/handoff.db` (read-only, via existing `vibe3` command surface — never raw DB access, HARD RULE #2) for flows with non-null `spec_ref`; classify how many hold issue IDs/URLs vs. file paths.
  - Output: counts feed T003 migration policy.
- [x] T003 [REVIEW] Decide `spec_ref=#issue` migration/cleanup policy (ADR-0006 Consequence)
  - **Decision (read-compat / write-strict, no batch migration)**: G1/FR-001/002 govern the **authoritative WRITE path only** — `record_spec` / `bind_spec` / `flow update --spec` MUST reject `#nnn`/URL/abs/dir/missing going forward. The **READ path keeps legacy compatibility**: a `#nnn` spec_ref resolves to issue body via existing `SpecRefService._resolve_issue_spec` (`gh issue view`), surfaced equivalently to `vibe3 task show #nnn`. The 181 historical `#nnn` rows stay as-is; no DB mutation. Issue identity continues to live in `task_issue_number` / `flow_issue_links`.
  - **Rationale**: spec-kit is recent; most historical flows have an issue body but no `.specify/specs/` file, so the issue body IS their de-facto spec. Batch-nulling would destroy that signal; read-compat preserves it while the write contract becomes canonical-only.
  - **Checkpoint gate**: human approved — proceed to Phase 2.

---

## Phase 2: Foundational (Unified Handoff Contract Core)

**Purpose**: Establish the shared write + validation contract that ALL four user stories depend on.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete and reviewed.

- [x] T010 [TDD] [REVIEW] Add `spec -> spec_ref` to canonical artifact mapping (FR-004)
  - Files: Modify `src/vibe3/services/handoff/service.py:31-35` — extend `_KIND_TO_REF_FIELD` and `_ACTIVE_KIND_TO_REF_FIELD` with `"spec": "spec_ref"`; add `spec` to whatever set gates `validate_authoritative_ref` (the `authoritative_kinds` caller).
  - Test: `tests/vibe3/services/test_handoff_service.py` — assert `spec` resolves through the same mapping as plan/run/review.
  - Done: added `"spec": "spec_ref"` to `_KIND_TO_REF_FIELD` (propagates to `_ACTIVE_KIND_TO_REF_FIELD`); added `spec` to `_AUTHORITATIVE_REF_KINDS`; added `handoff_spec` to `_HANDOFF_EVENT_TYPES` + `_SUCCESS_HANDOFF_EVENT_TYPES`. `_KIND_TO_ACTOR_FIELD` intentionally NOT extended — spec is an input artifact with no role actor.
- [x] T011 [TDD] [REVIEW] Implement `HandoffService.record_spec()` canonical writer (FR-005/007/008/009)
  - Files: Modify `src/vibe3/services/handoff/service.py` — mirror `record_plan()` (`service.py:365`) shape: `record_spec(spec_ref, actor, branch) -> Path`, delegating to `_record_ref` with ref_kind `spec`.
  - Interfaces: Consumes `_record_ref` (`service.py:254`); Produces `record_spec` for US1 command (T030) and `flow update --spec` delegation (T032).
  - Test: valid canonical path records + emits handoff event; invalid path raises `UserError` with **no** flow_state/event/actor mutation (assert mutation count = 0); repeat same ref is idempotent (no duplicate event).
  - Done: `record_spec` resolves worktree root, runs `validate_canonical_spec_path` (T012) BEFORE `_record_ref`, then delegates. Tests: happy-path (`spec_ref` + `handoff_spec` event), no-partial-mutation (validation precedes `_record_ref` → no row/event), idempotent re-record.
- [x] T012 [TDD] [REVIEW] Add canonical-path validation for spec ref (FR-001/002/007)
  - Files: `src/vibe3/services/handoff/validation.py` (extend) OR `src/vibe3/services/shared/spec_ref.py` (narrow). Enforce regex `^.specify/specs/[0-9]+-[a-z0-9-]+/spec\.md$` (repository-relative) **in addition to** existing `validate_authoritative_ref` checks (existence, regular-file, worktree containment, log/shared-store exclusion at `validation.py:43-57`).
  - Test matrix (each MUST raise `UserError` before mutation): issue number, issue URL, absolute path, directory, missing file, non-canonical path (e.g. `docs/foo.md`), `@spec` self-reference.
  - Done: new `validate_canonical_spec_path(ref_value, worktree_root)` in `validation.py` — regex + `is_file()` + worktree containment. Parametrized rejection matrix covers issue-id, bare number, URL, absolute, non-canonical, wrong filename, missing slug segment; plus missing-file and directory-at-spec.md cases. `@spec` self-reference rejected by the shared-store/containment arm of `validate_authoritative_ref` (exercised in US1 `handoff show @spec`).
- [x] T013 [TDD] [REVIEW] Restrict issue-id acceptance to the WRITE path only (FR-002/003, T003 decision)
  - Files: `src/vibe3/services/shared/spec_ref.py`. The WRITE surface (whatever `HandoffService.record_spec` / `FlowService.bind_spec` call to validate before mutation) MUST reject `#nnn`/URL/abs/dir/missing. **KEEP** `_try_parse_issue_number` / `_resolve_issue_spec` / `get_spec_content_for_prompt` (issue branch at `spec_ref.py:119-127`) intact — they ARE the read-compat layer; do not delete them.
  - Test: `tests/vibe3/services/test_spec_ref_service.py` — add cases that READ of `#3310` still returns issue body, while the write-validation helper rejects `#3310` with `UserError`.
  - Interfaces: feeds T012 (canonical-only write validation) and T013a (read fallback).
  - Done: write rejection lives in `record_spec` → `validate_canonical_spec_path` (T012); `#nnn` fails the canonical regex. Read-compat functions (`_try_parse_issue_number` / `_resolve_issue_spec` / `get_spec_content_for_prompt` issue branch) kept intact and locked by T013a regression. No `spec_ref.py` write-surface change was needed because the canonical validator is the single write gate.
- [x] T013a [TDD] [P] [SUBAGENT] Legacy `#nnn` read-compat regression (T003 decision)
  - Files: `src/vibe3/services/shared/spec_ref.py` + `src/vibe3/services/handoff/resolution.py:324-382` (`@spec` alias). Verify `@spec` on a `#nnn` spec_ref returns readable issue content (via the `get_spec_content_for_prompt` issue branch — equivalent to `vibe3 task show #nnn`).
  - Test: regression proving the 181 legacy rows still resolve to readable issue bodies after Phase 2 lands; assert NO data migration was performed on `flow_state.spec_ref`.
  - Done: `test_legacy_hash_ref_reads_as_issue_body` locks the `#nnn` → `parse_spec_ref` → `get_spec_content_for_prompt` → issue body chain. NO data migration performed (read-compat/ write-strict policy). The `@spec` alias end-to-end display path (`resolution.py`) builds on this same issue branch and gets its integration test in US1 (`handoff show @spec`, T030).
- [x] T014 [TDD] [P] [SUBAGENT] Export new symbols via public API (G5)
  - Files: `src/vibe3/services/handoff/__init__.py` — add `record_spec` (or the service method) to `__all__` + `_LAZY_IMPORTS`; `src/vibe3/services/shared/__init__.py` if spec_ref public surface changed.
  - Test: `uv run pytest tests/vibe3/test_modularity/ -v` stays green (no missing exports).
  - Done: `record_spec` is a method on the already-exported `HandoffService`; `validate_canonical_spec_path` is an internal helper (no public consumers). `tests/vibe3/test_modularity/` (51 tests) green — no `__all__`/`_LAZY_IMPORTS` change required.

**Checkpoint**: Foundation ready — spec is a first-class Handoff artifact with one validated, idempotent write path. User-story work may now begin (US1 first as MVP).

---

## Phase 3: User Story 1 — Publish Canonical Spec Artifact (Priority: P1) 🎯 MVP

**Goal**: An agent or spec-kit hook records a canonical `spec.md` through the same Handoff surface; `spec_ref` is repository-relative and `vibe3 handoff show @spec` resolves it.

**Independent Test** (spec US1): create a temp flow/worktree spec file, record via `handoff spec`, verify flow state + event history + display + `@spec` resolution.

### Tests for User Story 1 (write FIRST, watch them FAIL)

- [x] T030 [TDD] [US1] Contract test for `vibe3 handoff spec` writer in `tests/vibe3/commands/test_handoff_spec.py`
  - Covers spec acceptance scenarios 1 & 2: valid canonical records with event; all G1 invalid forms rejected pre-mutation.
  - Done: `tests/vibe3/commands/test_handoff_spec.py` — 2 tests (delegates-to-record_spec happy path + propagates UserError on `#3310`). GREEN, 7/7 with test_flow_update_spec.py.
- [x] T031 [TDD] [P] [US1] Delegation-equivalence test for `flow update --spec` in `tests/vibe3/commands/test_flow_manage.py`
  - Asserts `flow update --spec <canonical>` produces identical flow_state + event semantics as `handoff spec <canonical>` (spec US1 scenario 3, FR-006).
  - Done: landed in `tests/vibe3/commands/test_flow_update_spec.py` (same module as the legacy `--spec` tests it replaces). 3 new tests: `test_update_spec_delegates_to_canonical_writer` (record_spec called, bind_spec NOT), `test_update_spec_passes_path_unmodified` (no `.resolve()` — canonical rel-path forwarded as-is), `test_update_spec_propagates_validation_error` (UserError → exit 1). Observed RED (Exit at `Path.exists` check) → GREEN after T033. Dropped 3 obsolete tests that asserted the old `Path.exists/is_file/resolve` + `bind_spec` behavior.

### Implementation for User Story 1

- [x] T032 [TDD] [US1] Add `vibe3 handoff spec <path>` command (FR-005)
  - Files: Create `src/vibe3/commands/handoff_spec.py` (mirror `handoff_write.py:243` `plan` subcommand shape; < 50 lines per coding-standards Command layer). Register in `src/vibe3/commands/handoff.py` aggregator. Call `HandoffService.record_spec()` (T011) — never write `.git/vibe3` directly (G7).
  - Done (deviation, per HARD RULE #15 reuse-over-new): added `spec()` to the existing `src/vibe3/commands/handoff_write.py` (between `plan` and `report`) instead of a new `handoff_spec.py` file. It reuses the `_record_handoff_reference` helper with `method_name="record_spec"`, avoiding either duplicating the helper or a cross-module private import. Registered via `app.command()(spec)` in `register_write_commands`. Docstring states the ADR-0006 canonical-path contract + write-strict/read-compat policy.
- [x] T033 [TDD] [US1] Convert `flow update --spec` to delegate (FR-006)
  - Files: Modify `src/vibe3/commands/flow_manage.py:39,262-278` and `src/vibe3/services/flow/write_mixin.py:229-261` (`bind_spec`) — replace direct `flow_state.spec_ref = ...` write with a call into the same service operation T011 uses; preserve `spec_bound` event semantics.
  - Interfaces: Produces the unified writer consumed by both entry points.
  - Done (scoped): `flow_manage.py` `update()` non-empty `--spec` branch now calls `HandoffService().record_spec(spec, actor, branch=flow.branch)` (UserError → `typer.Exit(1)`), removing the local `Path.exists/is_file/resolve` checks + absolute-path conversion. `bind_spec` (write_mixin.py) is intentionally LEFT INTACT — it has 3 callers incl. `plan.py`'s read-compatible `#nnn`/absolute-path resolution (out of Phase 3 scope); routing `flow update --spec` directly to `record_spec` achieves FR-006's equivalent-semantics goal without touching the read-compat path. Added module-level `from vibe3.services.handoff import HandoffService` import (patch target for tests; verified no import cycle). Updated `SpecOption` help text to reflect canonical-path-only contract.
- [x] T034 [TDD] [P] [US1] Verify `@spec` resolution end-to-end (FR-004, already supported)
  - Files: `src/vibe3/services/handoff/resolution.py:279-318,324-382` already maps `@spec -> spec_ref`. Add a regression test proving `handoff spec` → `handoff show @spec` round-trips the exact file.
  - Done: added 2 regression tests in `tests/vibe3/services/test_handoff_resolution.py` mirroring the `@indicate` pattern — `test_resolve_handoff_target_at_spec_alias` (canonical spec_ref → resolves to exact file; locks FR-004 round-trip with the Phase 2 writer) and `test_resolve_handoff_target_at_spec_not_set` (unset spec_ref → FileNotFoundError, matching the post-T035 freshly-bootstrapped-flow state). Resolution code needed no change (`@spec` already wired at `resolution.py:280,376`). 20/20 resolution tests green.
- [x] T035 [TDD] [P] [US1] Remove bootstrap self-binding of task issue as `spec_ref` (issue acceptance criterion)
  - Files: Locate bootstrap/`vibe new` flow-creation path (per issue: "Bootstrap no longer self-binds the task issue as spec_ref"). If the explored baseline shows no self-bind, add a regression test asserting `spec_ref` stays unset after bootstrap; if it does self-bind, remove that write.
  - Done: root cause was `TaskService.link_issue(role="task")` at `src/vibe3/services/task/service.py:156-177` — it wrote `spec_ref=f"#{issue_number}"` + a `spec_bound` event, and `bootstrap_issue_flow` (orchestrator.py:193) reaches it via `link_issue(..., "task", ...)`. Removed the spec_ref write + spec_bound event block; kept the `latest_actor=effective_actor` update (`existing_events` still used by the `issue_linked` idempotency check). Updated `tests/vibe3/services/test_flow_binding.py::test_bind_flow_success` to the new contract (no spec_ref, 1 event) and added `test_link_issue_task_role_never_self_binds_spec_ref` regression. Observed RED (2 failed) → GREEN. Read path verified safe: `_resolve_spec_ref` already returns `str | None`, so a freshly-bootstrapped flow simply injects no spec content until an explicit canonical write. 45 task/orchestrator/binding tests + 192-test integration sweep green, mypy clean.
  - **Checkpoint**: US1 fully functional and independently testable — MVP demonstrable (acceptance criterion 1/2/3/5).

---

## Phase 4: User Story 2 — Recover Missing Artifact Without Destroying the Scene (Priority: P1)

**Goal**: A previously valid spec/plan/report/audit that later disappears becomes an artifact-repair blocker — the flow waits for explicit rebind/regeneration and is **not** auto-rebuilt.

**Independent Test** (spec US2): record a valid artifact, remove only the file in a temp test worktree, run consistency/recovery classification, verify non-destructive + actionable.

### Tests for User Story 2 (write FIRST)

- [x] T040 [TDD] [US2] Recovery-classification test in `tests/vibe3/services/test_flow_consistency.py`
  - Covers spec US2 scenarios 1/2/3: missing historical artifact → artifact blocker (not rebuild); role-output absence stays under no-op gate; runtime exception stays under FailedGate.

### Implementation for User Story 2

- [x] T041 [TDD] [REVIEW] [US2] Introduce `artifact_blocker` classification (FR-010/011/013)
  - Files: Modify `src/vibe3/services/flow/consistency.py:41-100` — the current `MISSING_REF` branch (`:91-98`) classifies as rebuild; split into: physical scene damage (worktree/flow corruption → rebuild) vs. missing historical artifact (→ artifact repair blocker). Add a new `FlowConsistencyCode` (e.g. `MISSING_ARTIFACT`) with `needs_rebuild=False`.
  - Interfaces: Produces the artifact-blocker signal consumed by recovery/serve layer.
- [x] T042 [TDD] [US2] Include `spec_ref` in consistency checking (FR-010)
  - Files: Modify `src/vibe3/services/flow/consistency.py:81` — add `spec_ref` to the checked ref tuple, sharing one resolution contract with plan/report/audit (do not special-case).
  - Test: missing spec file in healthy worktree → `MISSING_ARTIFACT`, not rebuild.
- [x] T043 [TDD] [P] [US2] Keep RoleOutputContract / no-op gate authoritative for absent role output (FR-012)
  - Files: `src/vibe3/config/role_policy.py:56-63`, `src/vibe3/execution/noop_gate.py:223-256`. No behavior change expected — add regression tests proving a role that omits required output (e.g. planner missing `plan_ref`) still hits the no-op gate, NOT the artifact blocker.
- [x] T044 [TDD] [P] [US2] Keep FailedGate separate from artifact blocked state (FR-013)
  - Files: `src/vibe3/domain/failed_gate.py:20-298`. Regression test: a runtime/system error still routes through FailedGate; artifact absence never triggers `E_MODEL_*`/`E_API_*` gate transitions.
  - **Checkpoint**: US2 independently testable — a missing artifact can no longer destroy a healthy worktree (SC-002).

---

## Phase 5: User Story 3 — Publish External Workflow Artifacts via Adapters (Priority: P1)

**Goal**: A project-owned spec-kit extension registers spec/plan/report/audit artifacts through public Vibe handoff commands; external sources stay untouched; direct superspec paths still publish.

**Independent Test** (spec US3): validate extension metadata + execute fixture hook commands against a temp flow, confirm expected Handoff refs + idempotent events.

### Tests for User Story 3 (write FIRST)

- [x] T050 [TDD] [US3] Extension metadata + hook fixture tests in `tests/vibe3/extensions/test_spec_kit_bridge.py` (new)
  - Covers spec US3 scenarios 1-4: after specify→spec, after plan→plan_ref, impl/review→report/audit, direct-superspec exit publishes; idempotent when both paths observe same artifact (FR-018).

### Implementation for User Story 3

- [x] T051 [REVIEW] [US3] Design project-owned spec-kit extension layout (FR-014/015/016)
  - Files: Create `.specify/extensions/vibe-spec-bridge/` (project-owned, NOT modifying `.specify/extensions/superspec/`). Define `extension.yml` with lifecycle hooks: `after_specify -> spec`, `after_plan -> plan`, implementation completion `-> report`, review completion `-> audit`. Each hook calls **public** Vibe handoff commands only (G7).
  - Note: existing `.specify/extensions/superspec/extension.yml:64-78` only defines `after_tasks/before_implement/after_implement` — the new `after_specify/after_plan` hooks are additive and live in the project-owned extension.
- [x] T052 [TDD] [US3] Implement `after_specify` → `handoff spec` and `after_plan` → `handoff plan` adapters (FR-015)
  - Files: adapter scripts under `.specify/extensions/vibe-spec-bridge/hooks/`. Each resolves the generated `.specify/specs/<NNN>/spec.md` / `plan.md` and invokes the public writer (T032 / existing `handoff plan`).
- [x] T053 [TDD] [P] [US3] Implement implementation → `report` and review → `audit` adapters (FR-015)
  - Files: same hook dir; call existing `handoff report` / `handoff audit` writers (`handoff_write.py:279,358`).
- [x] T054 [TDD] [US3] Direct-superspec exit contract (FR-017/018)
  - Files: a repository-owned bridge command (e.g. a thin `vibe3 handoff publish-spec-kit` or an exit rule document + adapter) that superspec skills invoke when bypassing core hooks. Must produce idempotent events when both this and the hook path observe the same artifact.
  - **Checkpoint**: US3 independently testable — fixture spec-kit workflow publishes all four artifact kinds without editing external source trees (SC-003).

---

## Phase 6: User Story 4 — Automated Planning Consumes Available Context (Priority: P2)

**Goal**: The task-branch planner consumes a recorded spec when present, evaluates accepted ADRs, and queries relevant long-term memory when available; absence stays legal; unreadable recorded ref is a blocker.

**Independent Test** (spec US4): build annotated/dry-run planner prompts for flows with (a) no spec, (b) valid spec, (c) unreadable recorded spec; verify context + failure boundaries.

### Tests for User Story 4 (write FIRST)

- [x] T060 [TDD] [US4] Planner prompt provenance tests in `tests/vibe3/roles/test_plan_spec_consumption.py`
  - Covers spec US4 scenarios 1-4: valid spec contributes content; absent spec legal; unreadable recorded spec → blocker; memory labeled advisory cannot override truth.
  - Done: 7 tests verify FR-019 (absent=legal / valid=content / unreadable=blocker), FR-020 (ADR recall), FR-021 (evidence limitation), FR-022 (memory advisory), FR-023 (dev/task independence).

### Implementation for User Story 4

- [x] T061 [TDD] [REVIEW] [US4] Planner must read recorded spec; distinguish absent vs unreadable (FR-019)
  - Files: `src/vibe3/roles/plan.py:135-154`. Added `elif spec_info.kind == "file"` blocker section when spec_ref is set but the file is unreadable. Absent spec_ref (None) remains legal — the section simply doesn't appear.
  - Done: `## Spec BLOCKED` surfaced for unreadable file specs; absent spec legal; valid spec content injected unchanged.
- [x] T062 [TDD] [P] [US4] ADR recall uses issue/spec semantics + accepted snapshot (FR-020)
  - Files: Added FR-020 annotation in `src/vibe3/roles/plan.py`. `supervisor/policies/plan.md:86` already instructs planner to run `vibe-adr-recall` skill (delivered by #3308). Low-code procedure verified — scans `status:accepted` ADR frontmatter.
  - Done: FR-020 annotation in plan.py; supervisor policy verified; ADR recall test guards regression.
- [x] T063 [TDD] [P] [US4] Memory retrieval is advisory + evidence-limitation reporting (FR-021/022)
  - Files: `src/vibe3/roles/plan.py:159-180`. Added `subprocess` call to `claude-memory smart-search` wrapped in try/except. On availability: memory content labeled `[Advisory]` — cannot override issue/spec/accepted-ADR/repository truth. On unavailability: `## Evidence Limitation` section reports the gap.
  - Done: advisory memory hook + evidence limitation fallback; test guards both paths.
- [x] T064 [REVIEW] [US4] Confirm `dev/*` independence from `task/*` label lifecycle (FR-023)
  - Files: Added `test_dev_branch_independence_from_task_lifecycle` in `tests/vibe3/roles/test_plan_spec_consumption.py`. Proves `_build_plan_task_guidance` produces identical output for `dev/issue-*` and `task/issue-*` branches.
  - Done: FR-023 regression test confirms branch-convention-agnostic plan prompt.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: ADR acceptance, baseline-spec updates, docs, and final verification — affect multiple stories.

- [ ] T701 [REVIEW] Advance ADR-0006 `proposed -> accepted` once implementation truth lands (spec "Documentation and governance")
  - Files: `docs/decisions/0006-spec-artifact-handoff-contract.md` frontmatter `status`; refresh Consequences with the T003 migration stance actually taken. Update `docs/decisions/INDEX.md` row.
- [ ] T702 [P] [SUBAGENT] Update baseline specs 001 / 003 / 006 implementation-truth sections (spec "Relationships to baseline specs")
  - Files: `.specify/specs/001-flow-lifecycle/spec.md` (consistency/recovery), `003-role-protocol/spec.md` (role context enrichment + output contract), `006-handoff-protocol/spec.md` (artifact kinds + validation). Only update where implementation truth changed; reference, do not reimplement (constitution principle II).
- [ ] T703 [P] [SUBAGENT] Update supervisor policies + handoff-store standard docs
  - Files: `supervisor/policies/plan.md:73` (strengthen from advisory to contract — planner MUST consume recorded spec), `docs/standards/v3/handoff-store-standard.md` (add `spec -> spec_ref` canonical kind).
- [ ] T704 [TDD] [P] Sync/async role equivalence tests (spec SC-006, issue acceptance criterion)
  - Files: `tests/vibe3/` — prove the unified writer + recovery classification behave equivalently across sync and async role execution paths.
- [ ] T705 Run modularity + targeted regression suite
  - `uv run pytest tests/vibe3/test_modularity/ tests/vibe3/services/test_handoff_service.py tests/vibe3/services/test_flow_consistency.py tests/vibe3/commands/test_handoff_spec.py -v`; full suite to CI (HARD RULE #14).
- [ ] T706 [REVIEW] Final spec acceptance-criteria sweep against issue #3310 checklist
  - Verify every box in issue #3310 "Acceptance criteria" maps to a completed task; record evidence in PR body.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no code deps; T003 migration stance is a **human checkpoint** blocking Phase 2.
- **Foundational (Phase 2)**: depends on T003; **BLOCKS all user stories** (T010-T014 establish the contract every story writes through).
- **US1 (Phase 3)**: depends on Phase 2 (T011/T012). MVP — deliver and validate first.
- **US2 (Phase 4)**: depends on Phase 2; conceptually also benefits from US1's `spec_ref` population but testable independently with synthetic recorded artifacts.
- **US3 (Phase 5)**: depends on Phase 2 + US1 public writer (T032). Hooks publish through US1's command.
- **US4 (Phase 6)**: depends on Phase 2 (canonical `spec_ref` shape from T012/T013); otherwise independent of US1-US3.
- **Polish (Phase 7)**: depends on all delivered user stories; T701 (ADR accept) gates on implementation truth.

### Within Each User Story

- Tests (T0xx with `[TDD]`) written and RED before implementation tasks.
- Service-layer contract (Phase 2) before command-layer (US1) before adapter-layer (US3).
- Story checkpoint must pass its Independent Test before moving on.

### Parallel Opportunities

- Phase 1: T001 ‖ T002 (independent audits).
- Phase 2: T014 (modularity export) ‖ other Phase 2 tasks once T010-T013 interfaces settle.
- US1: T031 ‖ T030 (independent test files); T034 ‖ T035 after T032/T033.
- US2: T043 ‖ T044 (independent regression assertions).
- US3: T053 ‖ T052 once adapter shape is fixed by T051.
- US4: T062 ‖ T063 ‖ T064 (independent policy/consumer concerns).
- Polish: T702 ‖ T703 (different doc trees) — both `[SUBAGENT]`-dispatchable.

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 (Setup) → T003 human gate.
2. Phase 2 (Foundational) → contract + validation + idempotent writer.
3. Phase 3 (US1) → `handoff spec` + `flow update --spec` delegation + `@spec` round-trip.
4. **STOP and VALIDATE** spec US1 Independent Test + issue acceptance criteria 1/2/3/5.

### Incremental Delivery

5. Phase 4 (US2) → recovery semantics; validate SC-002.
6. Phase 5 (US3) → extension bridge; validate SC-003.
7. Phase 6 (US4) → planner consumption; validate SC-004.
8. Phase 7 (Polish) → ADR accept + baseline specs + final sweep (SC-001/005/006).

---

## Notes

- File paths/line numbers anchor to explored baseline `306ef3b4`; re-anchor at implement time.
- Every implementation task is `[TDD]` (constitution principle III; superspec `before_implement` hook enforces Red-Green-Refactor).
- Adapters touch `.specify/extensions/vibe-spec-bridge/` only — never `.specify/extensions/superspec/` or external sources (G7).
- Shared-state writes always via public handoff commands (HARD RULE #2); never raw `.git/vibe3` access.
- Keep this task list reconciled with `plan.md`; do not maintain two divergent planning artifacts (constitution principle II).

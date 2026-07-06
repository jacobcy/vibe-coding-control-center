# Exit Contract: Direct Superspec Paths (FR-017 / FR-018)

## When this applies

A superspec skill that BYPASSES the core lifecycle hooks (for example an
`/speckit-superspec-execute` run that skips `after_specify`) MUST still
publish its artifacts into the Vibe flow through this exit contract. This
guarantees a recorded ref regardless of which path produced the artifact.

## Required publishing

| Phase     | Artifact                          | Public command                                  |
|-----------|-----------------------------------|-------------------------------------------------|
| specify   | `.specify/specs/<NNN>/spec.md`    | `vibe3 handoff spec <path> --branch <branch>`   |
| plan      | `.specify/specs/<NNN>/plan.md`    | `vibe3 handoff plan <path> --branch <branch>`   |
| implement | report (e.g. `docs/reports/...`)  | `vibe3 handoff report <path> --branch <branch>` |
| review    | audit  (e.g. `docs/reports/...`)  | `vibe3 handoff audit <path> --branch <branch>`  |

Or use the shared adapter, which resolves the artifact path automatically:

```bash
.specify/extensions/vibe-spec-bridge/hooks/publish-artifact.sh <kind> --branch <branch>
```

## Idempotency (FR-018)

When the hook path AND the direct exit path observe the SAME artifact, both
invoke `vibe3 handoff <kind>` with the identical canonical path. The writer
dedups the ref (`spec_ref` / `plan_ref` / `report_ref` / `audit_ref`) so the
second publish is a safe no-op: no duplicate state, no label churn. The
idempotent re-record contract is locked by
`tests/vibe3/services/test_handoff_service.py::test_record_spec_idempotent_rerecord`.

## Hard rules

- NEVER write shared state directly (`vibe3 handoff` only) — FR-016, HARD RULE #2.
- NEVER decide label or flow-state transitions — FR-016, G7.
- NEVER modify external spec-kit / superspec / Superpowers sources — FR-014.

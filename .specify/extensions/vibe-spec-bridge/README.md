# vibe-spec-bridge

Project-owned spec-kit extension that bridges spec-kit workflow artifacts
into the Vibe flow (spec 012 US3).

## What it does

After each spec-kit lifecycle phase, it publishes the generated artifact as
the matching Vibe handoff ref via the PUBLIC `vibe3 handoff` commands:

| Lifecycle hook   | Artifact        | Vibe ref     | Public command           |
|------------------|-----------------|--------------|--------------------------|
| after_specify    | spec.md         | spec_ref     | `vibe3 handoff spec`     |
| after_plan       | plan.md         | plan_ref     | `vibe3 handoff plan`     |
| after_implement  | report          | report_ref   | `vibe3 handoff report`   |
| after_review     | audit           | audit_ref    | `vibe3 handoff audit`    |

## Why a separate extension

- **FR-014**: the external `.specify/extensions/superspec/` tree is left
  untouched; this extension is fully project-owned.
- **FR-015 / FR-016**: adapters call `vibe3 handoff` only — they never write
  shared state directly and never decide label/state transitions.
- The `after_specify` / `after_plan` hooks are ADDITIVE (superspec only
  declares `after_tasks` / `before_implement` / `after_implement`).

## Files

- `extension.yml` — manifest, provided commands, lifecycle hooks.
- `commands/publish-*.md` — hook command guidance for each artifact kind.
- `hooks/publish-artifact.sh` — shared executable adapter that resolves a
  spec-kit artifact path and invokes `vibe3 handoff <kind>`.
- `EXIT_CONTRACT.md` — direct-superspec exit path (FR-017/018).

## Tests

`tests/vibe3/extensions/test_spec_kit_bridge.py` (T050) validates the
extension metadata, the adapter contract, and the fixture hook behavior
against a temp flow.

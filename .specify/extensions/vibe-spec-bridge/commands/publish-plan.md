---
description: Publish the generated plan.md into the Vibe flow (after plan)
---

# publish-plan (after plan)

After the spec-kit `plan` phase completes, record the generated
`.specify/specs/<NNN-slug>/plan.md` as `plan_ref` for the current Vibe flow.

## Resolution

The latest spec directory is `.specify/specs/<NNN-slug>/` (newest by name).
The artifact is `plan.md` within it.

## Publish

Use the shared adapter:

```bash
.specify/extensions/vibe-spec-bridge/hooks/publish-artifact.sh plan --branch <branch>
```

Or call the public writer directly:

```bash
vibe3 handoff plan .specify/specs/<NNN-slug>/plan.md --branch <branch>
```

## Contract

- MUST use `vibe3 handoff plan` — never write shared state directly (FR-016).
- Re-publishing the same path is safe (FR-018).

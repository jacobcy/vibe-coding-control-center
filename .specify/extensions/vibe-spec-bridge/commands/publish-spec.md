---
description: Publish the generated spec.md into the Vibe flow (after specify)
---

# publish-spec (after specify)

After the spec-kit `specify` phase completes, record the generated
`.specify/specs/<NNN-slug>/spec.md` as the canonical `spec_ref` for the
current Vibe flow.

## Resolution

The latest spec directory is `.specify/specs/<NNN-slug>/` (newest by name).
The artifact is `spec.md` within it.

## Publish

Use the shared adapter, which resolves the path automatically:

```bash
.specify/extensions/vibe-spec-bridge/hooks/publish-artifact.sh spec --branch <branch>
```

Or call the public writer directly:

```bash
vibe3 handoff spec .specify/specs/<NNN-slug>/spec.md --branch <branch>
```

## Contract

- MUST use `vibe3 handoff spec` — never write shared state directly (FR-016).
- Re-publishing the same path is safe; the writer dedups the ref (FR-018).
- `spec_ref` MUST be a canonical `.specify/specs/<NNN-slug>/spec.md` path
  (ADR-0006); legacy `#issue` forms are rejected on write.

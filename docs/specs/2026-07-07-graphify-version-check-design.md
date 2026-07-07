---
document_type: design
title: Graphify Version Check in Vibe Doctor
status: proposed
scope: tooling-diagnostics
author: Codex GPT-5
created: 2026-07-07
last_updated: 2026-07-07
---

# Graphify Version Check in Vibe Doctor

## Goal

Make the repository's Graphify output reproducible by declaring and checking one
stable `graphifyy` version through `vibe doctor`.

## Decision

- Pin the official PyPI package `graphifyy` to version `0.9.8`, which is the
  current stable PyPI release.
- Add Graphify to the configuration consumed by `vibe doctor`; do not add this
  concern to `vibe check` or `vibe3 check`.
- Treat Graphify as an optional development tool. A missing or mismatched version
  produces a non-blocking diagnostic with an exact remediation command.
- Keep the expected version in the dependency configuration as the single source
  of truth. Tests must not duplicate it in a second production configuration.

## Behavior

`vibe doctor` checks `graphify --version` and accepts only `0.9.8`.

For a missing installation or mismatched version, it reports the observed state
and recommends:

```bash
uv tool install --force graphifyy==0.9.8
```

The command remains successful when this optional tool is absent or mismatched,
consistent with existing optional-tool diagnostics.

## Implementation Boundary

- Extend the existing dependency-driven doctor configuration and its reader.
- Reuse the current doctor rendering path instead of adding a standalone version
  checker or a new top-level command.
- Do not change flow/task auditing, Graphify generation hooks, or tracking policy
  for `graphify-out/` in this change.

## Verification

Add targeted shell tests covering:

1. Installed Graphify version matches `0.9.8`.
2. Graphify is missing.
3. Graphify reports a different version.
4. Missing and mismatched Graphify remain non-blocking because it is optional.

Run only the relevant Bats test subset and configuration-reader tests locally.

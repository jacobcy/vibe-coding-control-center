---
document_type: design
title: Graphify Version Check in Vibe Doctor
status: approved
scope: tooling-diagnostics-and-generated-artifact-delivery
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
- Do not change flow/task auditing or install/uninstall user-local Graphify hooks.

## Generated Artifact Delivery

Feature branches do not commit `graphify-out/` changes produced by Graphify's
post-commit hook. After a source PR is merged, a GitHub Actions workflow runs on
`main`, regenerates the graph with the pinned Graphify version, and updates one
reusable `automation/graphify-sync` pull request.

The workflow cannot push directly to `main`: repository branch protection
requires changes to arrive through a pull request and applies to administrators.
The generated pull request therefore remains a normal reviewable delivery unit
and runs the existing required CI checks.

The sync workflow must:

- trigger only after non-`graphify-out/` changes reach `main`, with a manual
  dispatch fallback;
- grant the workflow `GITHUB_TOKEN` only `contents: read` and use a dedicated
  `GRAPHIFY_SYNC_TOKEN` for branch/PR writes;
- install exactly `graphifyy==0.9.8`;
- stage only the four tracked artifacts under `graphify-out/`;
- no-op when regeneration produces no staged changes;
- force-update the dedicated automation branch and reuse its existing PR;
- avoid a loop when that generated-only PR is merged.

The workflow requires `GRAPHIFY_SYNC_TOKEN`, backed by a GitHub App or PAT with
contents and pull-request write access, so generated PR events run required CI
normally. It fails before checkout when the secret is missing and never falls
back to `GITHUB_TOKEN`.

GitHub should classify `graphify-out/**` as generated so its large patches are
collapsed by default.

## Commit Workflow Contract

`vibe-commit` must treat ordinary feature PRs and generated-artifact PRs as
different delivery targets.

For an ordinary feature PR:

1. Record whether `graphify-out/` was clean before the commit cycle. If it was
   already dirty, stop and classify the changes instead of discarding them.
2. Capture the pre-validation commit as `BASE_SHA` and explicitly stage only the
   intended files.
3. Always create a temporary commit so the real commit hooks run.
4. If `graphify-out/` was clean before the commit, wait for the post-commit
   rebuild and restore only its generated changes.
5. Use `git reset --mixed "$BASE_SHA"`; do not call this a soft reset.
6. Re-stage and create the formal functional commits. Clean hook-generated graph
   changes after each formal commit under the same pre-clean condition.
7. Block PR publication if the full `origin/main...HEAD` PR range contains
   `graphify-out/` paths.

Intentional graph or curated-label changes require a separate Graphify delivery
target; they are never silently discarded or mixed into a functional PR.

## Verification

Add targeted shell tests covering:

1. Installed Graphify version matches `0.9.8`.
2. Graphify is missing.
3. Graphify reports a different version.
4. Missing and mismatched Graphify remain non-blocking because it is optional.

Run only the relevant Bats test subset and configuration-reader tests locally.

Add workflow and skill contract tests covering trigger loop prevention, minimum
permissions, the exact pinned version, graph-only staging, mandatory temporary
commit validation, correct mixed-reset terminology, and the feature-PR graph
exclusion gate.

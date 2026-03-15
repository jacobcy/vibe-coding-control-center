---
document_type: plan
title: Phase 04 - Handoff & Cutover
status: draft
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-15
related_docs:
  - docs/v3/plans/v3-rewrite-plan.md
  - docs/v3/implementation/02-architecture.md
---

# Phase 04: Handoff & Cutover

**Goal**: Implement synchronization between the local SQLite database and Markdown handoff files, then transition the primary entry point to `vibe3`.

## 1. Context Anchor (Optional)
If you require more than technical scope, refer to the [Vibe 3.0 Master Plan](v3-rewrite-plan.md).

## 2. Pre-requisites (Executor Entry)
- [ ] `docs/v3/handoff.md` template exists.
- [ ] `vibe3 flow status --json` returns a non-empty list of active flows.

## 2. Handoff Logic

- **Two-Way Sync**: Ensure `vibe3 handoff sync` can push SQLite state to Markdown markers and vice versa.
- **Marker Format**: Use standard HTML/Markdown comment markers (e.g., `<!-- VIBE_STATE_START -->`) to identify injectable regions.
- **Schema Validation**: Verify that the handoff Markdown matches the required structured data schema for the next Agent.

## 2. Technical Cutover

- **Entry Proxy**: Modify `bin/vibe` to check for a configuration flag (or file presence) to decide whether to run `vibe2` (legacy) or `vibe3`.
- **Delegation**: Ensure `vibe3` can transparently handle commands that were previously handled by `vibe2`, providing a compatibility layer if necessary.

## 3. Success Criteria (Technical)

- [ ] `vibe3 handoff sync` updates `docs/v3/handoff.md` without overwriting unrelated text.
- [ ] Run a comparison tool that confirms 100% data parity between `handoff.db` and the Markdown file.
- [ ] Executing `bin/vibe flow status` successfully triggers the `vibe3` path.
- [ ] `vibe3 handoff edit` opens the correct file with the specified editor.

## 4. Handoff for Executor 05
- [ ] Verify `bin/vibe` successfully delegates to the new implementation.
- [ ] Ensure all `lib3/` modules are correctly linked.

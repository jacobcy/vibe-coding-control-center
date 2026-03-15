---
document_type: plan
title: Phase 03 - PR Domain (GitHub Integration)
status: draft
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-15
related_docs:
  - docs/v3/plans/v3-rewrite-plan.md
  - docs/v3/implementation/02-architecture.md
---

# Phase 03: PR Domain (GitHub Integration)

**Goal**: Implement Pull Request automation logic and GitHub API integration.

## 1. Context Anchor (Optional)
If you require more than technical scope, refer to the [Vibe 3.0 Master Plan](v3-rewrite-plan.md).

## 2. Pre-requisites (Executor Entry)
- [ ] `Vibe3Store` can successfully write/read from SQLite.
- [ ] Environment variables for GitHub API (or `gh` CLI auth) are verified.

## 2. Interaction Requirements

- **Metadata Injection**: Automatically inject Task ID, Flow Slug, and Group ID into the PR Description.
- **State Feedback**: Fetch PR status (draft, open, merged) and reflect it in `flow status --json`.
- **API Helper**: Use `scripts/python/lib/github.py` for all GH interactions (wraps `gh` CLI).

## 2. Technical Requirements

- **PR Draft Logic**: Create PR as draft by default.
- **Versioning**: Implement the "group-based bump" logic where the highest priority change in the group determines the next version (patch/minor/major).
- **PR Readiness**: Move PR from draft to ready once local validation passes.

## 3. Success Criteria (Technical)

- [ ] `vibe3 pr draft` successfully creates a GitHub PR and returns the URL.
- [ ] PR description contains strictly formatted metadata: `Task: #123`, `Flow: <slug>`.
- [ ] `vibe3 pr ready` triggers the correct version bump calculation (logged to STDOUT).
- [ ] Log file confirms "API call successful" for each PR state transition.

## 4. Handoff for Executor 04
- [ ] Ensure `vibe3 pr draft` returns a URL (real or mock) that can be read by the Handoff sync logic.

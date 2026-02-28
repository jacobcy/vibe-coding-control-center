---
name: vibe-review-docs
description: Agentic Documentation and Changelog Review. Use when auditing documentation, PRDs, or markdown files for quality and consistency.
category: process
trigger: manual
---

# Vibe Documentation Review Protocol

When invoked to review documentation, your goal is to ensure clarity, consistency, and alignment with the Vibe Center architecture layout.

## 1. Context Gathering
- Identify modified `.md` files in the current branch or PR (`gh pr diff` or `git diff main...HEAD --name-only | grep '\.md$'`).
- Check if `CHANGELOG.md` has been reasonably updated if there are user-facing changes in the same diff.

## 2. Review Standards
Evaluate the documentation against the following checklist:
1. **Completeness**: Are `docs/prds/` following standard conventions (Background, Goals, Acceptance Criteria)?
2. **Language & Clarity**: Is the writing concise? Remove overly generic AI-speak ("In today's fast-paced digital world...").
3. **Accuracy**: Do the documented CLI commands and architecture limits (e.g., 1200 LOC limit) match `CLAUDE.md` and `DEVELOPER.md`?
4. **Git Constraints**: Are we strictly distinguishing `.agents/` (disposable global tools directory) from `.agent/` (managed project-specific workflows)?

## 3. Output: The Doc Review Report
Construct a structured report:

### 📄 Documentation Review Summary
**Conclusion:** [Approved / Needs Revisions]

### 🔴 Required Edits (Blockers)
- **[File:Line]** Detail what must be fixed (e.g. incorrect terminology, missing CHANGELOG entry).

### 🟡 Formatting & Clarity Suggestions
- **[File:Line]** Suggestions for better outline structure, markdown linting, or brevity.

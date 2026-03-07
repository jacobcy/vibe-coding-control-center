---
name: vibe-review-docs
description: Agentic Documentation and Changelog Review. Use when auditing entry files (CLAUDE.md, SOUL.md), docs/ directory, or checking for incorrect concepts. Use `vibe flow review` to check PR status. **RECOMMENDED: Run as subagent to save tokens.**
category: process
trigger: manual
---

# Vibe Documentation Review Protocol

**核心职责**: 文档概念审查（检查错误概念和过时信息）

**使用场景**:
1. **入口文件审查**: 检查 CLAUDE.md, SOUL.md, STRUCTURE.md 等入口文件
2. **docs/ 目录审查**: 审计 docs/ 目录下的文档质量
3. **概念对齐**: 确保文档中的概念与代码实际状态一致

When invoked to review documentation, your goal is to ensure clarity, consistency, and alignment with the Vibe Center architecture layout.

## 1. Context Gathering (Align Truth)
- **Identify Intent**: Run `vibe flow review` (Physical Tier 1) to determine the current state of documentation-heavy PRs.
- **Identify Files**: 
  - Use `gh pr diff --name-only` or `git diff main...HEAD --name-only` and filter for `\.md$`.
  - For local docs review, combine `git diff --name-only` and `git diff --cached --name-only`, then filter for `\.md$`.
- **Review Context**: Check if `CHANGELOG.md` has been reasonably updated by the `vibe flow pr --bump` process.

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

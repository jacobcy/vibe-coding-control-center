---
name: vibe-review-docs
description: Use when the user wants to review documentation changes, audit entry files or standards docs, check changelog quality, inspect concept drift in docs, or says "review docs" / "review documentation". Do not use for source-code implementation review.
---

# Vibe Documentation Review Protocol

> 项目命令参考见 `skills/vibe-instruction/SKILL.md`

**核心职责**: 文档概念审查（检查错误概念和过时信息）

**使用场景**:

1. **入口文件审查**: 检查 CLAUDE.md, SOUL.md, STRUCTURE.md 等入口文件
2. **docs/ 目录审查**: 审计 docs/ 目录下的文档质量
3. **概念对齐**: 确保文档中的概念与代码实际状态一致

语义边界：

- `vibe-review-docs` 负责 docs、standards、task/readme、changelog 与入口文件的概念和表达审查。
- 仅当对象是文档、标准、说明文字或文档治理问题时介入。
- source code diff、实现正确性与测试风险审查交给 `vibe-review-code`。

When invoked to review documentation, your goal is to ensure clarity, consistency, and alignment with the Vibe Center architecture layout.
## 1. Context Gathering (Align Truth)

- **Identify Intent**: Run `vibe3 review base` (Physical Tier 1) to determine the current state of documentation-heavy PRs.
- **Identify Files**:
  - Use `gh pr diff --name-only` or `git diff main...HEAD --name-only` and filter for `\.md$`.
  - For local docs review, combine `git diff --name-only` and `git diff --cached --name-only`, then filter for `\.md$`.
- **Review Context**: Check if `CHANGELOG.md` has been reasonably updated.

## 2. Review Standards

Evaluate the documentation against the following checklist:

1. **Completeness**: Are `docs/prds/` following standard conventions (Background, Goals, Acceptance Criteria)?
2. **Language & Clarity**: Is the writing concise? Remove overly generic AI-speak ("In today's fast-paced digital world...").
3. **Accuracy**: Do the documented CLI commands and architecture match the current V3 state? (Check `vibe3 --help`).
4. **Git Constraints**: Are we strictly distinguishing `.agents/` (disposable global tools directory) from `.agent/` (managed project-specific workflows)?

## 3. Output: The Doc Review Report
...
## 4. Handoff 记录

完成审查后，更新 handoff：

```bash
vibe3 handoff append "vibe-review-docs: Documentation review completed" --actor vibe-review-docs --kind milestone
```
### 🔴 Required Edits (Blockers)

- **[File:Line]** Detail what must be fixed (e.g. incorrect terminology, missing CHANGELOG entry).

### 🟡 Formatting & Clarity Suggestions

- **[File:Line]** Suggestions for better outline structure, markdown linting, or brevity.

## 4. Handoff 记录

完成审查后，更新 handoff：

```bash
uv run python src/vibe3/cli.py handoff append "vibe-review-docs: Documentation review completed" --actor vibe-review-docs --kind milestone
```

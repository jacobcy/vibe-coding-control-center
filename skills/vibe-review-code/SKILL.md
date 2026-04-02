---
name: vibe-review-code
description: Use when the user wants a structured code review for local or PR-bound code changes, asks for a pre-PR implementation audit, wants to validate fixes against PR review feedback, or says "review this code" for source changes. Do not use for docs-only review or concept/documentation governance review.
---

# Vibe Code Review Protocol

> 项目命令参考见 `skills/vibe-instruction/SKILL.md`

**核心职责**: 代码质量审查（PR 提交前后的深度分析）

**使用场景**:

1. **PR 前**: 在创建 PR 之前，进行深度静态分析
2. **PR 后**: 根据 `vibe3 review pr` 的反馈修复代码

语义边界：

- `vibe-review-code` 负责 source code diff、实现风险、调用影响、测试覆盖与 review feedback 复核。
- 仅当用户要审查代码实现本身，或根据 review feedback 回修代码时介入。
- 文档、标准、changelog、概念漂移的审查交给 `vibe-review-docs`。

When invoked as a code reviewer, you are a Senior Staff Engineer tasked with guarding the project against entropy, dead code, and standard violations.

## 0. Token 优化策略（推荐）

**此 skill 消耗大量 token（读取大量代码文件）。强烈建议使用以下策略：**

### 方案 A：使用 Subagent（推荐）

```bash
# 在独立 agent 中运行审查，避免污染主会话
# AI 会自动使用 Agent tool 启动 subagent
```

**优势**:

- 隔离执行环境
- 主会话 token 不被消耗
- 可并行执行其他任务

### 方案 B：使用本地审查（最快）

```bash
# 使用 vibe3 进行本地代码审查
vibe3 review base
```

**优势**:

- 零外部 token 消耗
- 执行速度最快
- 深度静态分析

### 方案 C：传统 AI 审查

直接在主会话中执行审查（不推荐，消耗大量 token）

## 1. 与验证流程的关系（互补）

- **自动验证**: 包含 Serena 分析、Lint、Tests。通常在代码改完后由 /vibe-commit 触发。
- `vibe-review-code`: 偏人工审查结论，适合 PR 前人工把关、PR 后针对 review comment 复核。
- 推荐顺序：先让自动验证跑出基础质量结果，再用本 skill 输出最终审查意见。

## 触发时机

- 你准备发起 PR，需要先做一轮严格审查时
- 你收到 review comment，需要确认修复是否引入回归时
- 你需要一份结构化审查结论（Blocking/Major/Minor/Nit）时
- 用户说“review 这段代码 / 这次改动 / 这个实现”且对象是 source changes 时

## 1. Context Gathering (Align Truth)

- **Identify Intent**: Run `vibe3 review base` (Physical Tier 1) to determine the current state of the PR and project health.
- **Fetch Diff**:
  - If a PR exists (opened): Use `gh pr diff` to fetch the source of truth for changes.
  - If local only: Use `git diff main...HEAD`.
- If local: Use `git diff` and `git diff --cached` for uncommitted changes; use `git diff main...HEAD` for committed branch diffs.
- **Review Context**: Cross-reference with the Task README and the original goal from `vibe3 handoff show`.

## 2. Serena 使用步骤（审查前）

Before deciding severity on function-level changes, run Serena impact analysis first.

Startup:

- Prefer on-demand startup: `uvx --from git+https://github.com/oraios/serena@v0.1.4 serena start-mcp-server`
- Preconditions: `uv/uvx` available and project has `.serena/project.yml`
- Evidence command: `vibe3 inspect symbols` or `vibe3 inspect base`
- Required artifact: `.agent/reports/` 中的分析结果

Required checks:

1. For each changed function, run `find_referencing_symbols("<function_name>")`.
2. For each removed function, verify caller count is `0`; otherwise mark as `Blocking`.
3. For each signature change, verify all callers are updated; otherwise mark as `Major`.

If Serena is unavailable:

- Record blocking reason (tool/network/config).
- Continue review with `git diff` + targeted grep as fallback.
- Add one `Major` finding: "AST impact analysis not completed".

## 3. Review Standards (Vibe V3 Paradigm Gate)

You **MUST** strictly evaluate the code against `CLAUDE.md` and `.agent/rules/python-standards.md`:

1. **LOC Hard Limits**: Are new functions blowing up the line count? (Max 300 lines per file).
2. **Zero Dead Code**: Does every added function have a clear caller? If not, FLAG IT as a blocking issue.
3. **Python Standards**: Does the code follow Pydantic models? Are type hints complete? (Refer to `.agent/rules/python-standards.md`).
4. **Testing**: Does the branch include modifications or additions to `tests/vibe3/` if a bug was fixed or feature added?
5. **Linting Check**: Run `uv run ruff check src` if unsure.

## 3.1 Document Governance Check

When the change touches documentation, you MUST also review it against:

- `SOUL.md`
- `docs/standards/glossary.md`
- `docs/standards/action-verbs.md`
- `docs/standards/doc-quality-standards.md`

Check these questions:

1. Is the document acting within its role (`入口文件` / `标准文件` / `参考文件` / `规则文件`)?
2. Does it redefine a concept that should only live in `glossary.md`?
3. Does it use a high-frequency action verb in a way that conflicts with `action-verbs.md`?
4. Is an entry document carrying too much detail that should move to `docs/standards/` or `.agent/rules/`?
5. If the file is historical or superseded, is that status made explicit?

If any answer fails, report it as a documentation governance finding even if the prose itself is clear.

## 4. Review Process

1. **Understand Intent**: Compare implementation against the `docs/prds/` or plan file.
2. **Line-by-Line Analysis**: Point out exact files and lines where issues exist.
3. **Actionability**: Never just say "it's bad", always provide the code snippet to fix it.

## 5. Output: The Code Review Report

Construct a structured report using Markdown with strict severity buckets:

- `Blocking`
- `Major`
- `Minor`
- `Nit`

Each finding MUST include:

- `file/function`
- `issue`
- `failure mode`
- `minimal fix`

## 6. Handoff 记录

完成审查后，更新 handoff：

```bash
vibe3 handoff append "vibe-review-code: Code review completed" --actor vibe-review-code --kind milestone
```

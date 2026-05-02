---
name: vibe-review-docs
description: Use when the user wants to review documentation changes, audit entry files or standards docs, check changelog quality, inspect concept drift in docs, or says "review docs" / "review documentation". Do not use for source-code implementation review.
---

# Vibe Documentation Review Protocol

## 职责

**本 Skill 只负责**：
1. 文档概念审查（检查错误概念和过时信息）
2. 入口文件审查（CLAUDE.md, SOUL.md, STRUCTURE.md 等）
3. docs/ 目录审查
4. 概念对齐（确保文档与代码实际状态一致）

**语义边界**：
- `vibe-review-docs` 负责 docs、standards、task/readme、changelog 与入口文件的概念和表达审查
- source code diff、实现正确性与测试风险审查交给 `vibe-review-code`

---

## Step 0: 初始化任务跟踪

**启动时创建 task 跟踪进度**（使用 TaskCreate tool）：

```yaml
TaskCreate(
  title: "Doc Review",
  description: "文档审查：检查概念对齐和引用正确性"
)
```

---

## Step 1: 确定审查范围

### PR 文档审查

```bash
PR_BASE=$(gh pr view <number> --json baseRefName -q .baseRefName)
PR_BRANCH=$(gh pr view <number> --json headRefName -q .headRefName)
git fetch origin "$PR_BASE" "$PR_BRANCH" --quiet
git diff --name-only "origin/$PR_BASE...origin/$PR_BRANCH" -- '*.md'
git diff "origin/$PR_BASE...origin/$PR_BRANCH" -- '*.md'
```

### 本地文档审查

```bash
git diff main...HEAD --name-only | grep '\.md$'
git diff main...HEAD -- '*.md'
```

---

## Step 2: 收集项目上下文

**关键区分**：本地开发 vs 远程审查

### 本地开发

```bash
uv run python src/vibe3/cli.py handoff status $(git branch --show-current)
```

### 远程审查

```bash
PR_BRANCH=$(gh pr view <number> --json headRefName -q .headRefName)
gh pr view <number> --comments
```

---

## Step 3: 审查标准

检查以下维度：

| 维度 | 检查项 |
|------|--------|
| **Completeness** | PRD 是否遵循标准格式（Background, Goals, Acceptance Criteria） |
| **Language & Clarity** | 是否简洁，去除泛化 AI 语言 |
| **Accuracy** | CLI 命令和架构描述是否与当前 V3 状态一致 |
| **References** | 引用的文件是否存在，路径是否正确 |
| **Deprecation** | 废弃文件是否有明确的 deprecation notice |

### 验证引用

```bash
# 检查引用文件是否存在
ls -la docs/standards/v3/command-standard.md

# 检查废弃文件状态
head -10 docs/standards/vibe3-state-sync-standard.md
```

---

## Step 4: 验证

运行相关检查：

```bash
# CLI 命令验证
uv run python src/vibe3/cli.py --help

# 特定命令验证
uv run python src/vibe3/cli.py <command> --help
```

---

## Step 5: 输出审查报告

### 格式

```markdown
## Findings

- [Blocking] path:line
  - Issue:
  - Failure mode:
  - Minimal fix:

## Verification

- Passed:
- Not run:

## Verdict

PASS | MAJOR | BLOCK
```

### 严重级别

| 级别 | 定义 |
|------|------|
| **Blocking** | 错误概念、指向不存在文件的引用、缺失 deprecation notice |
| **Major** | 应在合并前修复；描述与代码不一致、缺失关键文档 |
| **Minor** | 有限影响的问题；格式、措辞优化 |
| **Nit** | 小的清晰度问题 |

---

## Step 6: Handoff 记录

完成审查后，更新 handoff：

```bash
uv run python src/vibe3/cli.py handoff append "vibe-review-docs: Documentation review completed" --actor vibe-review-docs --kind milestone
```

---

## 文件位置

| 文件 | 职责 |
|------|------|
| `skills/vibe-review-docs/SKILL.md` | 本文件：文档审查流程 |
| `skills/vibe-review-code/SKILL.md` | 代码审查流程 |
| `docs/standards/quality-control-standard.md` | QC 标准 |

---

## 使用方式

```
/vibe-review-docs
/vibe-review-docs 637
```

或

```
用 vibe-review-docs 审查 PR #637
```

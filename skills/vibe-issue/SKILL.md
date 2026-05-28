---
name: vibe-issue
description: Use when the user wants to create or refine a GitHub issue. This is a human-facing intake entrypoint, not an automated workflow.
---

# /vibe-issue - Issue Intake Entrypoint

该技能负责人机协作的 Issue 创建：澄清、查重、规范化。

## Core Principle: Human-Facing Only

**只负责人机交互**：
- 澄清用户意图
- 查重现有 issue
- 规范化内容
- 创建 GitHub issue
- 解释下一步（roadmap 或 new）

**不承担的职责**：
- 不检查 flow/task 状态（那是执行阶段的产物）
- 不决定自动化路径
- 不判断 issue 是否应该进入 workflow

## Workflow

### Step 1: Clarify Intent

- 用户可直接运行 `/vibe-issue` 或 `/vibe-issue create "<标题>"`
- 扫描 `.github/ISSUE_TEMPLATE/*.md`
- 询问 Bug 或 Feature，获取模板 fields

### Step 2: Deduplication Check

```bash
gh issue list --search "<标题>" --state all --json number,title,state
```

- 高相似度：展示重复 Issue，建议合并或评论
- 低相似度：继续创建

### Step 3: Dependency Identification

扫描草稿中的依赖引用（`#<数字>`、`Depends on`）：

- 确认目标 issue 状态
- 引导用户写入 `## Dependencies` section
- 格式：`- Depends on #<id> — <短描述>`

### Step 4: Fill & Polish

- 引导补充缺失信息
- 建议 Labels（`bug`、`enhancement`、`priority/*`）
- **禁止添加 `vibe-task` 标签**（自动镜像）

### Step 5: Scope Check

扫描是否为 epic 候选：
- 标题含：`审查`、`总览`、`清理`、`重构所有`
- Body 含：`>N 个文件`、列出 >3 个子任务

建议拆分为主 issue + sub-issues，或记录 `## Scope estimate`。

### Step 6: Create

```bash
gh issue create --title "<标题>" --body "<内容>" --label "<labels>"
```

输出 Issue 链接，建议下一步：
- 版本规划：`vibe-roadmap`
- 人工开工：`vibe-new`
- 只说明已创建，等待规划

## Minimal Stop Points

- Issue created
- Existing issue confirmed
- Insufficient info, blocked
- Ready to handoff

## Design Principles

1. 不读取 flow/task 状态（创建阶段不需要）
2. 只负责人机交互，不定义自动化语义
3. GitHub issue 是真源，不检查本地状态
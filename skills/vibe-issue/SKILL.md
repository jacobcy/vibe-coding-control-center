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

### Step 4.5: Milestone Assignment

**必须为每个 issue 分配 milestone**，确保版本规划可追踪。

**检查现有 milestones**：

```bash
gh api repos/{owner}/{repo}/milestones --paginate -q '.[] | {number, title, open_issues, closed_issues}'
```

**询问用户**：

> 建议分配到哪个 milestone？
> 
> 当前活跃 milestones：
> - Phase 6: 架构清理与模块化 (5 open)
> - Phase 7: Runtime Kernel 核心能力 (3 open)
> - Phase 8: Runtime Kernel 高级特性 (1 open)
>
> 或创建新 milestone？

**分配原则**：

- **Bug 修复** → 当前版本 milestone（如有活跃修复阶段）或下一版本
- **Feature/Epic** → 根据规划放入对应版本 milestone
- **RFC/讨论** → 暂不分配 milestone，等待决策
- **Sub-issue** → 与父 epic issue 使用相同 milestone

**如果用户不确定**：

提供推荐并说明理由：

```text
建议分配到: Phase 6: 架构清理与模块化
理由: 此 issue 涉及 services/shared 模块重构，属于架构清理范围
```

### Step 5: Scope Check

扫描是否为 epic 候选：
- 标题含：`审查`、`总览`、`清理`、`重构所有`
- Body 含：`>N 个文件`、列出 >3 个子任务

建议拆分为主 issue + sub-issues，或记录 `## Scope estimate`。

### Step 5.5: Anti-Pattern Risk Check

对照以下 5 条反模式特征，检查 issue 是否存在反模式风险（定义详见 [roadmap-common.md](../../supervisor/roadmap-common.md#反模式-issue-识别标准)）：

**检查清单**：

- [ ] **有明确痛点**：描述具体使用场景、痛点和验证依据
- [ ] **复杂度与收益匹配**：修改范围合理，收益不只服务模糊或极小场景
- [ ] **不与现有能力重叠**：确认 CI、skill 或既有流程无法解决
- [ ] **符合项目原则**：最小变更、认知优先、Skill-First、验证优先
- [ ] **不是边缘场景驱动**：需求有通用价值，不能由用户自行处理

**风险评估**：

如果命中 >= 2 条未通过项，向用户展示警告：

> ⚠️ **反模式风险提示**
>
> 此 issue 可能被标记为反模式并关闭。建议补充痛点描述、验证证据，或说明为何现有能力无法满足需求。
>
> 详见 [反模式识别标准](../../supervisor/roadmap-common.md#反模式-issue-识别标准)。

**注意**：此步骤只提供警告，不阻止创建（vibe-issue 是 human-facing，不自动拒绝）。

### Step 6: Create

```bash
# 如果有 milestone
gh issue create --title "<标题>" --body "<内容>" --label "<labels>" --milestone "<milestone title>"

# 如果是 RFC 或用户明确不确定 milestone
gh issue create --title "<标题>" --body "<内容>" --label "<labels>"
```

**重要**：
- 创建后立即确认 milestone 是否正确设置
- 如无 milestone，提醒用户后续需通过 `vibe-roadmap` 补充分配

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

---
name: vibe-roadmap
description: Use when the user wants project-level roadmap planning, version goals, or backlog triage. Do not use for assignee pool governance or single-flow execution.
---

# /vibe-roadmap - 版本规划与 Backlog Triage

管理版本路线图和 backlog 分类。

## 核心原则

- **只管规划**：版本目标、milestone、backlog triage
- **GitHub-as-truth**：所有操作通过 GitHub labels
- **不做执行**：不处理单个 flow 执行

## Scope

**只做规划层决策**：
- 版本目标定义
- Issue 分类与 milestone 分配
- Roadmap/priority labels 设置
- Backlog triage（哪些 issue 进入规划）

**不做**：
- 执行层管理（由 `vibe-orchestra` 负责）
- RFC issues 处理（由 `vibe-task` 负责）
- Blocked issues 处理（由 `vibe-task` 负责）

## Workflow

### Step 1: 检查版本目标

```bash
vibe3 task status
gh issue list --limit 50
gh issue list -l "roadmap/p0"
gh issue list -l "roadmap/p1"
```

获取：
- 当前版本目标是什么
- 有哪些 issues 等待分类
- 各版本窗口下的候选 issue

### Step 2: 版本规划决策

**场景 A: 没有版本目标**
- 提示用户定义版本目标
- 展示 backlog 中的 issues 供选择
- 要求人类讨论确定目标

**场景 B: 有版本目标但有新 issues**
- 对新 issues 进行分类：
  1. 分配 milestone
  2. 添加 roadmap 状态标签（`roadmap/p0`, `roadmap/p1` 等）
  3. 必要时补 `priority/[0-9]`
- 对候选 issues 做 intake gate 判断：纳入 / 不纳入 / RFC

### Step 3: 应用标签

```bash
gh issue edit <issue-number> --milestone "Phase 1: 基础设施"
gh issue edit <issue-number> --add-label "roadmap/p0"
gh issue edit <issue-number> --add-label "priority/5"
```

### Step 4: 输出状态

```text
📋 版本规划状态

当前版本: Phase 1: 基础设施

P0 (紧急)
- #36: GitHub Projects 整合 [roadmap/p0, priority/8]

当前版本
- #34: Issue 同步 [roadmap/p1, priority/5]
- #35: save 自动关联 [roadmap/p1, priority/5]

下一个版本
- #37: 智能调度 [roadmap/p2, priority/3]

RFC (需讨论)
- #77: 架构方向未定 [roadmap/rfc]
```

## 与其他 Skills 的区别

- **vibe-roadmap**: 版本规划和 backlog triage
- **vibe-orchestra**: assignee issue pool 管理（运行中的 issues）
- **vibe-task**: RFC 和 blocked issues 检查（问题 issue）

## Restrictions

- 不处理执行层管理
- 不看 RFC 或 blocked issues（转给 `vibe-task`）
- 不根据当前 runtime 现场做即时抢占排序（由 `vibe-orchestra` 负责）
- 所有操作通过 GitHub labels，不在本地存储
---
name: vibe-task
description: Use when the user wants to inspect RFC and blocked issues, or check overall task status. Do not use for roadmap prioritization or issue pool governance.
---

# /vibe-task - RFC & Blocked Issues 检查

检查项目中的 RFC issues 和 blocked issues 状态。

## 核心原则

- **专注问题 issue**：RFC 和 blocked issues
- **基于真源**：只读 shell 输出，不补充字段
- **简单总览**：给出状态，不做复杂建议

## Scope

**只看两类 issue**：

1. **RFC issues** (`roadmap/rfc` label)
   - 需要人类讨论的 issue
   - 目标不明确或需要架构决策

2. **Blocked issues** (`state/blocked` label)
   - 有依赖阻塞的 issue
   - 需要解除阻塞才能继续

**不看**：
- 正常运行的 issue（由 `vibe-orchestra` 管理）
- 版本规划（由 `vibe-roadmap` 管理）

## Workflow

### Step 1: 运行 CLI

```bash
vibe3 task status
```

### Step 2: 解析 RFC issues

从输出中找出带 `roadmap/rfc` 的 issues：

- issue 编号、标题
- RFC 原因（从 labels 或 body 中解析）
- 当前状态

### Step 3: 解析 Blocked issues

从输出中找出带 `state/blocked` 的 issues：

- issue 编号、标题
- 阻塞原因（从 `blocked_reason` 或 `blocked_by_issue` 中解析）
- 依赖的 issue（如有）

### Step 4: 输出状态

```text
📋 RFC & Blocked Issues 检查

RFC Issues (需要人类讨论)
- #123: 架构方向未定
  - 原因: 需要确认是否使用新框架
  - 状态: open

Blocked Issues (有依赖阻塞)
- #456: 依赖 #123 完成
  - 阻塞原因: depends on #123
  - 状态: blocked

建议
- RFC issues: 安排讨论会议
- Blocked issues: 先处理依赖 issue
```

## 与其他 Skills 的区别

- **vibe-task**: 只读 surface RFC/blocked（提请人类关注，不做决策）
- **vibe-orchestra**: 入口 intake（筛选打 assignee）+ serve 监控
- **vibe-roadmap**: 版本规划 + 纠正 assignee-pool 决策（含 rfc 的 override）

**职责分工**：vibe-task 只**发现并提请**（rfc/blocked）；真正的**决策/纠正**去 vibe-roadmap（rfc/roadmap）或 vibe-orchestra（assign/入池）。Level 0 issue 由 intake/vibe-orchestra 打上 `roadmap/rfc` 后，vibe-task 通过 task-status Rule 1 自动 surface。

## Restrictions

- 不做复杂审计或修复
- 不补充 CLI 未提供的字段
- 不处理正常运行的 issue
- 不做版本规划建议
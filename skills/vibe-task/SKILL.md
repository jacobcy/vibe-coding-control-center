---
name: vibe-task
description: Use when the user wants to inspect RFC, blocked, or epic issues, check dependency chains, or assess milestone readiness. Do not use for roadmap prioritization or issue pool governance.
---

# /vibe-task - RFC / Blocked / Epic 检查与依赖图编排

检查项目中的 RFC、blocked、epic issues 状态，并梳理三类 issue 间的依赖关系。

## 核心原则

- **专注问题 issue**：RFC、blocked、epic
- **基于真源**：只读 shell 输出，不补充字段
- **依赖优先**：梳理依赖链，给出 milestone 可进性判断

## Scope

**只看三类 issue**：

1. **RFC issues** (`roadmap/rfc` label)
   - 需要人类讨论的 issue
   - 目标不明确或需要架构决策

2. **Blocked issues** (`state/blocked` label)
   - 有依赖阻塞的 issue
   - 需要解除阻塞才能继续

3. **Epic issues** (`roadmap/epic` label)
   - scope 过大、需要先拆分的 issue
   - 不可直接执行，需 split 成子 issues
   - 依赖图节点：影响多个 downstream issues 的调度

**依赖图编排**（三类 issue 间的依赖关系）：
- epic → 子 issues（split 产出的依赖关系）
- blocked_by 链（A depends on B depends on C）
- milestone 可进性：某 milestone 是否所有 blocker 已解除

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

### Step 4: 解析 Epic issues

从输出中找出带 `roadmap/epic` 的 issues：

- issue 编号、标题
- 已有的子 issues（从 body 或 comments 中解析 split 产出）
- 是否已触发 split 流程

### Step 5: 依赖图编排

基于上述三类 issue，梳理依赖链：

1. **构建依赖链**：找出 blocked_by 关系，找出 epic → 子 issues 关系
2. **识别根节点阻塞**：依赖链最上游的阻塞点（RFC / epic 未 split）
3. **milestone 可进性**：当前 milestone 的所有候选 issue 是否有未解除阻塞

### Step 6: 输出状态

```text
RFC & Blocked & Epic Issues 检查

RFC Issues (需要人类讨论)
- #123: 架构方向未定
  原因: 需要确认是否使用新框架
  状态: open

Blocked Issues (有依赖阻塞)
- #456: 依赖 #123 完成
  阻塞原因: depends on #123
  状态: blocked

Epic Issues (需要拆分)
- #789: 大功能重构
  已有子 issues: #790, #791
  状态: split in progress

依赖图
- #123 (RFC) -> #456 (blocked) [根节点阻塞：先解决 RFC]
- #789 (epic) -> #790, #791 [split 未完成，milestone 暂不可进]

建议
- RFC: 安排讨论，解除 #123 的 rfc 状态
- Blocked: #123 解除后 #456 自动解锁
- Epic: #789 需完成 split 才能进入调度
```

## 与其他 Skills 的区别

- **vibe-task**: 看 RFC、blocked、epic issues（问题 issue）及依赖图
- **vibe-orchestra**: 管理 assignee issue pool（运行中的 issues）
- **vibe-roadmap**: 版本规划 + 治理审查（Layer 3：消化 governance suggest，纠正 pool 决策）

## Restrictions

- 不做复杂审计或修复
- 不补充 CLI 未提供的字段
- 不处理正常运行的 issue
- 不做版本规划建议

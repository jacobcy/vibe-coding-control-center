---
name: vibe-orchestra
description: Use when the user wants heartbeat-style governance over the issue pool. inspect running issues, judge which issue is worth starting next, backfill assignee-triggered candidates, and propose non-state label or routing actions. Do not use for single-flow execution governance, coding, or implementation work.
---

# /vibe-orchestra - Orchestra Issue Pool Governance

Orchestra 心跳层的 assignee issue pool 治理：查看运行中的 issues，建议下一个值得处理的 issue。

## 核心原则

- **只管 assignee pool**：不处理 broader repo backlog
- **只做建议**：不强制调度，结合人工上下文判断
- **基于真源**：只读 shell 输出和 supervisor materials

## Scope

只回答两类问题（均以 assignee issue pool 为前提）：

1. pool 中现在有哪些 issue 正在运行
2. pool 中接下来哪个 issue 值得优先处理

**不处理**：
- supervisor issue
- broader repo backlog triage
- 单 flow 执行

## Workflow

### Step 1: 查看运行状态

```bash
vibe3 task status
```

必要时查看 orchestra heartbeat：

```bash
vibe3 serve status
```

### Step 2: 补捞候选

找出 assignee pool 中已满足启动条件但尚未调度的 issue：

```bash
gh issue list --assignee <manager-username> --label "state/ready"
```

### Step 3: 判断优先级

参考 `supervisor/governance/assignee-pool.md`，按以下顺序排序：

`milestone -> roadmap/* -> priority/[0-9] -> issue number`

结合当前人工上下文：
- 是否有人已明确接手某个 issue
- 是否有活跃 PR 或 review follow-up
- 是否有收口需求

### Step 4: 提出建议

输出包含：

```text
Running Issues
- #123: in_progress, wt-foo
- #456: blocked, depends on #123

Backfill Candidates
- #789: state/ready, no flow yet

Next Issue
- 建议处理 #789
- 原因：pool 中唯一 ready 且无阻塞

Label Actions (如有必要)
- 建议给 #456 加 dependency label
- 原因：明确依赖关系
```

## Hard Boundary

不负责：
- task registry 审计
- runtime 绑定修复
- roadmap 规划
- issue intake
- 单 flow plan/run/review
- 写代码
- 替代人类做最终业务优先级拍板

## Stop Point

完成治理建议后停止。

不进入执行分配、实现方案或代码修改。
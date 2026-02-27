---
document_type: task
title: Git Workflow & Worktree Lifecycle Standard
status: planning
author: Claude Sonnet 4.5
created: 2026-02-28
---

# Git Workflow & Worktree Lifecycle Standard

## 1. Design (设计方案)

### 核心原则：本地试错 0 成本，远端污染 0 容忍
将版本控制操作分为两个完全隔离的域：
- **行政区（本地 Worktree）**：极度宽松。高频 Commit，允许过程性错误。
- **决议区（远端 & PR）**：极度严格。必须经过 Audit Gate 的全绿报告，由人类执行。

### 模块一：开发域 Commit 规范
- **动作**：Agent 在 Test / Code 闸门中每次让功能或测试跑通（红变绿）后，**必须在当前分支主动发起本地 Commit**。
- **质量**：按 Conventional Commits 规范生成信息（推荐联动 `/vibe-commit` 工具）。
- **目的**：留下细粒度的上下文节点，允许 3 次熔断等原因出错时快速回滚至绿灯状态。

### 模块二：网络通信禁令 (Push 和 PR 禁令)
- **动作**：Agent 执行行政层（Code / Test）代码期间，**严禁使用任何 `git push` 或发起 Pull Request 的指令**。
- **治理**：“我要不要 Push ？”这句话从 Agent 嘴里说出来就是违法。绝对隔离开发分支与远端仓库。

### 模块三：Audit 决议与熔断
- **Audit 失败（打回/重开）**：代码无法挽救、架构设计崩塌时，**立刻废弃当前 Worktree 和分支**，回退到 PRD 和 Spec 层开启全新的沙盒重来。
- **Audit 通过（交付）**：经过人类审查和 Audit Gate 全绿后，人类（或调用专用交付流）执行将当前分支推送到远端 并 创建 PR 指向 `main`。

### 模块四：Post-PR 协议 (彻底的垃圾回收)
- **动作**：推送到远端并完成 PR 创建/合并后，**强制执行本地环境的垃圾回收**。
- **清理对象**：
  1. 杀掉此开发任务对应的独立 Worktree 目录。
  2. 删除对应的本地临时开发分支。
- **目的**：杜绝僵尸树和物理垃圾残留，保持极简无状态工作模式。

---

## 2. Execution Plan (执行计划)

- [x] **Step 1:** 创建标准文档 `docs/standards/git-workflow-standard.md`，将上述 4 个模块详细记录，确保附带 frontmatter。
- [x] **Step 2:** 更新 `docs/prds/vibe-workflow-paradigm.md`，在 Test/Code/Audit Gate 流程说明中，注入以上 Commit 与 Push 的硬规则（如 Code Gate 后需要 Commit，未过 Audit 禁止 Push）。
- [x] **Step 3:** 更新 `.agent/context/task.md` 记录当前任务的执行和变更，作为 Backlog 清理。
- [x] **Step 4:** 若有必要，向 `CLAUDE.md` 补充一条关于“严控 Push 并在本地 Worktree 高频 Commit”的一句话指引，以及指路 `git-workflow-standard.md`。


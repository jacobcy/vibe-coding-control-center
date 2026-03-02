---
document_type: standard
title: Git Workflow & Worktree Lifecycle Standard
status: approved
author: Claude Sonnet 4.5
created: 2026-02-28
---

# Git Workflow & Worktree Lifecycle Standard

> 本文档规范了 Vibe Coding 模式下 Agent 和人类协作时的 Git 与 Worktree 生命周期。秉承 **“本地试错 0 成本，远端污染 0 容忍”** 的核心原则约束所有版本控制行为。

## 1. 核心架构：双域隔离

工作模式被物理切分为两个完全隔离的域：
- **行政区（本地 Worktree）**：极度宽松的环境。Agent 可以高频 Commit，允许过程性错误，方便随时试错和回滚。
- **决议区（远端仓库 & PR）**：极度严格的环境。必须经过 **Audit Gate** 全要素通过后，由人类触发代码和分支流向远端。

## 2. 行为准则与四模块协议

### 模块一：本地高频游击战 (Commit 规范)
Agent 在实现业务逻辑时，禁止“憋大招”。
- **时机**：在 `Test Gate` 与 `Code Gate` 的循环中，只要完成了一个逻辑单元且测试变绿（Green），**必须在当前开发分支上主动发起本地 Commit**（或请求人类运行 `/vibe-commit`）。
- **质量要求**：Commit Info 须严格遵守 Conventional Commits 标准。
- **作用**：记录极其细粒度的上下文历史节点。当触发 “3 次重试失败熔断” 等情况，可以方便地退回上一个绿灯安全点。

### 模块二：网络通信铁律禁令 (Push / PR 禁令)
对于处于 `Code` 层的 Agent 设定绝对红线：
- **动作约束**：未最终通过 Audit Gate 前，Agent **严格禁止**执行任何网络相关的 Git 操作（包括 `git push`、发起 Pull Request 的指令或企图）。
- **认知治理**：“我是否要 push ？”属于 Agent 违法越位。一切进度全凭本地 Commit 固化。绝对物理隔离开发分支与远端主库。

### 模块三：决议与交付 (Audit Gate)
- **拦截与回退（Audit 失败）**：如果 Audit 并未通过（架构严重跑偏、幻觉泛滥），不要试图修修补补——**立刻废弃当前 Worktree 及其开发分支**（人类可直接使用 `vibe flow done` 将沙盒连根拔起）。重回 PRD 或 Spec 层启动新沙盒（`vibe flow start`）。
- **正式交付（Audit 通过）**：当且仅当人类检查了全绿的 AI 审计报告（也可借由 `vibe flow review` 提供的 Checklist 检查）并签署 Approve 后，才正式触发交付流程。此时人类在控制台执行 **`vibe flow pr`** 进入交互式发版流程，由底层辅助负责 Push 以及产生 PR 表单。

### 模块四：物理沙盒清理协议 (Post-PR 回收)
完成 PR 的合并或废弃后，必须彻底清理本地痕迹以确保系统零残留：
- **关联命令**：通过执行控制台命令 **`vibe flow done`** 安全地剥离并拔除当前工作树；并在对话窗口向 AI 呼叫 **`/vibe-done`** 来将挂在 Vibe 大盘（Task Registry）中该任务的状态结算关闭。
- **目标一**：彻底移除此开发任务对应的独立 Worktree 沙盒目录。
- **目标二**：清理本地对应的开发临时缓存信息与无用分支。
- **目的**：杜绝幽灵分支和僵尸树堆积，将环境重置为极简无状态的安全工作模式。

## 3. 分支保护规则 (Branch Protection Rules)

正如 [Vibe Coding 核心信念 (SOUL.md)](../../SOUL.md) 所定义，`main` 分支是项目唯一真源，必须施加严格保护伞。

### 保护目标：`main` 分支

在远端 (GitHub Repository Settings) 强制执行以下规则集 (Rulesets)：

#### 1. 强制 Pull Request 准入
- **合并前需提交 PR** (Require a pull request before merging): 开启。
- **必须获得 Review 批准** (Require approvals): 至少 1 票同意。
- **有新 Commit 需重新 Review** (Dismiss stale PR approvals): 开启。
- **必须解决所有评论/讨论** (Resolve conversations): 开启。

#### 2. 严厉的行为限制
- **禁止强推** (Block force pushes): 开启 (绝不允许篡改 `main` 历史记录)。
- **禁止删除主干** (Block deletions): 开启。

### 实现与变更约束
上述所有保护规则均通过 GitHub Rulesets 在代码托管平台引擎层面落地。
任何试图变更这些规则的行为都需要持有 Admin 系统权限，且所有变动都必须同步更新于本文档中进行审计记录。

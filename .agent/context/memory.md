# Memory

## Shared Memory Source

- current task: `2026-03-02-cross-worktree-task-registry`
- shared source of truth: `$(git rev-parse --git-common-dir)/vibe/tasks/2026-03-02-cross-worktree-task-registry/memory.md`
- registry reference: `$(git rev-parse --git-common-dir)/vibe/registry.json`
- compat layer: 在现有 skills 完成迁移前，`.agent/context/memory.md` 保留为入口索引与迁移说明，不再承载当前 task 的共享 memory 真源。
- local boundary: 当前 worktree 的 `.vibe/` 只保存 focus/session 类缓存，不保存共享 memory 真源。

## 认知对齐目录

本文档记录我们在对话中达成的**概念共识**，而非任务清单。

---

## 2026-03-02: Cross-Worktree Task Registry（共享任务注册表）

### 迁移策略

- 当前仓库的 task registry 真源固定放在 `$(git rev-parse --git-common-dir)/vibe/`。
- 当前 task 的共享 memory 真源迁移到 `$(git rev-parse --git-common-dir)/vibe/tasks/<task-id>/memory.md`。
- `.agent/context/memory.md` 继续作为 pointer/compat 层，避免一次性改动所有依赖 `.agent/context/*` 的 skill。
- 当前 worktree 的 `.vibe/` 只保留可重建的 focus 摘要和 session 缓存，不保留共享 memory 真源。

### 迁移边界

- 已迁移：共享 task registry schema、worktree 绑定模型、当前 task 共享 memory 路径
- 暂未迁移：所有直接读取 `.agent/context/*` 的 skill
- 兼容方式：旧 skill 先读取 `.agent/context/memory.md` 作为入口索引，再逐步切换到共享真源

---

## 2026-02-27: Vibe Workflow Paradigm（开发范式）

### 核心共识

**Vibe Guard 流程**：`PRD → Spec → Execution Plan → Test → Code → AI Audit`

**Vibe Guard 机制**：`Gate 0 Dispatcher → Scope Gate → Spec Gate → Plan Gate → Test Gate → Execution/Code Gate → Audit/Review Gate`

### 关键概念

| 概念 | 定义 |
| ---- | ---- |
| PRD（认知层） | 定目标，人类主导，不含实现方案 |
| Spec（规范层） | 定法律，人类主导 + AI 刺客找茬后锁定 |
| Execution Plan | 圈范围，AI 产出，人类审批，必须有上下文圈定 |
| Test | 锁行为，Spec 为唯一真源，先 Red 再 Green |
| Code | 填实现，AST 约束 + 复杂度熔断 |
| AI Audit | 呈报告，人类签决议，串通检测 |

### 职责分离

- **人类**：立法（PRD/Spec）、审批（Execution Plan）、裁决（Critic/Collusion Report）、签决议
- **AI**：行政（执行、测试、审计）
- **CI**：执法（熔断、阻断）

### Agent 辅助文件目录

| 目录 | 用途 |
| ---- | ---- |
| `docs/prds/` | PRD 文档 |
| `docs/specs/` | Spec 文档 |
| `docs/plans/` | Execution Plan 文档 |
| `.agent/lib/` | Agent/Skill 辅助脚本 |
| `.agent/context/task.md` | 任务状态（已完成 + 待办） |
| `.agent/context/memory.md` | 认知对齐目录（本文档） |

---

## 2026-02-26: 项目基础

### 关键决策

- V2 重建，保持 `lib+bin <= 1200`
- main 已启用分支保护，禁止 force push
- PR #12 曾因主分支历史分叉从 main 消失，后通过 PR #13 恢复

### 规则单一来源

- 原则在 `SOUL.md`
- 项目硬约束在 `CLAUDE.md`
- 执行细则在 `.agent/rules/*`

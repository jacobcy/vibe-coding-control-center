# Memory

## 认知对齐目录

本文档记录我们在对话中达成的**概念共识**，而非任务清单。

---

## 2026-02-27: Vibe Workflow Paradigm（开发范式）

### 核心共识

**六层流程**：`PRD → Spec → Execution Plan → Test → Code → AI Audit`

**四闸机制**：`Gate 0 Dispatcher → Scope Gate → Plan Gate → Execution Gate → Review Gate`

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

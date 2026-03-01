---
document_type: prd
title: Vibe Workflow Paradigm - 开发范式总览
status: approved
author: Claude Sonnet 4.5
created: 2025-01-15
last_updated: 2025-01-24
related_docs:
  - .agent/workflows/vibe-drift.md
  - .agent/workflows/vibe-check.md
  - SOUL.md
  - CLAUDE.md
  - docs/prds/unified-dispatcher.md
  - docs/prds/plan-gate-enhancement.md
  - docs/prds/spec-critic.md
  - docs/prds/collusion-detector.md
  - docs/prds/context-scoping.md
---

# PRD: Vibe Workflow Paradigm - 开发范式总览

> 本文档是 Vibe Coding 开发范式的总 PRD，定义标准开发流程的 Vibe Guard 工作流。

## 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        人类主权区（立法层）                        │
│  ┌─────────┐    ┌─────────┐    ┌──────────────────┐            │
│  │  PRD    │ →  │  Spec   │ →  │ Execution Plan   │            │
│  │ 定目标  │    │  定法律  │    │    圈范围        │            │
│  └─────────┘    └─────────┘    └──────────────────┘            │
│       ↓              ↓                   ↓                      │
│  Scope Gate     Spec Gate          Plan Gate                   │
│  (验证目标)    (验证契约+Critic)   (验证上下文)                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        AI 执行区（行政层）                        │
│  ┌─────────┐              ┌─────────┐                          │
│  │  Test   │    →         │  Code   │                          │
│  │ 先红Red │              │ 后绿Green│                          │
│  └─────────┘              └─────────┘                          │
│       ↓                        ↓                                │
│  Test Gate              Code Gate                              │
│ (验证覆盖率+Red)      (验证Green+复杂度+AST)                     │
│                                                                 │
│  🔴 3次熔断机制：Code 连续 3 次无法让 Test 变绿 → 强制中断      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        人类决议区（执法层）                        │
│  ┌──────────────────────────────────────────────────┐          │
│  │              AI Audit Review                     │          │
│  │  - 目标对齐检查                                   │          │
│  │  - 规范遵守检查（Spec 不变量 100% 覆盖）          │          │
│  │  - 路径一致性检查（按 Plan 执行）                 │          │
│  │  - 架构纯洁性检查（AST + 复杂度）                 │          │
│  └──────────────────────────────────────────────────┘          │
│                          ↓                                      │
│                    Audit Gate                                   │
│          (AI 审计 + Collusion Detector + 人类决议)               │
│                                                                 │
│  🔴 Collusion Detector：检测 AI 编码员和审计员是否串通          │
└─────────────────────────────────────────────────────────────────┘
```

## 总原则（宪法层）

1. **立法与行政分离**：人类主导立法（PRD/Spec/Plan），AI 负责行政（Test/Code），CI 与独立 AI 负责执法（熔断与审计）。
2. **测试先行，机械卡口**：先测试（Red），后代码（Green）。任何阶段不满足条件，CI 直接拒绝，不允许人情绕过。
3. **隔离探索与生产**：允许在沙盒（Spike 分支）中不受限地与 AI 自由对话探索；但一旦进入生产分支，**所有沙盒代码必须抛弃**，严格按本范式重新走线。
4. **人类只对"报告"负责，不对"源码"负责**：放弃肉眼 review 机器代码的执念，用系统和报告来治理系统。
5. **Vibe Guard 流程，层层把关**：每一层文档对应一个 Gate，Gate 不通过则阻断后续流程，确保质量收敛。

---

## Vibe Guard 流程详解

### 第 1 层：PRD（认知层）— 人类主导

**核心问题**：我们要解决什么问题？

**必须输出：**

| 项目 | 说明 | 示例 |
|------|------|------|
| 业务目标 | 核心能力是什么 | "实现 Plan Gate 能读取多种格式的计划文件" |
| 绝对边界 | 不做什么 | "不负责创建计划，不负责框架选择" |
| 核心数据流 | 输入→处理→输出 | "framework 字段 → 路径映射 → 文件内容" |
| 成功判据 | 如何判断成功 | "能正确读取 OpenSpec 和 Superpower 格式" |

**红线：**
- PRD 不完整 → 禁止进入 Spec
- 禁止 AI 过度设计（个人脚本用航母级架构）

**Gate 检查**：Scope Gate → 验证 PRD 完整性（目标/边界/数据流/成功判据）

---

### 第 2 层：Spec（规范层）— 人类主导 + AI 刺客

**核心问题**：系统行为的法律文本是什么？

**必须输出：**

| 项目 | 说明 |
|------|------|
| 接口契约 | 输入/输出/错误定义 |
| 核心不变量 | 任何情况下都必须成立的规则 |
| 边界行为 | 空值、超时、重试机制 |
| 非功能约束 | 性能上限、可观测性 |

**AI 刺客机制（Spec Critic）：**

```
Spec 完成后 → 触发 AI 刺客找茬 → 输出 Critic Report → 人类裁决
                                              ↓
                                    approve → 锁定 Spec
                                    reject → 返回修改
```

**红线：**
- Spec 锁定后，**绝对禁止**为了实现方便反向修改
- 发现不通 → 废弃流程 → 回退 PRD/Spec 重新立法

**Gate 检查**：Spec Gate → 验证 Spec 完整性（接口契约/不变量/边界行为）+ 触发 Spec Critic

---

### 第 3 层：Execution Plan — AI 产出，人类审批

**核心问题**：如何落地？

**必须输出：**

| 项目 | 说明 |
|------|------|
| 上下文圈定 | 需要读取哪些文件（防幻觉） |
| 任务拆分 | 具体到模块/文件/接口的改动点 |
| 风险对策 | 回滚条件、失败处理 |

**上下文圈定要求：**

```markdown
## Context

- lib/flow.sh - 流程控制主逻辑
- lib/utils.sh - 工具函数
```

**红线：**
- 无上下文圈定 → 阻断执行
- PRD/Spec 与 Execution Plan 逻辑不一致 → 打回重做

**Gate 检查**：Plan Gate → 验证上下文圈定存在 + 任务拆分清晰

---

### 第 4 层：Test — AI 编写，Spec 为唯一真源

**核心问题**：如何验证行为正确？

**强制规则：**

| 规则 | 说明 |
|------|------|
| 真理唯一 | 测试断言 100% 来源于 Spec |
| 全面覆盖 | Normal Path + Edge Cases + Error Flow |
| TDD 顺序 | 先 Red（测试必须失败）→ 再 Green（代码让测试通过）|

**红线：**
- 严禁弱化断言、删减边界用例让测试变绿
- 测试未失败（Red）→ 禁止进入 Code 层
- **禁止 Push**：测试阶段仅允许本地操作，严禁将未通过 Audit 的代码 Push 到远端

**Gate 检查**：Test Gate → 验证测试覆盖率 + 断言来源于 Spec + 测试必须失败（Red）

---

### 第 5 层：Code — AI 实现，机械防线锁死

**核心问题**：如何填实现？

**约束机制：**

| 类型 | 约束 | 说明 |
|------|------|------|
| AST 级 | 禁止未经审批引入新依赖 | 防腐 |
| AST 级 | 禁止跨层调用 | 架构纯洁 |
| 复杂度 | 单函数 ≤ 40 行 | 反大泥球 |
| 复杂度 | 圈复杂度 ≤ 10 | 可读性 |

**幻觉熔断机制：**

```
AI 修改代码 → 测试仍失败 → 重试
                ↓
         连续 3 次失败 → 🔴 强制中断
                         ↓
                    人类介入排查
```

**红线：**
- 复杂度超标 → CI 阻断 → 必须拆分重构
- "赶进度"不是绕过理由
- 3 次熔断后仍失败 → 必须人类介入
- **高频 Commit**：测试变绿后，**必须主动本地 commit**（或调用 `/vibe-commit`）留档
- **网络禁令**：本阶段**绝对禁止**任何 `git push` 或发起 PR 的企图

**Gate 检查**：Code Gate → 验证测试通过（Green）+ 复杂度 + AST 约束 + 3次熔断机制 + 本地高频Commit留痕

---

### 第 6 层：AI Audit Review — AI 审计，人类决议

**核心问题**：如何确保主权？整个流程是否出于幻觉？

**审计报告内容：**

| 检查项 | 问题 |
|--------|------|
| 目标对齐 | 代码是否偷换了 PRD 的概念？ |
| 规范遵守 | Spec 不变量是否 100% 测试覆盖且通过？ |
| 路径一致 | 是否严格按 Execution Plan 执行？ |
| 架构纯洁 | AST 与复杂度检查是否全绿？ |

**串通检测（Collusion Detector）：**

```
Spec 不变量 → Code 实现 → Audit 确认
                ↓
         三方对比
                ↓
    Audit 虚假确认 → 🔴 检测到串通 → 阻断合并
```

**人类职责：**
- 拿着审计报告核对
- 重点审查"AI 越权"
- 反思整个需求和代码是否出于幻觉
- **决议通过后**：才允许执行 `git push` 及创建指向 `main` 的 PR
- **Post-PR**：PR合入或废弃后，必须删除相关本地分支和 Worktree 环境

**红线：**
- 任何一项红灯 → 拒绝合并，抛弃当前临时分支和 Worktree
- 串通检测发现作恶 → 重大事故

**Gate 检查**：Audit Gate → AI 审计报告 + Collusion Detector + 人类最终决议 + Post-PR 回收机制

---

## Gate 流程总览

```
/vibe-new <feature>
       │
       ↓
┌──────────────┐
│  Gate 0      │ → 智能调度：选择 OpenSpec 或 Superpower
│  Dispatcher  │    记录到 task.md
└──────────────┘
       │
       ↓
┌──────────────┐
│  Scope Gate  │ → 读取 PRD → 验证目标/边界/数据流/成功判据
│              │    缺失 → 阻断
└──────────────┘
       │
       ↓
┌──────────────┐
│  Spec Gate   │ → 读取 Spec → 验证接口契约/不变量/边界行为
│              │ → 触发 Spec Critic → 人类裁决
└──────────────┘
       │
       ↓
┌──────────────┐
│  Plan Gate   │ → 读取 Execution Plan → 验证上下文圈定/任务拆分
│              │    缺失 → 阻断
└──────────────┘
       │
       ↓
┌──────────────┐
│  Test Gate   │ → AI 编写测试 → 验证覆盖率/断言来源/必须失败(Red)
│              │    未失败 → 阻断
└──────────────┘
       │
       ↓
┌──────────────┐
│  Code Gate   │ → AI 编写代码 → 验证测试通过(Green)/复杂度/AST
│              │ → 3 次熔断机制
│              │    失败 → 人类介入
└──────────────┘
       │
       ↓
┌──────────────┐
│  Audit Gate  │ → AI 审计报告 → 目标对齐/规范遵守/路径一致/架构纯洁
│              │ → Collusion Detector 串通检测
│              │ → 人类最终决议 → Approve/Reject
└──────────────┘
       │
       ↓
    合并/发布
```

---

## 相关 PRD

| PRD | 文件 | 对应能力 |
|-----|------|----------|
| Unified Dispatcher | `docs/prds/unified-dispatcher.md` | Gate 0 智能调度 |
| Plan Gate Enhancement | `docs/prds/plan-gate-enhancement.md` | Spec Gate 多源计划读取与验证 |
| Spec Critic | `docs/prds/spec-critic.md` | Spec Gate AI 刺客找茬机制 |
| Collusion Detector | `docs/prds/collusion-detector.md` | Audit Gate AI 串通检测机制 |
| Context Scoping | `docs/prds/context-scoping.md` | Plan Gate 执行计划上下文圈定 |

**注意**：`plan-gate-enhancement.md` 实际上是 Spec Gate 的实现，命名需要后续统一。

---

## 一句话铁律

> **PRD 定目标，Spec 定法律，Execution Plan 圈范围，Test 锁行为（先红），Code 填实现（后绿），AI Audit 呈报告，Human 签决议。**
>
> **Vibe Guard 工作流，层层把关：Scope Gate → Spec Gate → Plan Gate → Test Gate → Code Gate → Audit Gate**
>
> *（AST 管控依赖边界，复杂度熔断控制腐化，3 次重试失败强制熔断打断 AI 幻觉，Collusion Detector 防止 AI 串通作恶！）*

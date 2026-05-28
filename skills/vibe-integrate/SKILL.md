---
name: vibe-integrate
description: Use when the user wants to assess, unblock, and merge PRs. This is a human-facing convergence entrypoint that explains integration status and guides decisions, not an automated merge workflow.
---

# /vibe-integrate - Human-Facing Convergence Entrypoint

该技能是人机协作的 PR 整合入口，负责解释当前状态、判断阻塞项、确认下一步。

## Core Principle: Human-Facing Interaction Only

**`vibe-integrate` 只负责人机交互**：
- 解释当前 PR / CI / review / flow 现场
- 判断阻塞项与 merge readiness
- 和用户确认下一步（等待、补证据、进入 merge、拆 follow-up）
- 提供对不同 evidence 来源的统一解释
- 明确停点与下一步建议

**`vibe-integrate` 不承担的职责**（由基础设施承接）：
- 不定义 merge readiness policy
- 不定义 review evidence 是否足够的语义
- 不定义 CI 是否通过的判断标准
- 不独自作为 merge/readiness policy 的隐式真源

这些集成语义由 `vibe3 pr`、`vibe3 flow`、CI 系统等基础设施承接。

## Semantic Boundary

- **vibe-integrate**: 人机收敛入口（解释、判断、确认）
- **vibe3 pr/flow**: PR 与 flow 状态基础设施
- **vibe3 review**: Review evidence 基础设施
- **CI systems**: CI/checks 状态真源
- **vibe-done**: PR 合并后的终态清理入口

## Integration Contract Layer

底层基础设施应提供统一能力（供 `vibe-integrate` 消费）：
- PR 状态与链接事实
- CI / checks 状态事实
- Review evidence 事实
- Flow/handoff 当前阶段信息
- Merge readiness / blocked reason 的基础判定材料

这些能力由 `vibe3` CLI、`gh` CLI、CI 系统等提供，`vibe-integrate` 只负责解释和确认，不重新定义语义。

## Human-Facing Workflow

该 workflow 只描述人机交互步骤，不隐含自动化执行链语义。

### Step 1: Establish Integration Context

优先读取基础设施提供的事实：

```bash
vibe3 flow show
vibe3 task status
```

确认：
- 当前要处理哪些 PR
- 哪些 PR 是独立的，哪些是 stacked
- 哪些 flow 已经进入 `open + had_pr` 状态

### Step 2: PR Review Status Assessment (Tiered)

**根据 PR 类型选择审核策略**：

#### Simple Scenarios (Fast Track)

满足以下任一条件，跳过 review evidence 要求：
- 纯文本修改（README、文档、注释）
- 配置调整（.gitignore、.editorconfig）
- 非逻辑性变更（格式化、重命名）

直接进入 Step 3。

#### Complex Scenarios (Full Flow)

涉及以下任一条件，必须有 review evidence：
- 代码逻辑修改
- 架构调整
- 安全相关变更

检查：
- 在线 Codex/Copilot review 状态
- 无在线 review → 等待或触发 `@codex` comment
- 备选：`vibe3 review base`

### Step 3: Assess Merge Conditions

判断合并条件（基于基础设施事实）：
- CI 是否通过
- Review evidence 是否存在（复杂场景）
- 是否触发总量 / 单文件 LOC 超限
- 阻塞性 review threads 是否已处理
- Merge base / stack 顺序是否正确

**LOC 超限场景**（额外质量门）：

满足以下任一条件，除了 review evidence，还必须做一轮代码质量复查：
- 当前分支会让核心代码总量超过 `config/v3/loc_limits.yaml` 阈值
- 某个单文件超过 LOC 限制

复查目标：
- 是否存在明显可回收的坏味道
- 是否有业务逻辑越界或职责漂移
- 是否只是因为合理聚合导致总量上升

### Step 4: Handle Blockers

和用户确认阻塞项处理方案：
- 修复 CI 或 review 阻塞问题
- 处理 LOC 超限后的质量收口
- 推送并重新检查状态
- 只修当前 PR 的 follow-up

### Step 5: Merge in Order

确认合并顺序（stacked PR 场景）：
- CI 通过
- Review evidence 存在（复杂场景）
- 阻塞性 review 已处理
- 堆叠上游已先合并

### Step 6: Write Handoff

记录本轮整合决策：

```bash
vibe3 handoff append "vibe-integrate: <summary>" --actor vibe-integrate --kind milestone
```

若 handoff 与当前真源不一致，必须在退出前修正。

## Minimal Stop Points

该 skill 的最小停点：
- Waiting for CI
- Waiting for review evidence
- Merge-ready with explanation
- Blocked with explicit reason
- Follow-up issue required

## Integration Evidence Sources

Review evidence 可以来自：
- 在线 Codex/Copilot review
- `vibe3 review base` 本地 review
- 人工 review
- 外部审查结果

`vibe-integrate` 负责统一解释这些 evidence，但不定义"哪种 evidence 更权威"的语义。

## Design Principles

1. `vibe-integrate` 只负责人机交互，不定义 merge/readiness policy
2. 底层集成语义由基础设施承接
3. 不同 evidence 来源平等，由用户和下游 workflow 决定采纳
4. Handoff 记录决策，不作为业务真源

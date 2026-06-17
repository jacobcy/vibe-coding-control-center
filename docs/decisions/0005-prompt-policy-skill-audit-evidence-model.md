---
document_type: decision
title: Prompt/Policy/Skill 审计证据模型
adr_id: 0005
status: proposed
date: 2026-06-17
supersedes: null
superseded_by: null
related_docs:
  - docs/standards/v3/audit-evidence-model-standard.md
  - docs/standards/v3/database-schema-standard.md
  - docs/standards/v3/event-driven-standard.md
  - docs/standards/v3/skill-standard.md
  - docs/standards/v3/skill-trigger-standard.md
  - supervisor/roadmap-common.md
issues:
  - 2946
  - 2947
  - 2948
  - 2949
  - 2950
  - 2952
  - 2953
  - 2954
  - 2956
  - 2957
---

# Prompt/Policy/Skill 审计证据模型

## Context

Vibe 的治理重心正在从代码层稳定性上移到 prompt、policy、material、skill 和跨项目运行质量。远端运行现场已经产生大量可用信号：

- issue body 与 comments，包括 roadmap intake、assignee-pool、roadmap decision 等治理评论
- flow timeline、flow state、handoff refs 与角色输出 artifact
- PR body/comments、git commit window 与 review gap
- dry-run rendered prompt、recipe variant、section provenance 与 prompt hash
- skill 执行留痕和 claude-mem 中的历史运行观察

这些材料分散在不同 issue-flow-PR 循环里。若审计 agent 每轮直接读取原始材料，会出现三个失败模式：

- **不可收敛**：flow A 得出一个结论，flow B 得出另一个结论，缺少跨样本聚合面。
- **prompt 膨胀**：每个失败案例都变成一段新规则，prompt/material 越写越长。
- **真源混淆**：本地开发 DB、远端 production telemetry、GitHub comments、claude-mem memory 的可信度不同，不能混为同一层证据。

SkillOpt 可借鉴的关键不是直接移植训练框架，而是保留 trajectory 到反思、聚合、选择、受控更新、验证 gate 的分层闭环。Vibe 需要先把这个思想映射到自身的运行真源和治理角色上。

## Decision

采用分层审计证据模型，将 Prompt/Policy/Skill 审计链路拆成稳定的四段：

```yaml
raw evidence -> observation -> suggestion -> decision
```

四层语义分别为：

1. **Raw evidence**：GitHub issue/PR、flow timeline、handoff artifact、git commit diff、dry-run prompt provenance、skill 留痕、claude-mem memory 等原始材料。
2. **Observation**：由 Observation Collector 从原始材料提炼出的结构化观察。单个 flow 只能产生 observation，不能直接产生全局 prompt/policy 修改结论。
3. **Suggestion**：由 Prompt/Governance Auditor 基于多个 observation 聚合出的 hypothesis 或修正建议。suggestion 必须带目标层级、证据强度、风险和预期指标。
4. **Decision**：由 human、vibe-task、roadmap decision 或后续专门 decider 对 suggestion 做采纳、拒绝、hold、split 或要求更多证据的决策。

确立两个新增角色边界：

- **Observation Collector**：负责 raw evidence -> observation。可纳入现有 governance material rotation，也可手动 dry-run；每轮只采样少量未观察过的 flow，并通过 source watermark 避免重复观察；不产出 suggestion 或 decision。
- **Prompt/Governance Auditor**：负责 observation -> suggestion。读取 observation ledger 和有限抽样 refs，不直接扫全量原始材料；不直接修改 prompts、skills、supervisor materials 或 state labels。

claude-mem 纳入审计模型，但只作为 `memory_signal` 类补充来源。memory-derived observation 必须记录 memory id、query、项目/平台、时间范围和 staleness；它可用于 recurrence/corroboration，不可单独作为决策真源。

关键权衡：

- ✅ 稳定观察面让审计 agent 不必反复读取庞大原始材料。
- ✅ observation/suggestion/decision 分层防止单个失败案例直接污染全局 prompt。
- ✅ source watermark 和采样上限让审计可以持续运行，而不是一次性大扫描。
- ✅ claude-mem 的历史价值被纳入，但不会覆盖 repo/DB/GitHub 真源。
- ❌ 需要新增持久层和角色执行路径，复杂度高于一次性报告脚本。

## Consequences

正面影响：

- 审计闭环可以从“读散乱材料给建议”升级为可追踪、可去重、可复核的数据链。
- Prompt/Policy 修正必须经过 observation 聚合和 suggestion 选择，降低 prompt bloat 风险。
- 远端 production telemetry、本地开发 DB、GitHub comments、claude-mem memory 的可信度边界清晰。
- 后续效果评估可以绑定 suggestion、decision 和变更 PR，形成真正的改进闭环。

负面影响：

- 需要引入新的 ledger schema 或等价持久层。
- governance rotation 中会新增审计材料，必须控制频率和单轮样本量。
- 观察面过窄会漏掉系统性问题；观察面过宽又会重新制造上下文膨胀。

风险：

- 如果 Observation Collector 不做 watermark，会反复观察同一批 flow，造成重复结论。
- 如果 Prompt/Governance Auditor 绕过 observation ledger 直接读取全量原始材料，会回到不可收敛状态。
- 如果 suggestion 未经过 decision/gate 就自动改 prompt/material，会把噪声固化进运行层。

## How

**硬约束：本段只放链接，禁止复制实现细节。**

相关实现和操作流程见：

- [Issue #2947](https://github.com/jacobcy/vibe-coding-control-center/issues/2947) — Prompt/Policy/Skill 审计证据模型 RFC
- [Issue #2956](https://github.com/jacobcy/vibe-coding-control-center/issues/2956) — Observation Ledger 与 Observation Collector
- [Issue #2957](https://github.com/jacobcy/vibe-coding-control-center/issues/2957) — Suggestion Ledger 与 Prompt/Governance Auditor
- [Issue #2952](https://github.com/jacobcy/vibe-coding-control-center/issues/2952) — 失败聚类与根因映射报告
- [Issue #2953](https://github.com/jacobcy/vibe-coding-control-center/issues/2953) — suggestion 到 decision/反哺机制
- [Issue #2954](https://github.com/jacobcy/vibe-coding-control-center/issues/2954) — 改进效果评估与二次迭代机制
- [docs/standards/v3/audit-evidence-model-standard.md](../standards/v3/audit-evidence-model-standard.md) — 审计证据 bundle schema 与来源可信度标准
- [docs/standards/v3/database-schema-standard.md](../standards/v3/database-schema-standard.md) — SQLite schema 标准
- [docs/standards/v3/event-driven-standard.md](../standards/v3/event-driven-standard.md) — runtime event 与 projection 标准
- [supervisor/roadmap-common.md](../../supervisor/roadmap-common.md) — governance suggest / roadmap decision 语义边界

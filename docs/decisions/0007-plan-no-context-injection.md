---
document_type: decision
title: Plan Prompt 不预注入上下文 — Agent 自用工具收集
adr_id: 0007
status: accepted
decides: "plan prompt MUST NOT 预注入 spec_ref 正文或长期记忆检索结果；自动化 plan 只允许通过 issue body 注入已明确任务；spec / memory / ADR 上下文由 agent 在 plan 阶段按 supervisor/policies/plan.md 自行调用 spec-kit / graphify / mem-search / context7 工具收集，禁止 code 层 subprocess 预填。"
scope:
  - src/vibe3/roles/plan.py
  - src/vibe3/agents/plan_prompt.py
  - supervisor/policies/plan.md
  - supervisor/policies/review.md
date: 2026-07-07
supersedes: null
superseded_by: null
related_docs:
  - .specify/specs/012-spec-handoff-bridge/spec.md
  - supervisor/policies/plan.md
  - supervisor/policies/review.md
  - skills/vibe-adr-recall/SKILL.md
issues:
  - 3333
---

# Plan Prompt 不预注入上下文 — Agent 自用工具收集

## Context

PR #3319（spec 012 US4）在 `_build_plan_task_guidance`（`src/vibe3/roles/plan.py`）中引入了预注入：plan prompt 被预填 spec_ref 正文（via `SpecRefService`）+ claude-memory 检索结果（via `claude-memory smart-search` subprocess）。原意是让自动化 planner 稳定消费已有 spec/ADR/记忆。

实践暴露问题：

- **全自动化效果不好**：把 spec/memory 预注入 prompt，等于让自动化"自己完成 spec 消费"，但 plan 阶段真正需要的是 agent 基于最新 issue/spec/仓库事实做判断，预注入内容易 stale、且与 agent 自身工具收集重复。
- **职责错位**：plan prompt 应承载"任务是什么"（issue body），而非"上下文是什么"。上下文收集是 agent 的职责，应由 policy 指示、agent 用工具完成。
- **工具边界混乱**：code 层调 `claude-memory` subprocess 绕过了项目工具规范（无 `claude-memory` CLI，应走 `/mem-search` skill 3-layer）；spec_ref 读取应走 `vibe3 handoff show @spec`。
- **与 review 闭环重叠**：spec 完成度对账已由 reviewer 承担（review policy §0f，#3329），plan 阶段再注入 spec 正文 + blocker 属于越位。

用户架构指令（2026-07-07）：

- plan prompt 不直接注入 spec_ref / memory
- agent 本身应通过 spec-kit / graphify / claude-mem 工具主动收集上下文，然后 plan
- 自动化工作流（plan/execute/review）适用于 **spec 已明确的任务**，通过 **issue body** 注入；不该让自动化"自己完成 spec"
- 全权委托自动化已实践，效果不好

## Decision

plan prompt 的 code 层预注入被移除，改为 agent 工具收集模型：

1. **plan prompt MUST NOT 预注入 spec_ref 正文**：`_build_plan_task_guidance` 不再读 `flow.spec_ref`、不再调 `SpecRefService.get_spec_content_for_prompt`。agent 通过 `vibe3 handoff show @spec` 自行读取已登记 spec（policy 指示）。
2. **plan prompt MUST NOT 预注入长期记忆**：移除 `claude-memory smart-search` subprocess。agent 通过 `/mem-search` skill（3-layer：search → timeline → get_observations）按需查询（policy 指示）。
3. **只允许 issue body 注入**：issue body 是自动化的合法注入通道（任务已明确）。`_build_plan_task_guidance` 保留 issue title + body 注入。
4. **ADR recall 仍由 policy 指示**：`vibe-adr-recall` skill 在 plan 阶段产出 `ADR Consideration` artifact（FR-020），不受本决策影响 — 它本身就是 agent 工具，非 code 预注入。
5. **reviewer 承担 spec 完成度对账**：plan 不再在 prompt 里 surfacing "Spec BLOCKED"；unreadable spec_ref 由 reviewer 在 review 阶段经 `vibe3 inspect base --json` actual diff + spec requirements 对账（review policy §0f，#3329）。

不 supersede ADR-0006：0006 是 spec artifact 与 handoff 统一契约（spec 必须是仓库 artifact、ref 契约），仍然有效。本 ADR 只约束 plan prompt 的构造方式，与 0006 正交。

## Consequences

**正面**：

- plan prompt 保持最小（issue body only），agent 基于最新事实判断，避免 stale 预注入。
- 职责清晰：code 承载任务，policy 指示上下文收集，agent 用工具执行。
- 工具规范对齐：mem-search 3-layer 替代 `claude-memory` subprocess；spec 读取走 handoff 命令。
- 与 review 闭环解耦：plan 不越位 surfacing spec blocker，reviewer 统一对账。

**负面 / 成本**：

- plan agent 必须主动调工具，依赖 policy 跟随；工具不可用时 agent 须自行报告证据限制（不再由 code 兜底注入 "Evidence Limitation" 段）。
- 若 agent 跳过上下文收集，plan 质量下降 — 由 review 阶段 spec 完成度对账（§0f）+ ADR 合规 gate（§0e）兜底。

**风险**：

- agent 不遵循 policy → plan 漏 spec/ADR 约束。缓解：review §0e/§0f 对账 + vibe-adr-recall skill 强制产出 artifact。

## How

**硬约束：本段只放链接，禁止复制实现细节。**

相关实现和操作流程见：

- [supervisor/policies/plan.md](../../supervisor/policies/plan.md) — §主动收集上下文（agent 工具：mem-search / graphify / context7 / exa）
- [supervisor/policies/review.md](../../supervisor/policies/review.md) — §0e ADR Reconciliation + §0f Spec Completion Reconciliation
- [skills/vibe-adr-recall/SKILL.md](../../skills/vibe-adr-recall/SKILL.md) — plan/review 阶段 ADR Consideration artifact
- [.specify/specs/012-spec-handoff-bridge/spec.md](../../.specify/specs/012-spec-handoff-bridge/spec.md) — spec 012 US4（FR-019/021 已同步修订）
- [RFC issue #3333](https://github.com/jacobcy/vibe-coding-control-center/issues/3333) — 原始问题讨论

# ADR 体系设计：RFC → ADR → Standards 闭环

- 关联 issue: #2015（[Discussion] ADR 治理体系设计）
- 状态: Design（已批准进入 planning）
- 日期: 2026-06-04
- 作者: Claude Opus 4.8（人机协作）

## 目标 (Goal)

为项目补上一个**缺失的中间环节**：跨任务、长期有效的**架构决策理由**（"为什么这样设计"）的耐久记录，并把它接入已有的 RFC / roadmap 治理闭环，形成"生成 → 消费"闭环。

约束：纯文档 + 约定，**零 Python 代码、零 CI 门禁、不动现有 33 个 standards 物理结构**，符合 SOUL §0（单一事实 + 渐进披露）、HARD RULE 4（最小变更）、15（复用优先）、16（Skill-First）。

## 问题 (Problem)

现有文档体系是**任务中心**的：`PRD → Spec → Execution Plan → Test → Code → Audit`（见 [cognition-spec-dominion.md](../../standards/cognition-spec-dominion.md)），覆盖"单个 issue 怎么做"，但没有承载"为什么选 Protocol DI / 为什么用 Domain Events"这类**跨任务、长期有效的架构选型理由**的真源。

更关键的是：项目已有一条 RFC/roadmap 治理闭环，但其中的**决策是易失的**：

- "RFC" 不是文档，是 issue 标签 `roadmap/rfc`（语义="需人类设计决策"）。
- 决策当前以 `[roadmap decision]` / `[decision]` **评论 + `.agent/context/memory.md` 本地缓存**形式存在。
- 后果：架构级决策与日常 triage 决策（"intake completed" / "close"）混在同一 marker，**无法区分、无法索引、无 supersede 链**，PR/issue 关闭后理由蒸发。

"为什么"其实已零散存在（[docs/design/blocked-state-architecture.md](../../design/blocked-state-architecture.md)、[docs/standards/v3/](../../standards/v3/) 下的 `*-philosophy.md`），缺的是**统一入口、索引、不可变生命周期，以及与治理闭环的接线**，而非"完全没有地方写"。

## 生命周期模型 (Lifecycle Model)

本设计的概念核心：**按生命周期/可变性给文档定位**，三层各司其职、内容禁止重叠。

| 层 | 是什么 | 生命周期 | 载体 | 维护者 |
|---|---|---|---|---|
| RFC | 问题 / 待决策 | 前瞻、易失 | `roadmap/rfc` 标签 + issue | vibe-roadmap / vibe-task |
| ADR | 为什么 / 决策了什么 | 正文语义不可变、可 supersede | `docs/decisions/`（新增） | 人类决策时结晶 |
| Standards/v3 | 怎么做 / 当前现状 | living、持续更新 | `docs/standards/` | 趋向 supervisor 维护 |

- **生成**：`roadmap/rfc` issue → 人类决策 → 结晶为 ADR（耐久"为什么"）→ 更新 standards（"怎么做"）。
- **消费**：读 standards（现状）→ 溯 ADR（为什么这样）→ 溯 RFC issue（原始问题 / 被否的备选）。

> "standards 由 supervisor 动态维护"是目标态（现状治理材料 intake/pool/cron 并不维护 standards）。无论是否实现，设计含义一致：**ADR 必须独立于 living 区，因为它的决策正文不可变**。让 standards 真正 supervisor-maintained 列为独立 follow-up，不在本轮。

## 决策 (Decision)

采纳一个**薄决策层 + 链接式**的 ADR 体系，并把它接入 RFC/roadmap 闭环的生成侧与消费侧。ADR 只记"为什么 + 决策了什么"，"怎么做"靠链接复用现有 standards/design/philosophy。

## 组件设计

### 1. ADR 载体（4 个文件）

- `docs/decisions/NNNN-kebab-title.md`：4 位**顺序号**（如 `0001-adopt-adr-loop.md`）。顺序号而非日期，以支持 supersede 链。
- `docs/decisions/INDEX.md`：决策总表（ID / 标题 / 状态 / 日期 / 取代关系 / 关联 standard）= 发现入口 + supersede 链追踪点。
- `docs/decisions/_template.md`：Nygard-lite 模板。
- frontmatter 字段：

```yaml
---
document_type: decision          # 新增 doc_type
title: <标题>
adr_id: 0001
status: accepted                 # proposed | accepted | superseded | deprecated
date: 2026-06-04
supersedes: null                 # 取代的 adr_id（如 0003）
superseded_by: null              # 被哪个 adr_id 取代
related_docs:                    # → 承载"怎么做"的 standard/design/philosophy
  - docs/standards/client-boundaries.md
issues: [2015]                   # → 来源 RFC issue
---
```

- 正文 4 段：**Context（为什么要决策）→ Decision（决策了什么，核心一句）→ Consequences（正负权衡 + 约束了后续什么）→ How（只放链接，禁复制实现细节）**。

### 2. 边界铁律（防重复，守 SOUL §0）

- ADR 写**为什么 + 决策了什么**（决策正文不可变）；Standards/design/philosophy 写**怎么做**（可变）；RFC 是 GitHub 信号，不入库。
- ADR 的 `## How` 段**只放链接，禁止复制实现细节** ← 防重复的硬约束。
- 现有 `v3/*-philosophy.md` 视为"已存在的胖 ADR"：**不搬家、不强制迁移**；新 ADR 用 `related_docs` 链过去；将来下次触碰时再把其中决策理由瘦身为反链。

### 3. 生成侧：RFC → ADR 结晶（独立小 PR，issue comment 指向 PR）

矛盾：vibe-task/vibe-roadmap 处理的是 GitHub RFC 决策，而 ADR 是仓库文件、必须经 PR 落地。把 ADR 托付给后续功能 PR "顺手写"不稳定，容易让 RFC 评论已经结论化、但 durable ADR 长期缺失。

解法是：**RFC 决策本身触发一个小型 ADR PR**。skill 在 issue comment 中写明"采纳并形成 ADR 决议"，随后通过正常 git/PR 流程创建只包含 ADR 文件、INDEX 更新和必要 standards 链接的窄 PR，并回到原 RFC issue comment 指出该 ADR PR。ADR PR 合并后，RFC 才算 durable resolved。

- 架构级判据（三条全满足才结晶）：① 跨任务/跨模块的架构选型；② 有真实权衡或反直觉；③ 期望跨 PR/issue 长期有效。
- 非架构级 rfc（绝大多数）→ 维持 `[decision]` 评论，**不产 ADR，流程不变**。
- ADR PR 范围：新增 `docs/decisions/NNNN-*.md`、更新 `docs/decisions/INDEX.md`，必要时只加最小 standards/design 链接；禁止混入实现代码或大范围文档迁移。
- issue comment 必须包含 ADR PR 链接，例如：`[decision] 采纳并形成 ADR 决议；ADR PR: <url>; [reason] <理由>`。
- 效果：rfc 的"终点"从"悬浮在 GitHub"变成"**一个可审、可合并、可追溯的小 ADR PR**"。这比要求后续实现 PR 顺手写 ADR 更稳定。

挂载点：vibe-task `Step 2.2 方案1（采纳并推进）`、vibe-roadmap `rfc override / Step X` 分支。

### 4. 消费侧：plan / task / roadmap 决策时必查 ADR（纯 policy，无 CI 门禁）

- **`supervisor/policies/plan.md`**（plan mode 真源）：在"上下文圈定"阶段加一步——**计划前先查 `docs/decisions/INDEX`，再读取相关 `accepted` ADR 正文；新计划不得违反当前有效 ADR；要偏离必须显式提议 supersede，而非偷偷违反**。
- **vibe-task**（处理 rfc）：决策前先查相关 ADR，避免 re-litigate 或与既有决策矛盾。
- **vibe-roadmap**（roadmap 审查）：规划 / intake 判断参考既有架构决策。

> 这是在"长期记忆"基础上叠加的 plan-time 主动消费（仅在 plan/triage 检查点查，**不做 code-time 注入、不做 CI 门禁**），守住"不上审计门禁"的底线。

### 5. Supersede 机制（"保持现状"）

ADR 的决策正文不可变，但 **supersede 链反映当前生效决策**——这正是 standards(living, 当前 HOW) 之外，ADR 反映"当前 WHY"的方式：

- 新 ADR `supersedes: N`；旧 ADR 的生命周期 metadata 可转为 `status: superseded` + `superseded_by: M`，但旧 ADR 正文不得重写。
- INDEX 永远可见"当前有效"决策；历史决策保留可追溯，不删除、不改写。

### 6. 治理登记（让模型成为权威）

- **SOUL.md §0 文档职责分工表** +1 行「决策文件 (ADR)」：可写 为什么/权衡/决策记录；不能写 实现细节/操作流程。（fallback：放 doc-organization.md）
- **[governance-roadmap-closed-loop.md](../../governance/governance-roadmap-closed-loop.md)**：把 ADR 写入闭环作为"决策耐久化"环节——这是闭环文档，ADR 的概念家。
- `doc-organization.md`（目录结构 + 命名）、`docs/README.md`（入口）、`CLAUDE.md「参考」`、`AGENTS.md` 各 +1 行指针；`glossary.md` 加 "ADR / 架构决策记录" 词条。
- `.github/PULL_REQUEST_TEMPLATE.md` 加可选 `Related ADRs:` 行。
- **不碰** supervisor 注入 / 审计角色 / CI。

## 本轮落地范围 (Scope)

1. `docs/decisions/` 骨架：`INDEX.md` + `_template.md`。
2. **ADR-0001 = "采纳 RFC→ADR→Standards 闭环"**（本决策，源自 issue #2015）—— dogfood，引入体系的 PR 第一份内容就是描述它自己。
3. **ADR-0002 = Protocol-based DI**（读 PR #2014 / issue #1884 / `protocols.py` 写实际内容，第二个范例）。
4. 组件 §3 的结晶约定 → 加入 vibe-task + vibe-roadmap：架构级 RFC 直接推动小型 ADR PR，并在 issue comment 指向该 PR。
5. 组件 §4 的消费约定 → 加入 supervisor/policies/plan.md + vibe-task + vibe-roadmap。
6. 组件 §6 的治理登记。
7. 历史决策（Domain Events / 3-Tier / Orchestra）→ INDEX 列为 backlog 指针，**不补写**。
8. 结论回帖 issue #2015。

## 明确不做 (Non-goals / YAGNI)

- Tier-3 `.claude/rules/` 注入 / supervisor 审计角色 / CI 门禁。
- review/run policy 的 ADR 合规校验（一旦"验证 PR 是否违反 ADR"即滑向审计门禁）→ 独立 follow-up。
- 33 个 standards 物理重排 / 迁移 design 文档。
- standards 的 supervisor 自动维护机制 → 独立 follow-up issue。

## 相关清理：CLAUDE.md policies 路径修正

设计调研中发现 `CLAUDE.md` 有 5 处引用 `.agent/policies/`，但该目录不存在、无同步逻辑；V3 权威配置（`config/v3/settings.yaml` `policies_root: supervisor/policies`、`adapters/vibe_center.py`）与全局安装均以 `supervisor/policies/` 为真源。本轮顺手将 CLAUDE.md 5 处 `.agent/policies/` 修正为 `supervisor/policies/`。

> 残留同类陈旧引用（`lib/profiles.sh:95` 的 `paths.policies_root:.agent/policies`、`lib/init.sh:452` 的提示文案）属 V2 Shell 代码，超出本次文档修正范围，建议单独 issue 处理。

## 验证 (Acceptance)

- `docs/decisions/INDEX.md` 列出 ADR-0001、ADR-0002，状态正确。
- ADR-0001/0002 正文符合模板，`How` 段只含链接、无实现细节复制。
- vibe-task / vibe-roadmap / supervisor/policies/plan.md 含生成与消费约定文字：生成侧为小型 ADR PR，消费侧读取相关 ADR 正文。
- SOUL §0 表 + governance-roadmap-closed-loop.md + 各入口文件含 ADR 登记/指针。
- CLAUDE.md 无 `.agent/policies/` 残留（`grep -n '.agent/policies' CLAUDE.md` 为空）。
- 零 Python 代码改动；pre-commit 全绿。

## 开放问题 (Open Questions)

无。三个核心决策（核心目标=长期记忆+追溯；边界=薄决策层+链接；范围=立模型+落 ADR+RFC→ADR 约定）及两个细节（ADR-0001=dogfood、架构级 rfc 直接生成小型 ADR PR）均已确认。

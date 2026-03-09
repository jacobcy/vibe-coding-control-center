---
title: "Vibe Skill Governance Design"
date: "2026-03-09"
status: "draft"
author: "Codex GPT-5"
related_docs:
  - docs/standards/skill-standard.md
  - docs/standards/command-standard.md
  - docs/standards/shell-capability-design.md
  - docs/standards/git-workflow-standard.md
  - docs/standards/worktree-lifecycle-standard.md
  - docs/standards/glossary.md
  - docs/standards/action-verbs.md
  - skills/vibe-task/SKILL.md
  - skills/vibe-check/SKILL.md
  - skills/vibe-roadmap/SKILL.md
---

# Vibe Skill Governance Design

## Goal

创建一个专属的 `vibe-skill`，用于服务本项目自有 Vibe Skills 的创建、更新、审查与漂移提醒。

它必须满足三条硬约束：

1. skill 不直接操作共享真源，只能通过 `bin/vibe ...` 或其他合法 shell 能力层命令完成写入。
2. skill 的术语、动作词、命令语义、flow 生命周期语义必须引用 `docs/standards/*` 真源，而不是在 skill 内自定义第二套解释。
3. 当标准文件已更新、而 skill 未同步时，必须能明确提醒“引用缺失”或“可能漂移”。

## Non-Goals

- 不在本轮设计里直接改现有 `skills/vibe-*`。
- 不把 `vibe-skill` 做成新的 shell 命令域。
- 不让 `vibe-skill` 代替 `skill-creator` 的通用能力；它应是 Vibe 项目内的受限包装层。
- 不在 skill 层做自动修复共享真源的“暗箱事务”。

## Current Findings

### 已确认的边界真源

- `docs/standards/command-standard.md` 已明确 `vibe roadmap`、`vibe task`、`vibe flow`、`vibe check` 的命令语义与层级分工。
- `docs/standards/shell-capability-design.md` 已明确 shell 只提供原子能力，skill 不得直接写共享真源。
- `docs/standards/git-workflow-standard.md` 与 `docs/standards/worktree-lifecycle-standard.md` 已分别定义交付 flow 和物理 worktree 生命周期，不应由 skill 重写。

### 当前 skill 体系的明显问题

1. 多数现有 `vibe-*` skill 没有系统引用 `docs/standards/*`，漂移风险高。
2. 现有 `skills/vibe-skills/SKILL.md` 的职责是“skills 生命周期管理”，不是“Vibe skill 设计审查器”，不宜继续叠加职责。
3. `skills/vibe-task/SKILL.md`、`skills/vibe-check/SKILL.md`、`skills/vibe-roadmap/SKILL.md` 都写了自己的边界说明，但多数没有把标准文件当显式引用真源。
4. 当前仓库中存在历史上关于 `vibe skill` / `vibe skills` 的旧表述，后续新 skill 需要主动避免再次混淆 shell 命令、skill、本地源码、运行时链接四个层次。

## Recommendation

推荐创建一个新的独立 skill：`skills/vibe-skill/`。

理由：

- 它和现有 `vibe-skills` 不是同一职责。前者是“Vibe 自有 skill 的创建与治理”，后者是“已安装 skills 的生命周期管理”。
- 它天然需要双模式：`create/update` 与 `review/audit`。这适合放进一个受限治理 skill，而不是散落到多个文档约定里。
- 它应该显式复用 `skill-creator` 的方法，但收紧为 Vibe 项目专用规则：真源边界、标准引用、命令真实性、flow 生命周期对齐。

## Alternative Approaches

### 方案 A：扩展现有 `vibe-skills`

优点：

- 少一个 skill 目录。

缺点：

- 会把“安装/同步/推荐第三方 skills”和“审查 Vibe 自有 skill”混成一层。
- 继续放大会让 `vibe-skills` 变成超大入口，不符合渐进披露。

结论：不推荐。

### 方案 B：创建独立 `vibe-skill`

优点：

- 职责清晰，可把 create/review 都收敛在同一治理 skill 内。
- 方便定义专属引用清单、审查清单和漂移提醒规则。

缺点：

- 需要新增一个 skill 目录与少量参考文件。

结论：推荐。

### 方案 C：拆成 `vibe-skill-create` + `vibe-skill-review`

优点：

- 触发更精确。

缺点：

- 当前范围偏早拆分。
- 两个 skill 会共享大量重复规则，维护成本更高。

结论：现阶段不推荐，除非后续审查流程显著复杂化。

## Proposed Responsibility

`vibe-skill` 应只做四类事：

1. 为新 Vibe skill 生成受限设计框架。
2. 审查现有 Vibe skill 是否越权、是否引用真源、是否误述命令或生命周期。
3. 检查 skill 中提到的 `vibe` shell 命令是否真实存在、参数是否真实可用。
4. 检查 skill 所依赖的标准文件是否已更新，若 skill 未显式引用或内容可能过期，则发出提醒。

## Required Review Checklist

每次创建或审查 skill，至少要回答以下问题：

### 1. 真源边界

- 是否直接读取或修改 `.git/vibe/*.json`？
- 是否把 `.agent/context/task.md` 当成共享真源？
- 是否把 shell 审计命令写成自动修复器？

任一为“是”则判定为阻塞问题。

### 2. 命令真实性

- skill 中引用的 `bin/vibe` 命令是否真实存在？
- 子命令名、参数名、输出模式是否与当前实现一致？
- 是否要求 shell 提供并不存在的原子能力？

若命令不存在，应输出 `Capability Gap`，而不是让 skill 绕过 shell。

### 3. 标准引用完整性

至少检查是否引用了与自身语义相关的标准真源：

- 术语语义：`docs/standards/glossary.md`
- 动作词语义：`docs/standards/action-verbs.md`
- 命令语义：`docs/standards/command-standard.md`
- Shell/Skill 边界：`docs/standards/shell-capability-design.md`
- Skills 层边界：`docs/standards/skill-standard.md`

若 skill 涉及 flow / branch / worktree / PR，还应检查：

- `docs/standards/git-workflow-standard.md`
- `docs/standards/worktree-lifecycle-standard.md`

### 4. 生命周期与 flow 对齐

- 是否把 `roadmap current` 误写成分支当前态？
- 是否把 `flow`、`workflow`、`worktree`、`branch` 混用？
- 是否暗示一个 flow 可以同时承载多个当前 PR 目标？

### 5. 漂移提醒

至少检查两类漂移：

1. **引用缺失**：相关标准已经存在，但 skill 完全没有引用。
2. **更新滞后**：标准文件的 `last_updated` 晚于 skill 最近一次更新，且 skill 涉及该标准覆盖的语义域。

第一版可以只做“提醒”，不做自动改写。

## Suggested Skill Structure

```text
skills/vibe-skill/
  SKILL.md
  references/
    review-checklist.md
    standards-mapping.md
  scripts/
    audit-skill-references.sh
  agents/
    openai.yaml
```

说明：

- `SKILL.md` 只保留触发描述、模式切换、最小流程。
- `references/review-checklist.md` 存放审查问题，不把长清单堆进入口。
- `references/standards-mapping.md` 维护“语义域 -> 必需标准引用”的映射。
- `scripts/audit-skill-references.sh` 用于做确定性的引用扫描与命令探测。

## Proposed Execution Flow

### 模式 1：Create / Update

1. 读取目标 skill 范围与使用场景。
2. 先调用 `skill-creator` 的通用方法形成草案。
3. 再套用 Vibe 专属检查：
   - 是否走 shell 合法通道
   - 是否引用相关标准真源
   - 是否对齐 flow / lifecycle / action verbs
4. 输出建议结构与必需引用。

### 模式 2：Review / Audit

1. 读取目标 `skills/<name>/SKILL.md`。
2. 扫描其中的：
   - `vibe` 命令
   - 共享真源相关表述
   - 标准文件引用
   - 生命周期语义
3. 与 `docs/standards/*` 真源进行对照。
4. 输出：
   - Blocking
   - Drift Warning
   - Missing Reference
   - Capability Gap

## Additional Recommendations

除了你已经提出的点，我建议再补三项：

1. **命令证据要求**
   对 skill 中每个写操作示例，都要求至少能映射到一个真实 CLI 命令，不允许只写概念步骤。

2. **引用不是装饰**
   不仅检查“有没有链接”，还要检查 skill 是否把关键语义委托给真源，而不是自己重复定义。

3. **标准映射表**
   为不同类型的 skill 预置最小引用集合。例如：
   - task/roadmap/flow/check 类 skill
   - review 类 skill
   - 纯安装管理类 skill

## Files To Modify In Execution Phase

- Create: `skills/vibe-skill/SKILL.md`
- Create: `skills/vibe-skill/references/review-checklist.md`
- Create: `skills/vibe-skill/references/standards-mapping.md`
- Create: `skills/vibe-skill/scripts/audit-skill-references.sh`
- Create: `skills/vibe-skill/agents/openai.yaml`

预计 5 个文件，属于一个逻辑变更。

## Test Command

实施阶段建议至少验证：

```bash
scripts/quick_validate.py skills/vibe-skill
bash skills/vibe-skill/scripts/audit-skill-references.sh skills/vibe-task/SKILL.md
bash skills/vibe-skill/scripts/audit-skill-references.sh skills/vibe-check/SKILL.md
bash skills/vibe-skill/scripts/audit-skill-references.sh skills/vibe-roadmap/SKILL.md
```

## Expected Result

- 新 `vibe-skill` 能服务“创建 + 审查 + 漂移提醒”三个目标。
- 它不会直接操作共享真源，只会要求通过 shell 能力层完成动作。
- 它能对现有 skill 给出标准引用缺失、命令失真、生命周期误述、能力缺口等结论。
- 后续 standards 更新后，skill 至少会收到提醒，而不是静默漂移。

## Change Summary

- Discussion output only: 新增 1 个计划文件
- Added lines: 150 左右
- Modified files: 0
- Removed files: 0

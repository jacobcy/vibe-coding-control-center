---
document_type: audit
title: Python Skill Boundary Audit
status: approved
scope: python-skill-boundary
author: Codex GPT-5
created: 2026-03-08
last_updated: 2026-04-02
related_docs:
  - docs/standards/v3/command-standard.md
  - docs/standards/v3/python-capability-design.md
  - docs/standards/v3/skill-standard.md
---

# Python Skill Boundary Audit

本文档记录当前 Python/CLI 与 Skill 边界的审计基线，用于检查两类问题：

- CLI 是否越权执行了应由 skill 负责的业务判断
- Skills / workflows 是否准确描述了 CLI 是围绕共享真源的能力层，而不是业务判断者

## 1. Audit Questions

本审计使用 [python-capability-design.md](python-capability-design.md) 中的审查原则，并将 [command-standard.md](command-standard.md) 作为命令语义真源。

审计时统一使用以下问题：

1. CLI 是否提供了足够的共享真源相关能力让 skill 完成工作，而不必自己拼接高成本机械步骤？
2. CLI 是否替 skill 做了归属、拆分、优先级、下一步等业务判断？
3. CLI 的 `git` / `gh` / worktree 副作用是否都服务于共享真源同步或单一现场落地？
4. Skill 是否暗示“调用 CLI 命令即可自动完成业务判断”？
5. Skill 是否被诱导绕过 CLI 直接触碰共享状态？

## 2. Findings

### 2.1 Aligned: 现场注册与 Skill 编排的边界

过去 `vibe3 flow new` 承担了过多职责（创建分支、生成 task id、创建 worktree）。在当前 Python 实现中，边界已清晰：

- `git checkout -b` 负责物理分支创建（基础工具）。
- `vibe3 flow update` 负责本地现场注册（CLI 原子能力）。
- `/vibe-new (skill)` 负责全流程编排，含 issue 确认与 PR draft 创建（Skill 层职责）。

判定：
- `Aligned`

### 2.2 Aligned: `task` 语义整合

在 V3 设计中，`task` 作为一个独立的顶级 CLI 已被废弃，其执行桥接语义被整合进 `flow` 体系。

- `vibe3 flow bind` 提供了足够的 issue 关联能力（支持 `--role task/related/dependency`）。
- Skill 层已适配不再调用不存在的 `vibe3 task` 命令。

判定：
- `Architecture Shift Complete`

### 2.3 Blocking: `roadmap current` 语义风险

依据 [command-standard.md](command-standard.md)，`roadmap.current` 属于规划窗口状态，而分支当前焦点属于 `flow` runtime。

如果 Skill 将 `roadmap.current` 误解释为分支当前态，会导致多分支冲突。

判定：
- `Semantic Boundary Risk`

期望：
- 审查 `vibe-roadmap` skill，确保其不将规划态 backlog 自动视为当前分支的执行池。

### 2.4 Aligned: SQLite 数据库路径统一

此前文档中存在多种表述。现已统一：

- **真源位置**: `.git/vibe3/handoff.db` (由 `git rev-parse --git-common-dir` 定位)。

判定：
- `Documentation Fixed`

### 2.5 Medium: `/vibe-new` 与 `/vibe-start` 的职责重叠

`/vibe-new` 负责新任务启动，`/vibe-start` 负责已有分支环境恢复。

判定：
- `Contract Accurate`

期望：
- 持续观察 agent 在切换分支后是否能正确选择 `/vibe-start` 而不是重复运行 `/vibe-new`。

## 3. Audit Summary

当前边界状态可以概括为：

- V3 Python CLI 已成功退化为“围绕共享真源的原子能力层”。
- 复杂的业务编排（如 PR draft 创建、分支命名策略）已上移至 Skill 层。
- 数据库路径和术语冲突已在 2026-04-02 的语义清理中得到修正。
- 当前主要风险在于 agent 对“规划态”与“执行态”的语义混淆。

## 4. Required Follow-Up

1. **Skill 审查**: 定期审查 `skills/vibe-*/SKILL.md`，确保其 description 不含已废弃的命令（如 `flow new`, `flow done`, `flow switch`）。
2. **自动化审计**: 在 `vibe3 check` 中增加对 `handoff.db` 结构与代码模型一致性的自动校验。

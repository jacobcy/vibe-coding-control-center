---
document_type: standard
title: Agent Document Lifecycle Standard
status: active
scope: project-wide
authority:
  - document-lifecycle
  - temporary-artifacts
  - issue-centered-traceability
author: GPT-5 Codex
created: 2026-04-02
last_updated: 2026-04-02
related_docs:
  - docs/README.md
  - docs/standards/doc-organization.md
  - docs/standards/doc-quality-standards.md
  - docs/standards/github-labels-standard.md
  - docs/standards/v3/handoff-store-standard.md
---

# Agent 文档生命周期标准

本文档定义 AI Agent 相关文档的生命周期、留存边界和长期语义落点。

## 1. 任务身份真源

- GitHub issue 是任务身份真源。
- 任务描述、范围说明、验收口径和长期结论，应优先写入 issue 本体或 issue comment。
- 当存在 PR 时，适合放进 PR comment 的结论，也应同步到 PR comment。

## 2. 临时文档

- `.agent/plans/` 是临时计划工作区。
- `.agent/reports/` 是临时报告工作区。
- 这两个目录下的文件都属于工作产物，不是长期规范真源。
- 新的 plan / report 文档只应落在这两个目录中，不应再作为正式文档放入 `docs/plans/` 或 `docs/reports/`。

## 3. 留存规则

- 只要内容需要被后续会话稳定引用，就不要只留在本地 plan / report 里。
- 需要长期保留的判断、发现、风险、决策和跟进项，应写入对应 issue comment。
- 若该结论直接影响合并或审查，也应同步到 PR comment。
- 本地临时文档只保留工作过程与证据，不承担长期沟通职责。

## 4. 任务文档

- `docs/tasks/` 下的任务文档是任务镜像，不是任务身份真源。
- 任务 README 可以记录导航、状态和阶段，但任务定义应以 issue 为准。
- 若任务文档与 issue 冲突，以 issue 及其 comment 为准。

## 5. 兼容原则

- 旧的 `docs/plans/` 和 `docs/reports/` 内容可作为历史参考保留。
- 这些历史文件不应再被新的工作流当作默认落点。
- 如果需要引用历史结论，应优先引用 issue comment，而不是复制旧计划或旧报告正文。

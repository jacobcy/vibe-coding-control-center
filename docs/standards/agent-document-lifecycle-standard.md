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
- 临时草稿和过程证据可先写入这里；需要长期保留、供人类阅读的正式 plan / report，应落在 `docs/plans/` 和 `docs/reports/`。

## 3. 留存规则

- 只要内容需要被后续会话稳定引用，就不要只留在本地 plan / report 里。
- 需要长期保留的判断、发现、风险、决策和跟进项，应写入对应 issue comment。
- 若该结论直接影响合并或审查，也应同步到 PR comment。
- 本地临时文档只保留工作过程与证据，不承担长期沟通职责。

## 4. 正式文档落点

- GitHub issue 是任务身份真源。
- 与任务相关的正式 Spec / Plan / Report 文档，可分别落在 `docs/specs/`、`docs/plans/`、`docs/reports/`。
- 不再维护统一任务镜像目录。
- 若正式文档与 issue 冲突，以 issue 及其 comment 为准。

## 5. 兼容原则

- `docs/plans/` 和 `docs/reports/` 既承载当前可用的正式文档，也保留历史参考内容。
- 如果需要引用历史结论，应优先引用 issue comment，而不是复制旧计划或旧报告正文。

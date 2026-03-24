---
document_type: standard
title: Vibe Workflow Engine Design Note
status: redirected
scope: migration-note
authority:
  - historical-doc-redirect
author: GPT-5 Codex
created: 2026-03-13
last_updated: 2026-03-13
related_docs:
  - docs/references/vibe-engine-design.md
  - docs/standards/glossary.md
  - docs/standards/v3/command-standard.md
  - docs/standards/v3/skill-standard.md
---

# Vibe Workflow Engine 文档迁移说明

原 `vibe-engine-design.md` 正文已迁移到 [docs/references/vibe-engine-design.md](../references/vibe-engine-design.md)。

原因：

- 该文档是历史架构蓝图与背景叙事，不是现行标准体裁
- 其中 `Stage 1/2/3/4`、`Execution Gate`、`Review Gate`、统一编排器等表述容易被误读为当前强制标准
- 当前正式语义已经由以下标准承接：
  - [glossary.md](glossary.md)
  - [command-standard.md](command-standard.md)
  - [skill-standard.md](skill-standard.md)
  - [skill-trigger-standard.md](skill-trigger-standard.md)

使用规则：

- 需要当前对象边界、命令语义、skill/workflow 边界时，读取现行标准
- 需要追溯历史设计背景或旧叙事来源时，读取 reference 版本
- 若 reference 内容与现行标准冲突，以现行标准为准

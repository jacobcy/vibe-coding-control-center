---
document_type: standard
title: Document Quality Standards
status: approved
scope: project-wide
authority:
  - document-metadata
  - frontmatter-schema
  - document-quality
author: Claude Sonnet 4.5
created: 2025-01-24
last_updated: 2025-01-24
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/README.md
  - docs/standards/doc-organization.md
---

# Document Quality Standards

## 概述

本文档定义 Vibe Center 2.0 项目的统一文档质量标准体系。通过 YAML frontmatter 元数据为不同类型的文档建立质量标准框架，确保文档的可维护性、可追溯性和一致性。

### 目的

- 为所有文档类型定义清晰的元数据 schema
- 建立统一的文档质量标准
- 支持文档的版本管理和追溯
- 促进文档间的关联和上下文圈定
- 确保 AI Agent 和人类协作时的文档一致性

### 适用范围

本标准适用于以下目录和文档：

- **`docs/` 目录**：人类文档区（PRD、标准、任务文档等）
- **`.agent/` 目录**：AI 工作区（模板、工作流、规则等）
- **根目录核心入口文档**：SOUL.md、STRUCTURE.md、CLAUDE.md、AGENTS.md 等

### 不适用范围

以下目录和文档不在本标准范围内：

- **`skills/` 目录**：项目自己的 skills 有特殊格式要求
- **`.agent/skills/` 目录**：外部 skills 的 symlinks，不应修改
- **`lib/`、`bin/` 目录**：Shell 脚本，不需要 frontmatter

## 文档类型分类

本标准定义 7 种文档类型：

| 文档类型 | document_type 值 | 位置 | 用途 | 受众 |
|---------|-----------------|------|------|------|
| 核心入口文档 | `core-entry` | 根目录 | 项目入口和核心定义 | Human + AI |
| 技能文档 | `skill` | `.agent/skills/*/SKILL.md` | AI 技能定义 | AI |
| 模板文档 | `template` | `.agent/templates/*.md` | 文档生成模板 | AI |
| 工作流文档 | `workflow` | `.agent/workflows/*.md` | 工作流定义 | AI |
| PRD 文档 | `prd` | `docs/prds/*.md` | 产品需求文档 | Human + AI |
| 任务文档 | `task-*` | `docs/tasks/{Task_ID}/*.md` | 任务文档 | Human + AI |
| 标准文档 | `standard` | `docs/standards/*.md` | 标准和规范 | Human + AI |

## Frontmatter Schema 定义

### 通用字段

所有文档类型共享以下通用字段：

| 字段名 | 类型 | 必需 | 说明 | 格式示例 |
|--------|------|------|------|---------|
| `document_type` | string | 是 | 文档类型标识 | `core-entry`, `skill`, `template` 等 |
| `author` | string | 是 | 文档创建者 | AI: `"Claude Sonnet 4.5"` / Human: 真实姓名 |
| `created` | string | 是 | 创建时间 | `2025-01-24` (ISO 8601) |
| `last_updated` | string | 否 | 最后更新时间 | `2025-01-24` (ISO 8601) |
| `related_docs` | array[string] | 否 | 相关文档路径（上下文圈定） | `["SOUL.md", "docs/README.md"]` |

#### 字段说明

**`document_type`**
- 标识文档的类型，用于分类和处理
- 必须是预定义的文档类型之一
- 使用 kebab-case 格式

**`author`**
- **AI Agent 创建的文档**：必须使用真实 AI 身份签名
  - ✅ 正确：`"Claude Sonnet 4.5"`
  - ❌ 错误：`"Vibe Center Team"`、`"AI Assistant"`
- **人类创建的文档**：使用真实姓名或用户名
- 这是真实性原则的体现，避免虚假身份

**`created`**
- 文档首次创建的日期
- 使用 ISO 8601 格式：`YYYY-MM-DD`
- 必需字段，用于追溯文档历史

**`last_updated`**
- 文档最后一次实质性更新的日期
- 使用 ISO 8601 格式：`YYYY-MM-DD`
- 可选字段，但建议在更新文档时同步更新

**`related_docs`**
- 列出与当前文档相关的其他文档路径
- 用于上下文圈定，帮助读者理解文档的关联关系
- 使用相对路径（相对于项目根目录）
- 示例：`["SOUL.md", "docs/README.md", ".agent/workflows/vibe-drift.md"]`

### 核心入口文档 (Core Entry Document)

核心入口文档是项目的主要入口点，如 SOUL.md、STRUCTURE.md、CLAUDE.md、AGENTS.md 等。

#### Schema

| 字段名 | 类型 | 必需 | 说明 | 示例值 |
|--------|------|------|------|--------|
| `document_type` | string | 是 | 固定值 | `core-entry` |
| `authority` | array[string] | 是 | 该文档是哪些概念的权威来源 | `["project-structure", "file-organization"]` |
| `audience` | string | 是 | 目标受众 | `human` / `ai` / `both` |
| `review_frequency` | string | 是 | 审查频率 | `yearly` / `quarterly` / `on-change` |

#### 完整示例

```yaml
---
document_type: core-entry
authority:
  - project-structure
  - file-organization
  - directory-layout
audience: both
review_frequency: on-change
author: Claude Sonnet 4.5
created: 2025-01-24
last_updated: 2025-01-24
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/README.md
---
```

#### 字段说明

**`authority`**
- 标识该文档是哪些概念的权威来源
- 符合 SOUL.md 中的"单一事实来源"原则
- 其他文档引用这些概念时应指向此文档
- 示例：STRUCTURE.md 是 `project-structure` 的权威来源

**`audience`**
- `human`：主要面向人类读者
- `ai`：主要面向 AI Agent
- `both`：同时面向人类和 AI

**`review_frequency`**
- `yearly`：每年审查一次
- `quarterly`：每季度审查一次
- `on-change`：当相关内容变化时审查

### 技能文档 (Skill Document)

技能文档定义 AI Agent 的技能，位于 `.agent/skills/*/SKILL.md`。

#### Schema

| 字段名 | 类型 | 必需 | 说明 | 示例值 |
|--------|------|------|------|--------|
| `document_type` | string | 是 | 固定值 | `skill` |
| `name` | string | 是 | 技能名称 | `receiving-code-review` |
| `description` | string | 是 | 技能用途简述 | `Use when receiving code review feedback...` |
| `category` | string | 否 | 技能分类 | `process` / `orchestrator` / `validation` |
| `trigger` | string | 否 | 触发方式 | `manual` / `auto` |

#### 完整示例

```yaml
---
document_type: skill
name: receiving-code-review
description: Use when receiving code review feedback from human reviewers
category: process
trigger: manual
author: Claude Sonnet 4.5
created: 2025-01-24
last_updated: 2025-01-24
related_docs:
  - .agent/workflows/code-review.md
  - docs/standards/coding-standards.md
---
```

#### 字段说明

**`name`**
- 技能的唯一标识符
- 使用 kebab-case 格式
- 应与技能目录名一致

**`description`**
- 简短描述技能的用途和适用场景
- 帮助 AI Agent 决定何时使用该技能

**`category`**
- `process`：流程类技能（如代码审查、测试）
- `orchestrator`：编排类技能（如任务分解、工作流管理）
- `validation`：验证类技能（如质量检查、合规性验证）

**`trigger`**
- `manual`：需要显式调用
- `auto`：可自动触发

### 模板文档 (Template Document)

模板文档用于生成其他文档，位于 `.agent/templates/*.md`。

#### Schema

| 字段名 | 类型 | 必需 | 说明 | 示例值 |
|--------|------|------|------|--------|
| `document_type` | string | 是 | 固定值 | `template` |
| `template_for` | string | 是 | 模板用于生成的文档类型 | `prd` / `task-readme` / `spec` |
| `description` | string | 是 | 模板用途说明 | `Template for PRD documents` |

#### 完整示例

```yaml
---
document_type: template
template_for: prd
description: Template for Product Requirements Documents (PRD)
author: Claude Sonnet 4.5
created: 2025-01-24
last_updated: 2025-01-24
related_docs:
  - docs/prds/vibe-workflow-paradigm.md
  - docs/README.md
---
```

#### 字段说明

**`template_for`**
- 标识该模板用于生成什么类型的文档
- 常见值：`prd`, `task-readme`, `spec`, `plan`, `audit`

**`description`**
- 说明模板的用途和使用场景
- 帮助 AI Agent 选择合适的模板

### 工作流文档 (Workflow Document)

工作流文档定义 AI Agent 的工作流程，位于 `.agent/workflows/*.md`。

#### Schema

| 字段名 | 类型 | 必需 | 说明 | 示例值 |
|--------|------|------|------|--------|
| `document_type` | string | 是 | 固定值 | `workflow` |
| `description` | string | 是 | 工作流简述 | `Detect project drift from original principles` |

#### 完整示例

```yaml
---
document_type: workflow
description: Detect and report project drift from original principles defined in SOUL.md
author: Claude Sonnet 4.5
created: 2025-01-24
last_updated: 2025-01-24
related_docs:
  - SOUL.md
  - .agent/context/memory.md
---
```

#### 字段说明

**`description`**
- 简短描述工作流的目的和功能
- 帮助理解工作流的适用场景

### PRD 文档 (PRD Document)

PRD 文档定义产品需求，位于 `docs/prds/*.md`。

#### Schema

| 字段名 | 类型 | 必需 | 说明 | 示例值 |
|--------|------|------|------|--------|
| `document_type` | string | 是 | 固定值 | `prd` |
| `title` | string | 是 | PRD 标题 | `Vibe Workflow Paradigm` |
| `status` | string | 是 | 文档状态 | `draft` / `review` / `approved` / `deprecated` |

#### 完整示例

```yaml
---
document_type: prd
title: Vibe Workflow Paradigm
status: approved
author: Claude Sonnet 4.5
created: 2025-01-15
last_updated: 2025-01-24
related_docs:
  - .agent/workflows/vibe-drift.md
  - .agent/workflows/vibe-check.md
  - SOUL.md
---
```

#### 字段说明

**`title`**
- PRD 的标题，应简洁明了
- 反映 PRD 的核心内容

**`status`**
- `draft`：草稿状态，正在编写
- `review`：审查中，等待反馈
- `approved`：已批准，可以实施
- `deprecated`：已废弃，不再使用

### 任务文档 (Task Document)

任务文档记录具体任务的信息，位于 `docs/tasks/{Task_ID}/*.md`。

#### Schema

| 字段名 | 类型 | 必需 | 说明 | 示例值 |
|--------|------|------|------|--------|
| `task_id` | string | 是 | 任务 ID | `2024-01-15-feature-name` |
| `document_type` | string | 是 | 文档类型 | `task-readme` / `task-prd` / `task-spec` / `task-plan` / `task-test` / `task-code` / `task-audit` |
| `title` | string | 是 | 任务标题 | `Implement Document Quality Standards` |
| `current_layer` | string | 否（README 必需） | 当前层级 | `prd` / `spec` / `plan` / `test` / `code` / `audit` |
| `status` | string | 否（README 必需） | 任务状态 | `draft` / `in-progress` / `completed` |

#### 完整示例 - Task README

```yaml
---
task_id: 2024-01-15-doc-quality
document_type: task-readme
title: Implement Document Quality Standards
current_layer: code
status: in-progress
author: Claude Sonnet 4.5
created: 2025-01-15
last_updated: 2025-01-24
related_docs:
  - docs/standards/doc-quality-standards.md
  - CLAUDE.md
gates:
  scope:
    status: passed
    timestamp: 2025-01-15T10:00:00Z
    reason: Requirements clearly defined
  spec:
    status: passed
    timestamp: 2025-01-16T14:30:00Z
    reason: Design approved
  plan:
    status: passed
    timestamp: 2025-01-17T09:00:00Z
    reason: Implementation plan ready
  test:
    status: pending
    timestamp: ""
    reason: ""
  code:
    status: pending
    timestamp: ""
    reason: ""
  audit:
    status: pending
    timestamp: ""
    reason: ""
---
```

#### 完整示例 - Task PRD

```yaml
---
task_id: 2024-01-15-doc-quality
document_type: task-prd
title: Document Quality Standards - PRD
author: Claude Sonnet 4.5
created: 2025-01-15
last_updated: 2025-01-15
related_docs:
  - docs/tasks/2024-01-15-doc-quality/README.md
---
```

#### 字段说明

**`task_id`**
- 任务的唯一标识符
- 格式：`YYYY-MM-DD-feature-name`
- 使用 kebab-case 格式

**`document_type`**
- `task-readme`：任务总览文档
- `task-prd`：任务 PRD 文档
- `task-spec`：任务规格文档
- `task-plan`：任务计划文档
- `task-test`：任务测试文档
- `task-code`：任务代码文档
- `task-audit`：任务审计文档

**`current_layer`**（仅用于 task-readme）
- 标识任务当前所在的层级
- 值：`prd`, `spec`, `plan`, `test`, `code`, `audit`

**`status`**（仅用于 task-readme）
- `draft`：草稿状态
- `in-progress`：进行中
- `completed`：已完成
- **重要**：frontmatter 中的 `status` 字段是唯一真源（Single Source of Truth）
- 正文中的"当前状态"部分应使用指引文本：`见 frontmatter \`status\` 字段（唯一真源）`
- 不要在正文中重复或冗余状态值，避免双头真源问题

**`gates`**（仅用于 task-readme）
- 记录任务各个 Gate 的状态
- 每个 Gate 包含：
  - `status`：`pending` / `passed` / `failed`
  - `timestamp`：ISO 8601 格式的时间戳
  - `reason`：通过或失败的原因

### 标准文档 (Standard Document)

标准文档定义项目的标准和规范，位于 `docs/standards/*.md`。

#### Schema

| 字段名 | 类型 | 必需 | 说明 | 示例值 |
|--------|------|------|------|--------|
| `document_type` | string | 是 | 固定值 | `standard` |
| `title` | string | 是 | 标准标题 | `Document Organization Standard` |
| `status` | string | 是 | 文档状态 | `draft` / `review` / `approved` / `deprecated` |
| `scope` | string | 是 | 适用范围 | `project-wide` / `specific-module` |
| `authority` | array[string] | 否 | 该标准是哪些概念的权威来源 | `["document-naming", "file-organization"]` |

#### 完整示例

```yaml
---
document_type: standard
title: Document Organization Standard
status: approved
scope: project-wide
authority:
  - document-naming
  - file-organization
  - directory-structure
author: Claude Sonnet 4.5
created: 2025-01-20
last_updated: 2025-01-24
related_docs:
  - docs/README.md
  - STRUCTURE.md
  - docs/standards/doc-quality-standards.md
---
```

#### 字段说明

**`title`**
- 标准的标题，应简洁明了
- 反映标准的核心内容

**`status`**
- `draft`：草稿状态，正在编写
- `review`：审查中，等待反馈
- `approved`：已批准，应遵循
- `deprecated`：已废弃，不再使用

**`scope`**
- `project-wide`：适用于整个项目
- `specific-module`：仅适用于特定模块

**`authority`**
- 标识该标准是哪些概念的权威来源
- 符合单一事实来源原则

## 使用指南

### AI Agent 创建文档时

1. **确定文档类型**：根据文档的用途和位置，确定使用哪种 document_type
2. **添加 frontmatter 块**：在文档开头添加 YAML frontmatter，用 `---` 包围
3. **填写必需字段**：确保所有必需字段都已填写
4. **使用真实身份签名**：在 `author` 字段中使用真实的 AI 身份（如 "Claude Sonnet 4.5"）
5. **圈定上下文**：在 `related_docs` 字段中列出相关文档，帮助读者理解上下文
6. **使用正确格式**：
   - 日期使用 ISO 8601 格式（YYYY-MM-DD）
   - 名称使用 kebab-case 格式
   - 枚举值使用预定义的值

### 人类创建文档时

1. **参考示例**：查看同类型文档的 frontmatter 示例
2. **填写必需字段**：确保所有必需字段都已填写
3. **使用真实姓名**：在 `author` 字段中使用真实姓名或用户名
4. **保持更新**：修改文档时更新 `last_updated` 字段

### 上下文圈定

`related_docs` 字段用于建立文档间的关联关系，帮助读者理解文档的上下文边界。

**使用场景**：
- 文档引用其他文档的概念或定义
- 文档是其他文档的补充或扩展
- 文档与其他文档共同构成一个完整的主题

**示例**：
```yaml
related_docs:
  - SOUL.md                              # 引用核心原则
  - docs/README.md                       # 引用文档组织结构
  - docs/standards/doc-organization.md   # 引用相关标准
```

### 最佳实践

1. **单一事实来源**：每个概念应有唯一的权威文档，其他文档引用而不重复定义
2. **真实性原则**：作者字段必须是真实身份，不使用虚假团队名
3. **实用主义**：每个字段必须有实际用途，不为标准而标准
4. **最小侵入**：frontmatter 不影响文档正文内容
5. **保持更新**：修改文档时同步更新 `last_updated` 字段
6. **上下文圈定**：使用 `related_docs` 建立文档间的关联
7. **状态字段单一真源**：对于 Task README，frontmatter 的 `status` 字段是唯一真源，正文使用指引文本而非重复状态值

### 常见问题

**Q: 现有文档是否必须立即添加 frontmatter？**
A: 不强制。新文档应遵循标准，现有文档可逐步更新。

**Q: 如果文档类型不在 7 种类型中怎么办？**
A: 选择最接近的类型，或在 `related_docs` 中说明特殊性。未来可扩展新类型。

**Q: AI Agent 如何签名？**
A: 使用真实的 AI 身份，如 "Claude Sonnet 4.5"、"GPT-4"、"Gemini Pro" 等。

**Q: `related_docs` 应该列出所有相关文档吗？**
A: 列出最直接相关的文档即可，通常 3-5 个。避免过度关联。

**Q: 日期格式为什么使用 ISO 8601？**
A: ISO 8601 是国际标准，无歧义，易于解析和排序。

## 验证清单

创建或修改文档时，使用以下清单进行自检：

- [ ] frontmatter 格式正确（YAML 语法，用 `---` 包围）
- [ ] 所有必需字段都已填写
- [ ] `document_type` 值正确
- [ ] `author` 使用真实身份（AI Agent 签名或人类名字）
- [ ] 日期格式为 ISO 8601 (YYYY-MM-DD)
- [ ] 枚举值使用预定义的值
- [ ] `related_docs` 正确圈定上下文
- [ ] 文档正文内容未被破坏

## 参考文档

- [SOUL.md](../../SOUL.md) - 单一事实原则和文档职责分工
- [STRUCTURE.md](../../STRUCTURE.md) - 项目结构定义
- [CLAUDE.md](../../CLAUDE.md) - 项目上下文和硬规则
- [docs/README.md](../README.md) - 文档结构和组织
- [docs/standards/doc-organization.md](./doc-organization.md) - 文档组织标准
- [YAML Specification](https://yaml.org/spec/1.2/spec.html) - YAML 格式规范
- [ISO 8601](https://www.iso.org/iso-8601-date-and-time-format.html) - 日期时间格式标准

## 版本历史

- **2025-01-24**: 初始版本，定义 7 种文档类型的 frontmatter schema

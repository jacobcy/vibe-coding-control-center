---
document_type: standard
title: Document Organization Standard
status: approved
scope: project-wide
authority:
  - document-naming
  - file-organization
  - directory-structure
  - task-structure
author: Claude Sonnet 4.5
created: 2025-01-20
last_updated: 2025-01-24
related_docs:
  - docs/README.md
  - docs/standards/doc-quality-standards.md
  - docs/prds/vibe-workflow-paradigm.md
  - STRUCTURE.md
---

# 文档组织标准

本文档定义 Vibe Center 2.0 的文档组织标准，与 Vibe Workflow Paradigm 的 Vibe Guard 范式完全对齐。

## 核心原则

1. **文档即规范**：文档是唯一的真理来源，代码必须符合文档
2. **流程对齐**：文档结构与 Vibe Guard 流程一一对应
3. **人工优先**：标准设计为人工操作友好，不依赖自动化工具
4. **AI 工作区分离**：模板等 AI 工具放在 `.agent/`，人类文档放在 `docs/`

## 目录结构

```
docs/
├── README.md                        # 项目文档总览和索引
├── standards/                       # 标准和规范文档
│   ├── DOC_ORGANIZATION.md         # 本文档组织标准
│   └── vibe-engine-design.md       # Vibe 工作流引擎设计
├── prds/                           # 产品需求文档（全局 PRD）
│   ├── vibe-workflow-paradigm.md   # 总 PRD：Vibe Guard 范式
│   └── ...                         # 其他全局 PRD
└── tasks/                          # 任务文档（按任务组织）
    └── {Task_ID}/                  # 格式: YYYY-MM-DD-feature-name
        ├── README.md               # 任务概述、状态和导航
        ├── prd-v1-initial.md       # PRD 层文档
        ├── spec-v1-initial.md      # Spec 层文档
        ├── plan-v1-initial.md      # Plan 层文档
        ├── test-strategy.md        # Test 层文档
        ├── code-implementation.md  # Code 层文档
        └── audit-2024-01-15.md     # Review 层文档（AI 审计）

.agent/templates/                    # AI 工作模板（不在 docs/ 下）
├── prd.md                          # PRD 模板
├── tech-spec.md                    # Spec 模板
├── plan.md                         # Plan 模板
├── test.md                         # Test 模板
├── code.md                         # Code 模板
├── audit.md                        # Audit 模板
└── task-readme.md                  # Task README 模板
```

## 命名规范

### Task_ID 格式

```
YYYY-MM-DD-feature-name
```

**规则**：
- 使用 kebab-case（小写字母 + 连字符）
- 以日期前缀开头（YYYY-MM-DD）
- 日期后跟功能名称
- 功能名称简洁明了，3-5 个单词

**示例**：
- `2024-01-15-docs-organization-standard`
- `2024-01-16-unified-dispatcher`

### 文档命名规范

所有文档使用 `{layer}-{version/description}.md` 格式：

**PRD/Spec/Plan 文档**（支持版本管理）：
```
{layer}-v{version}-{description}.md

示例：
- prd-v1-initial.md
- spec-v2-add-validation.md
- plan-v1-initial.md
```

**Test/Code 文档**（描述性命名）：
```
{layer}-{description}.md

示例：
- test-strategy.md
- code-implementation.md
```

**Audit 文档**（日期命名）：
```
audit-{YYYY-MM-DD}.md

示例：
- audit-2024-01-15.md
```

## Vibe Guard 对应关系

| 层级 | 文档类型 | Gate | 验证标准 |
|------|---------|------|---------|
| PRD（认知层） | prd-*.md | Scope Gate | 业务目标、绝对边界、核心数据流、成功判据 |
| Spec（规范层） | spec-*.md | Spec Gate | 接口契约、核心不变量、边界行为、非功能约束 |
| Plan（执行计划层） | plan-*.md | Plan Gate | 上下文圈定、任务拆分、风险对策 |
| Test（测试层） | test-*.md | Test Gate | 测试策略、断言来源、TDD 流程记录 |
| Code（代码实现层） | code-*.md | Code Gate | 实现概述、复杂度报告、AST 约束检查 |
| Review（AI 审计层） | audit-*.md | Audit Gate | 目标对齐、规范遵守、路径一致、架构纯洁 |

## 使用指南

### 创建新任务

1. **创建任务目录**：
   ```bash
   mkdir -p docs/tasks/2024-01-15-feature-name
   ```

2. **从模板创建 README**：
   ```bash
   cp .agent/templates/task-readme.md docs/tasks/2024-01-15-feature-name/README.md
   ```

3. **替换占位符**：
   - `{{TASK_ID}}` → `2024-01-15-feature-name`
   - `{{TASK_TITLE}}` → `Feature Name`
   - `{{DATE}}` → `2024-01-15`

4. **创建 PRD 文档**：
   ```bash
   cp .agent/templates/prd.md docs/tasks/2024-01-15-feature-name/prd-v1-initial.md
   ```

5. **按 Vibe Guard 流程逐步创建其他文档**

### 更新任务状态

在任务 README.md 的 frontmatter 中更新：

```yaml
current_layer: "spec"  # 当前所在层级
status: "in-progress"  # 任务状态

gates:
  scope:
    status: "passed"
    timestamp: "2024-01-15T10:00:00Z"
  spec:
    status: "in-progress"
```

### Gate 验证

每个 Gate 都有明确的验证标准（见各模板文件末尾），人工检查确认后才能通过。

## 模板位置说明

**重要**：所有模板文件位于 `.agent/templates/`（AI 工作区），而不是 `docs/templates/`（人类主权区）。

这是因为：
- `docs/` - 人类阅读的文档（PRD、Spec、任务文档等）
- `.agent/` - AI 使用的工具（模板、规则、工作流等）

模板是 AI 用来生成文档的工具，应该放在 AI 工作区。

## 参考

- [Vibe Workflow Paradigm](../prds/vibe-workflow-paradigm.md) - Vibe Guard 范式总 PRD
- [Cognition Spec Dominion](cognition-spec-dominion.md) - 宪法大纲
- [Vibe Engine Design](vibe-engine-design.md) - 工作流引擎设计

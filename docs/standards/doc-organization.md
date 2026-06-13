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
last_updated: 2026-06-03
related_docs:
  - docs/README.md
  - docs/standards/agent-document-lifecycle-standard.md
  - docs/standards/glossary.md
  - docs/standards/doc-quality-standards.md
  - docs/prds/vibe-workflow-paradigm.md
  - STRUCTURE.md
  - SOUL.md
---

# 文档组织标准

本文档只定义目录结构、命名规范和文档落位。若涉及 `task`、`workflow`、`PRD`、`Spec`、`Plan`、`Code`、`Audit` 等项目术语，其正式语义以 [glossary.md](glossary.md) 为准。

本文档定义 Vibe Center 的文档组织标准，旨在建立清晰的文档交付链。
任务身份以 GitHub issue 为准；正式 Spec / Plan / Report 分别落在 `docs/specs/`、`docs/plans/`、`docs/reports/`。
旧的统一任务镜像目录不再作为默认组织方式；若历史文件仍存在，仅作为归档参考。

## 核心原则

1. **单一事实来源 (Single Source of Truth)**：每个概念、规则、流程只在一个文档中详细阐述，代码必须符合文档（详见 [SOUL.md](../../SOUL.md) §0）。
2. **渐进披露 (Progressive Disclosure)**：按“入口 -> 标准/规则 -> 细节”路径逐层展开，控制认知负担。
3. **流程对齐**：文档结构与 V3 规范工作流 (Vibe Guard) 一一对应。
4. **人工优先**：标准设计为人工操作友好，不依赖自动化工具。
5. **AI 工作区分离**：工具、模板与 AI 上下文放在 `.agent/` 和 `.claude/`，人类文档放在 `docs/`。

## 目录结构

```
docs/
├── README.md                        # 项目索引
├── standards/                       # 标准和规范文档
│   ├── doc-organization.md          # 本文档组织标准
│   ├── glossary.md                  # 术语真源 (T1-T3 & L1-L4)
│   └── ...                          # 其他现行标准
├── specs/                           # 规范文档 (Issue/Feature 契约)
├── prds/                            # 产品需求文档（全局 PRD）
├── design/                          # 设计文档
├── decisions/                       # 架构决策记录 (ADR)
│   ├── INDEX.md                     # 决策总表
│   └── NNNN-kebab-title.md          # 具体决策文件
├── plans/                           # 执行计划
├── directives/                      # [V3 Active] 指令集文档 (Executor/Manager/Supervisor)
├── handoff/                         # [V3 Active] 执行交接现场 (Artifacts, Results)
├── reports/                         # 报告与总结
├── references/                      # 外部参考资料
├── archive/                         # 历史文档归档
├── handoffs/                        # [Legacy] 旧版交接记录归档

核心系统目录说明：
- `src/vibe3/` - V3 Python 实现 (Tier 1/2/3)
- `lib3/` - V3 Python 核心包装器 (Tier 1 Core Wrapper)
- `supervisor/` - 治理与决策指令集 (Tier 3 Governance)
- `skills/` - 技能定义权威来源 (Canonical Source)
- `.agent/` - AI 运行时上下文 (Context/Memory, Templates)
- `.claude/` - AI 规则与技能运行时真源 (Rules, Skills runtime)

AI 工作区中的临时产物与模板：
- `.agent/context/memory/` - [TRACKED] 持久化模式记忆目录；注意：claude-memory MCP 是会话回溯的主工具
- `.agent/templates/` - AI 工作模板 (prd, spec, plan, etc.)
- `.claude/rules/` - 编码规则真源 (coding-standards, python-standards, etc.)
- `.claude/skills/` - 技能运行时规则与指令
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
- `2026-06-01-docs-organization-standard`
- `2026-06-02-unified-dispatcher`

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
- audit-2026-06-03.md
```

**ADR 文档**（顺序编号命名）：
```
NNNN-kebab-title.md

示例：
- 0001-adopt-adr-loop.md
- 0002-protocol-based-di.md
```

ADR 编号格式：`NNNN-kebab-title.md`（4 位顺序号，如 `0001-adopt-adr-loop.md`）。顺序号支持 supersede 链。

## 文档交付层级

| 层级 | 文档类型 | 主要内容 | 验证标准 |
|------|---------|------|---------|
| PRD（认知层） | prd-*.md | 业务目标、绝对边界、核心数据流、成功判据 | 语义完整、无歧义、符合 SOUL.md |
| Spec（规范层） | spec-*.md | 接口契约、核心不变量、边界行为、非功能约束 | 逻辑自洽、技术可行、符合 PRD |
| Plan（执行计划层） | plan-*.md | 上下文圈定、任务拆分、风险对策 | 步骤清晰、依赖明确、符合 Spec |
| Test（测试层） | test-*.md | 测试策略、断言来源、TDD 流程记录 | 覆盖核心路径、边界条件完备 |
| Code（代码实现层） | code-*.md | 实现概述、复杂度报告、AST 约束检查 | 结构清晰、符合规范、通过测试 |
| Audit（审计层） | audit-*.md | 目标对齐、规范遵守、架构纯洁 | 满足 PRD/Spec 要求、无技术债引入 |

## 使用指南

### 创建新任务

1. **创建对应目录**：
   ```bash
   mkdir -p docs/specs docs/plans docs/reports
   ```

2. **从模板创建正式文档**：
   ```bash
   cp .agent/templates/tech-spec.md docs/specs/<name>.md
   cp .agent/templates/plan.md docs/plans/<name>.md
   cp .agent/templates/prd.md docs/prds/<name>.md
   ```

3. **替换占位符并填写内容**

4. **按文档交付层级逐步推进**
   - 临时草稿与过程证据记录在 issue / handoff 中。
   - 需要长期保留的正式版本写入 `docs/plans/`、`docs/reports/`。
   - 长期结论写入 issue comment 或 PR comment。

### 更新任务状态

在对应文档的 frontmatter 中更新：

```yaml
current_layer: "spec"  # 当前所在层级
status: "in-progress"  # 任务状态

gates:
  scope:
    status: "passed"
    timestamp: "2026-06-03T10:00:00Z"
  spec:
    status: "in-progress"
```

### Gate 验证

每个 Gate 都有明确的验证标准（见各模板文件末尾），人工检查确认后才能通过。

## 模板位置说明

**重要**：所有模板文件位于 `.agent/templates/`（AI 工作区），而不是 `docs/templates/`（人类主权区）。

这是因为：
- `docs/` - 人类阅读的文档（PRD、Spec、Plan、Report、归档等）
- `.agent/` - AI 使用的工具（模板、规则、工作流、上下文等）

模板是 AI 用来生成文档的工具，应该放在 AI 工作区。

## 参考

- [Vibe Workflow Paradigm](../prds/vibe-workflow-paradigm.md) - Vibe Guard 范式 总 PRD
- [Cognition Spec Dominion](cognition-spec-dominion.md) - 宪法大纲
- [docs/archive/](../archive/) - 历史文档归档区
- [STRUCTURE.md](../../STRUCTURE.md) - 项目结构真源
- [SOUL.md](../../SOUL.md) - 项目宪法
- [AGENTS.md](../../AGENTS.md) - AI Agent 入口指南
- [Shared-State Command Standard (v3)](v3/command-standard.md) - V3 命令标准

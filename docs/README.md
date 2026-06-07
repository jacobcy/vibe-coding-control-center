# Vibe Center 3.0 文档

本目录包含 Vibe Center 3.0 的所有人类可读文档。V3 规范优先，V2 兼容语义只在历史和辅助边界里保留。

> 进行 V3 相关工作时，先读 `standards/v3/`，再回看 `CLAUDE.md` / `STRUCTURE.md`。除兼容和历史边界外，不应把 V2 目录当作语义真源。

## 📁 目录结构

```
lib3/                                # V3 Python 核心包装器与仓库重定向 (hub)
docs/
├── README.md                        # 本文件：文档总览
├── standards/                       # 标准和规范文档
│   ├── doc-organization.md          # 文档组织标准（必读）
│   ├── glossary.md                  # 术语真源（必读）
│   ├── v3/                          # V3 核心标准 (handoff, git, models)
│   └── ...                         # 其他现行标准
├── v3/                              # V3 实施、架构、Orchestra 与 Prompt 参考
├── specs/                           # 规范文档 (Issue/Feature 契约)
├── prds/                           # 产品需求文档 (全局 PRD)
├── decisions/                       # 架构决策记录 (ADR)
├── plans/                          # 执行计划 (草稿于 .agent/plans/)
├── reports/                        # 报告与总结 (草稿于 .agent/reports/)
├── design/                          # 设计文档与架构演进
├── closeout/                        # 任务结项报告与回顾
├── directives/                      # 任务指令与执行引导
├── executor/                        # 任务执行过程记录与审计
├── governance/                      # 治理流程、审计记录与立项决策
├── handoff/                         # Handoff 链路存档与交接记录
├── handoffs/                        # (Legacy) 历史交接记录存档
├── migration/                       # 迁移设计与执行记录
├── migrations/                      # (Legacy) 历史迁移记录存档
├── project/                         # 项目级文档与 Meta-layer
├── publish/                         # 发布记录
├── publish-directives/              # 发布指令与发布流程记录
├── references/                      # 外部参考资料
├── superpowers/                     # Superpowers 技能文档
├── validation/                      # 验证报告与测试证据
└── ...                             # 其他现行文档
```

## 🎯 文档分类

### 标准文档 (`standards/`)
存放项目的标准、规范、架构设计等元文档。这些文档定义了"如何做事"。

**必读文档**：
- **[glossary.md](standards/glossary.md)** - 项目术语真源，统一概念定义与别称边界
- **[action-verbs.md](standards/action-verbs.md)** - 高频动作词真源，统一默认含义与执行提醒
- **[v3/architecture-convergence-standard.md](standards/v3/architecture-convergence-standard.md)** - Vibe3 目标架构总纲
- **[v3/human-mirror-architecture-philosophy.md](standards/v3/human-mirror-architecture-philosophy.md)** - Vibe3 人机对称架构哲学
- **[v3/serve-debugging-guide.md](standards/v3/serve-debugging-guide.md)** - Vibe3 Serve 调试指南
- **[doc-organization.md](standards/doc-organization.md)** - 文档组织标准

**已废弃文档 (Archives)**：
- **[supervisor-handoff-standard.md](archive/supervisor-handoff-standard.md)** (DEPRECATED) - 跨角色交接标准 (已废弃，见 [standards/v3/handoff-governance-standard.md](standards/v3/handoff-governance-standard.md))
- **[vibe3-role-checks-and-balances-standard.md](archive/vibe3-role-checks-and-balances-standard.md)** (DEPRECATED) - Vibe3 角色制衡架构标准 (已废弃，见 [standards/v3/human-mirror-architecture-philosophy.md](standards/v3/human-mirror-architecture-philosophy.md))
- **[agent-debugging-standard.md](archive/agent-debugging-standard.md)** (DEPRECATED) - Agent 调试标准 (已废弃，见 [standards/v3/serve-debugging-guide.md](standards/v3/serve-debugging-guide.md))
- **[vibe3-worktree-ownership-standard.md](archive/vibe3-worktree-ownership-standard.md)** (DEPRECATED) - Worktree 所有权标准 (已废弃，见 standards/v3/worktree-lifecycle-standard.md)

**V3 规范目录**：
- **[standards/v3/](standards/v3/)** - V3 核心标准（handoff, git, models, registry migration）
- **[v3/](v3/)** - V3 实施参考、架构演进与 Prompt 定义
### 全局 PRD (`prds/`)
存放不针对特定任务的全局性产品需求文档。

**核心 PRD**：
- **[vibe-workflow-paradigm.md](prds/vibe-workflow-paradigm.md)** - 总 PRD，定义 Vibe Guard 范式

### 决策文档 (`decisions/`)
存放架构决策记录 (ADR)。每个 ADR 记录一个不可变的"为什么"决策，通过 INDEX.md 提供发现入口。详见 `docs/decisions/INDEX.md`。

### 外部参考资料 (`references/`)
存放从外部收集的参考资料，包括但不限于：
- 技术文档和论文
- 设计参考和案例研究
- 行业标准和最佳实践
- 第三方工具和框架文档

**用途**：为项目决策和实现提供外部知识支持，不属于项目自身文档。

### 规范文档 (`specs/`)
按 issue / feature 组织的规范和实现约束文档。

**原则**：
- issue 是任务身份真源
- 规范文档记录接口契约、边界行为和实现约束
- 需要长期保留的结论写到 issue comment 或 PR comment

### 执行计划 (`plans/`)
需要长期保留的计划文档与推进记录。

**原则**：
- 正式计划可以直接写入 `docs/plans/`
- 临时草稿优先写入 `.agent/plans/`

### 报告与总结 (`reports/`)
长期保留的报告、审计和复盘文档。

**原则**：
- 正式报告可以直接写入 `docs/reports/`
- 临时草稿优先写入 `.agent/reports/`

### 临时计划 (`.agent/plans/`)
存放 Agent 生成的临时计划文档，不作为正式真源。

**用途**：圈定上下文、拆分任务、记录短期执行方案。

### 临时报告 (`.agent/reports/`)
存放 Agent 生成的临时报告文档，不作为正式真源。

**用途**：记录审计、分析、调试和验证过程中的工作证据。

### 任务命名与文档命名

**任务命名格式**：`YYYY-MM-DD-feature-name`（kebab-case）

**文档命名格式**：
- PRD/Spec/Plan：`{layer}-v{version}-{description}.md`
- Test/Code：`{layer}-{description}.md`
- Audit：`audit-{YYYY-MM-DD}.md`

**兼容说明**：
- 旧任务目录里可能仍有 `plan-*` / `audit-*` 示例文件，它们只作为历史任务归档
- 新的 plan / report 草稿写入 `.agent/plans/` 和 `.agent/reports/`，需要长期保留的正式版本写入 `docs/plans/` 和 `docs/reports/`

## 🚪 Vibe Guard 流程

每个任务遵循 Vibe Guard 流程，每层有对应的 Gate 验证：

| 层级 | 文档 | Gate | 职责 |
|------|------|------|------|
| 1. PRD（认知层） | prd-*.md | Scope Gate | 定义业务目标、边界、数据流 |
| 2. Spec（规范层） | spec-*.md | Spec Gate | 定义接口契约、不变量、边界行为 |
| 3. Plan（执行计划层） | plan-*.md | Plan Gate | 圈定上下文、拆分任务、识别风险 |
| 4. Test（测试层） | test-*.md | Test Gate | 编写测试用例、TDD 流程 |
| 5. Code（代码实现层） | code-*.md | Code Gate | 记录实现、复杂度报告 |
| 6. Review（AI 审计层） | audit-*.md | Audit Gate | AI 审计、人类决议 |

## 📝 如何使用

### 创建新任务

1. 创建对应目录：
   ```bash
   mkdir -p docs/specs docs/plans docs/reports
   ```

2. 从模板创建正式文档（模板位于 `.agent/templates/`）：
   ```bash
   cp .agent/templates/tech-spec.md docs/specs/<name>.md
   cp .agent/templates/plan.md docs/plans/<name>.md
   cp .agent/templates/prd.md docs/prds/<name>.md
   ```

3. 替换占位符并填写内容

4. 按 Vibe Guard 流程逐步推进
   - 临时草稿优先写入 `.agent/plans/`、`.agent/reports/`
   - 需要长期保留的正式版本写入 `docs/plans/`、`docs/reports/`
   - 长期结论写入 issue comment 或 PR comment

### 查看任务状态

对应文档可在 frontmatter 中记录当前层级、状态和 Gate 结果。

## 🔗 相关文档

- **[AGENTS.md](../AGENTS.md)** - AI Agent 入口指南
- **[CLAUDE.md](../CLAUDE.md)** - 项目上下文和硬性规则
- **[SOUL.md](../SOUL.md)** - 项目宪法和核心原则
- **[.claude/rules/README.md](../.claude/rules/README.md)** - AI 编码规则与标准
- **[.agent/README.md](../.agent/README.md)** - AI 工作流与治理
- **[agent-document-lifecycle-standard.md](standards/agent-document-lifecycle-standard.md)** - Agent 文档生命周期标准

## 📚 文档 vs AI 工作区

**重要区分**：
- **`docs/`** - 人类主权区，存放给人类阅读的正式规范、计划、报告和历史归档
- **`.claude/rules/`** - AI 规则区，存放架构规则、编码标准和模式约束
- **`.agent/`** - AI 工作区，存放 AI 使用的模板、工作流、记忆和临时产物

模板文件位于 `.agent/templates/`，临时计划与报告分别位于 `.agent/plans/` 和 `.agent/reports/`；正式计划与报告分别位于 `docs/plans/` 和 `docs/reports/`。

## 🆘 需要帮助？

- 阅读 [doc-organization.md](standards/doc-organization.md) 了解详细的文档组织标准
- 阅读 [vibe-workflow-paradigm.md](prds/vibe-workflow-paradigm.md) 了解 Vibe Guard 范式
- 阅读 [standards/v3/](standards/v3/) 了解 V3 的正式语义边界
- 查看 `docs/specs/`、`docs/plans/` 和 `docs/reports/` 中的现有文档作为参考

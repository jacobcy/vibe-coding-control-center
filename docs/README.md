# Vibe Center 3.0 文档

本目录包含 Vibe Center 3.0 的所有人类可读文档。V3 规范优先，V2 兼容语义只在历史和辅助边界里保留。

## 📁 目录结构

```
docs/
├── README.md                        # 本文件：文档总览
├── standards/                       # 标准和规范文档
│   ├── DOC_ORGANIZATION.md         # 文档组织标准（必读）
│   ├── cognition-spec-dominion.md  # 宪法大纲：Vibe Guard 流程定义
│   ├── ...                         # 其他现行标准
│   └── v3/                          # V3 命令、数据、技能与 handoff 标准
├── prds/                           # 产品需求文档（全局 PRD）
│   ├── vibe-workflow-paradigm.md   # 总 PRD：Vibe Guard 范式
│   └── ...                         # 其他全局 PRD
├── references/                     # 外部参考资料
│   └── ...                         # 收集的外部文档、论文、资料等
├── tasks/                          # 任务文档（按 issue 组织）
│   └── {Task_ID}/                  # 任务镜像与导航
├── archive/                        # 历史归档
└── ...                             # 其他现行文档
```

## 🎯 文档分类

### 标准文档 (`standards/`)
存放项目的标准、规范、架构设计等元文档。这些文档定义了"如何做事"。

**必读文档**：
- **[glossary.md](standards/glossary.md)** - 项目术语真源，统一概念定义与别称边界
- **[action-verbs.md](standards/action-verbs.md)** - 高频动作词真源，统一默认含义与执行提醒
- **[vibe3-architecture-convergence-standard.md](standards/vibe3-architecture-convergence-standard.md)** - Vibe3 目标架构总纲，解释最终分层、收敛方向与 domain-first 的取舍
- **[vibe3-role-checks-and-balances-standard.md](standards/vibe3-role-checks-and-balances-standard.md)** - Vibe3 角色制衡架构标准，理解 Governance / Apply / Manager / Plan / Run / Review 的权力边界与制衡关系
- **[agent-debugging-standard.md](standards/agent-debugging-standard.md)** - Agent 调试标准，统一 supervisor 与 manager 链调试方法
- **[doc-organization.md](standards/doc-organization.md)** - 文档组织标准，定义命名规范和使用指南
- **[cognition-spec-dominion.md](standards/cognition-spec-dominion.md)** - 宪法大纲，定义 Vibe Guard 流程

**V3 规范目录**：
- **[standards/v3/](standards/v3/)** - V3 命令、数据、技能、handoff 与运行时标准真源目录
### 全局 PRD (`prds/`)
存放不针对特定任务的全局性产品需求文档。

**核心 PRD**：
- **[vibe-workflow-paradigm.md](prds/vibe-workflow-paradigm.md)** - 总 PRD，定义 Vibe Guard 范式

### 外部参考资料 (`references/`)
存放从外部收集的参考资料，包括但不限于：
- 技术文档和论文
- 设计参考和案例研究
- 行业标准和最佳实践
- 第三方工具和框架文档

**用途**：为项目决策和实现提供外部知识支持，不属于项目自身文档。

### 任务文档 (`tasks/`)
每个任务一个子目录，按 GitHub issue 组织任务镜像。

**原则**：
- issue 是任务身份真源
- task README 只做导航、状态和阶段记录
- 需要长期保留的结论写到 issue comment 或 PR comment

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
- 新的 plan / report 一律写入 `.agent/plans/` 和 `.agent/reports/`

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

1. 创建任务目录：
   ```bash
   mkdir -p docs/tasks/2024-01-15-feature-name
   ```

2. 从模板创建文档（模板位于 `.agent/templates/`）：
   ```bash
   cp .agent/templates/task-readme.md docs/tasks/2024-01-15-feature-name/README.md
   cp .agent/templates/prd.md docs/tasks/2024-01-15-feature-name/prd-v1-initial.md
   ```

3. 替换占位符并填写内容

4. 按 Vibe Guard 流程逐步推进，长期结论写入 issue comment 或 PR comment

### 查看任务状态

每个任务的 `README.md` 包含：
- 当前所在层级
- Vibe Guard 各 Gate 的通过状态
- 文档导航链接

## 🔗 相关文档

- **[AGENTS.md](../AGENTS.md)** - AI Agent 入口指南
- **[CLAUDE.md](../CLAUDE.md)** - 项目上下文和硬性规则
- **[SOUL.md](../SOUL.md)** - 项目宪法和核心原则
- **[.agent/README.md](../.agent/README.md)** - AI 工作流和规则
- **[agent-document-lifecycle-standard.md](standards/agent-document-lifecycle-standard.md)** - Agent 文档生命周期标准

## 📚 文档 vs AI 工作区

**重要区分**：
- **`docs/`** - 人类主权区，存放给人类阅读的正式规范、任务镜像和历史归档
- **`.agent/`** - AI 工作区，存放 AI 使用的模板、规则、工作流和临时产物

模板文件位于 `.agent/templates/`，临时计划与报告分别位于 `.agent/plans/` 和 `.agent/reports/`。

## 🆘 需要帮助？

- 阅读 [doc-organization.md](standards/doc-organization.md) 了解详细的文档组织标准
- 阅读 [vibe-workflow-paradigm.md](prds/vibe-workflow-paradigm.md) 了解 Vibe Guard 范式
- 阅读 [standards/v3/](standards/v3/) 了解 V3 的正式语义边界
- 查看 `docs/tasks/` 中的现有任务作为参考

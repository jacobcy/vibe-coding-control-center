# Vibe Ecosystem vs Vibe-Center Boundary

> **文档定位**：定义 vibe 生态内容与 vibe-center 项目专属内容的边界
> **维护者**：Vibe Team
> **关联**：[glossary.md](glossary.md)、[CLAUDE.md](../../CLAUDE.md)

## 核心概念

Vibe 是一个**跨项目的 AI 开发编排工具**。它被安装到其他项目中，提供 CLI 命令、
角色执行管线、orchestra 服务和治理能力。

Vibe-center 是 vibe 工具链自身的开发仓库。它**同时也是** vibe 的用户之一。

区分这两者的意义在于：当 vibe 在其他项目中运行时，只应注入生态级内容，
不应注入 vibe-center 项目专属的开发约定。

## MaterialLayer 映射

| MaterialLayer | 含义 | 跨项目是否注入 |
|---|---|---|
| `core_invariant` | vibe 生态基础能力，任何项目都需要 | 是 |
| `repo_profile` | 目标仓库自身的配置描述 | 是（目标仓库提供） |
| `project_policy` | vibe-center 项目专属约定 | 否 |
| `runtime_evidence` | 运行时动态上下文（flow 状态等） | 是 |

## 分类标准

判断一个材料属于生态还是项目专属，使用以下三问法：

1. **其他项目使用 vibe 时是否需要此能力？** YES = 生态
2. **内容是否引用 vibe-center 的代码结构、LOC 限制、特定开发约定？** YES = 项目专属
3. **移除此内容后，vibe 在其他项目中能否正常运行？** NO = 生态

## 具体分类

### 生态级内容 (core_invariant)

以下内容是 vibe 工具链的核心能力，任何使用 vibe 的项目都需要：

**CLI 与工具链**
- `vibe3 flow/task/run/plan/review` 等命令
- Plan/Run/Review 角色执行管线
- `vibe3 handoff` 交接协议

**策略材料**
- `supervisor/policies/common.md` — vibe 工具链操作指南（如何使用 vibe 命令）
- `supervisor/policies/plan.md` — plan 模式策略
- `supervisor/policies/run.md` — run 模式策略
- `supervisor/policies/review.md` — review 模式策略

**Orchestra 与治理**
- `supervisor/apply.md` — supervisor handoff 执行材料
- `supervisor/governance/assignee-pool.md` — Issue 池管理
- `supervisor/governance/roadmap-intake.md` — Roadmap 摄取治理
- `supervisor/governance/cron-supervisor.md` — 定期清理治理
- `supervisor/governance/code-auditor.md` — 代码质量审计
- `supervisor/governance/audit-observation.md` — 失败 flow 观察

**角色定义**
- Manager 角色的核心契约（Role, Permission Contract, Architecture Contract）
- Supervisor 角色基础设施（vibe-orchestrator, vibe-audit, vibe-scope-gate 等）

**Prompt 组件**
- plan/run/review 的 policy、output_format、exit_contract 等 section
- common.rules provider（工具链操作指南）

### 项目专属内容 (project_policy)

以下内容仅适用于 vibe-center 仓库自身的开发：

**开发约定**
- `supervisor/policies/common-develop.md` — vibe-center 内部开发规则
  （LOC 限制、跨层检查、vibe-center 特定的编码标准）

**角色材料中的项目特定部分**
- `supervisor/manager.md` 中引用 vibe-center 特定路径和约定的内容
  （handoff 格式示例中的 vibe-center 路径、特定测试命令等）

## 当前已知问题

### 1. Governance 材料错误分类

`config/prompts/prompt-recipes.yaml` 中 `governance.scan` 的 5 个
material_catalog 条目全部标注为 `project_policy`。

根据上述分类标准，这些治理材料是生态级能力，应标注为 `core_invariant`。

**受影响条目**：
- `supervisor/governance/assignee-pool.md`
- `supervisor/governance/roadmap-intake.md`
- `supervisor/governance/cron-supervisor.md`
- `supervisor/governance/code-auditor.md`
- `supervisor/governance/audit-observation.md`

### 2. Layer 标注设计冗余

`common-develop.rules` 在 6 个 recipe variant 中各自重复标注
`layer: project_policy`。layer 是材料的固有属性，不应在每个引用处重复定义。

改进方向：在 adapter 或 provider 注册层定义 layer，recipe 引用处自动继承。

### 3. Manager 材料可能需要拆分

`supervisor/manager.md`（64K）同时包含：
- 生态级内容：角色定义、权限契约、架构契约、决策逻辑
- 项目专属内容：handoff 格式示例中的 vibe-center 路径

当前整体标注为 `project_policy`，可能需要类似 common.md 的拆分处理。

## 参考

- [CLAUDE.md](../../CLAUDE.md) — 项目上下文
- [glossary.md](glossary.md) — 术语定义
- [v3-module-architecture-standard.md](v3-module-architecture-standard.md) — 模块架构

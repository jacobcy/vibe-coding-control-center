# Design: Task Registry Audit & Repair

## Context

### Current State

Vibe 的任务管理系统依赖 `registry.json` 作为单一真源，但存在以下数据完整性问题：

1. **注册遗漏**：开发者直接开发功能，忘记通过 `vibe task` 注册
2. **多任务 PR**：一个 PR 可能完成多个任务，但只绑定一个
3. **OpenSpec 同步延迟**：changes 目录中有未同步到 registry 的任务
4. **数据质量差**：`worktrees.json` 中大量 `branch: null`，阻断 PR 检测

当前 `vibe-task` skill 只有查看能力，无法核对和修复这些问题。

### Stakeholders

- **开发者**：需要快速发现并修复任务注册问题
- **AI Agent**：需要准确的任务状态来做出决策
- **vibe check**：依赖完整的任务注册来检测已完成任务

### Constraints

- 不能破坏现有的 `vibe task` 命令结构
- 必须保持 Shell 层的简洁性（LOC 限制）
- 需要复用现有的 PR 检测基础设施（`vibe-check-smart-sync`）

## Goals / Non-Goals

### Goals

1. **实现多维度任务核对** - 从分支、PR、OpenSpec 三个来源核对任务注册
2. **提供智能修复建议** - 发现问题后给出可执行的修复方案
3. **修复数据质量问题** - 自动修复 `worktrees.json` 中的 null branch
4. **集成现有流程** - 可独立运行，也可作为 `vibe check` 的一部分

### Non-Goals

1. **自动执行修复** - 所有修复都需要用户确认，不自动修改数据
2. **复杂的 PR 分析** - 第一版只做简单的文本匹配，不做深度 AI 分析
3. **跨仓库核对** - 只核对当前仓库，不涉及多仓库任务管理
4. **历史任务追溯** - 不追溯已归档的任务，只检查活跃任务

## Decisions

### D1: 核对流程的层次结构

**Decision**: 采用三层核对流程（数据质量 → 确定性规则 → 启发式分析）

**Rationale**:
- 数据质量问题是根本原因（null branch），必须先修复
- 确定性规则（分支名匹配）准确度高，优先使用
- 启发式分析（PR 内容）有误判风险，放在最后

**Alternatives Considered**:
- **单层混合核对**：所有来源一起核对 → 难以定位问题根源
- **仅确定性规则**：只做分支匹配 → 会漏掉未创建分支的任务

**Implementation**:
```
vibe task audit (Shell 层 - 确定性核对)
  ├── Phase 1: Data Quality Check
  │   └── 修复 worktrees.json 的 null branch
  └── Phase 2: Deterministic Audit
      ├── 分支 → 任务核对
      └── OpenSpec changes → registry 核对

/vibe-task audit (Skill 层 - 语义分析)
  ├── 调用 Shell 获取 PR 数据
  ├── 分析 PR 语义 (Subagent)
  ├── 检查 docs/plans、docs/prds
  ├── 生成建议并询问用户
  └── 调用 Shell 执行操作
```

### D2: 实现位置（Shell vs Skill）

**Decision**: Shell 层只提供数据和确定性操作，Skill 层做语义分析和决策

**Rationale**:
- 严格遵循三层架构原则（Shell 物理真源，Skill 智能编排）
- Shell 层保持无状态、无判断，只提供确定性核对和数据查询
- Skill 层处理所有语义分析、智能判断和用户交互

**Shell 层职责** (只提供数据和确定性操作):
- `vibe task audit --fix-branches` - 修复 null branch 字段（确定性）
- `vibe task audit --check-branches` - 核对分支任务注册（确定性）
- `vibe task audit --check-openspec` - 核对 OpenSpec 同步（确定性）
- `vibe flow review --json` - 提供 PR 原始数据（数据）
- `vibe task list --json` - 提供任务列表（数据）
- `vibe task add/update/remove` - 任务 CRUD（原子操作）

**Skill 层职责** (语义分析和决策):
- 调用 Shell 获取数据
- 分析 PR 语义、文档内容
- 判断是否需要创建/更新任务
- 与用户交互确认
- 调用 Shell 执行操作
- `vibe task audit --check-openspec` - 核对 OpenSpec 同步

**Skill Workflow**:
- `skills/vibe-task/SKILL.md` 扩展 audit 模式
- 调用 Shell 命令获取数据
- 汇总结果并给出修复建议

### D3: PR 任务识别策略

**Decision**: 第一版只做简单的文本匹配，不做 AI 分析

**Rationale**:
- AI 分析成本高，需要调用 Subagent
- 简单的文本匹配已能覆盖大部分场景（分支名、commit message）
- 后续可以根据反馈决定是否增加 AI 分析

**Matching Rules**:
1. **分支名匹配**：PR 分支名包含 task_id 或 slug
2. **Commit message 匹配**：commit message 包含 task_id
3. **PR description 匹配**：PR 描述中提到 "完成 #task_id" 或类似表达

**Alternatives Considered**:
- **AI 语义分析**：理解 PR 内容，智能识别完成的任务 → 成本高，第一版不做
- **仅 PR title 匹配**：太局限，会漏掉多任务 PR

### D4: 修复模式（Batch vs Interactive）

**Decision**: 提供两种模式 - 批量预览 + 交互确认

**Rationale**:
- 批量预览让用户看到所有问题
- 交互确认允许用户选择性修复
- 平衡效率和安全

**Workflow**:
```bash
vibe task audit
  → 显示所有发现的问题
  → 用户选择修复模式：
     1. 批量修复所有
     2. 逐个确认
     3. 仅查看不修复
```

### D5: 与 vibe check 的集成

**Decision**: Phase 2 核对作为 `vibe check` 的可选步骤

**Rationale**:
- `vibe check` 专注于 PR merged 检测
- 任务注册核对是独立的能力，不应强制执行
- 用户可以选择在 `vibe check` 中启用或独立运行

**Implementation**:
```bash
vibe check --audit-tasks  # 启用任务注册核对
vibe task audit           # 独立运行
```

## Risks / Trade-offs

### Risk 1: 误判导致错误注册

**Risk**: 文本匹配可能误判，将不相关的分支/PR 关联到任务

**Mitigation**:
- 使用高置信度规则（完全匹配 task_id）
- 中等置信度规则需要用户确认
- 提供撤销机制（用户可以手动删除错误注册的任务）

### Risk 2: 数据质量修复的副作用

**Risk**: 自动修复 `worktrees.json` 的 null branch 可能覆盖正确的数据

**Mitigation**:
- 只在 branch 为 null 时修复
- 修复前备份原文件
- 显示修复内容，让用户确认

### Risk 3: 性能问题

**Risk**: 大量分支/PR 时，核对过程可能很慢

**Mitigation**:
- 默认只核对活跃分支（有 worktree 的）
- 提供 `--all` 参数核对所有分支
- PR 核对限制最近 N 个（默认 50）

### Trade-off: 准确性 vs 覆盖率

**Trade-off**: 简单规则准确但覆盖率低，AI 分析覆盖率高但可能误判

**Decision**: 第一版优先准确性，接受较低的覆盖率

**Reasoning**:
- 错误注册比漏检更糟糕（污染 registry）
- 用户可以手动补充未检测到的任务
- 后续可以增加 AI 分析作为可选能力

## Implementation Phases

### Phase 1: Data Quality Repair (MVP)

**Scope**: 修复 worktrees.json 的 null branch

**Commands**:
- `vibe task audit --fix-branches`
- `vibe task audit --check-branches`

**Success Criteria**:
- 所有活跃 worktree 的 branch 字段不为 null
- 不覆盖已有数据

### Phase 2: Deterministic Audit

**Scope**: 分支核对 + OpenSpec 核对

**Commands**:
- `vibe task audit --check-openspec`

**Success Criteria**:
- 检测到所有未注册的分支任务
- 检测到所有未同步的 OpenSpec changes

### Phase 3: Skill 层智能审计

**Scope**: Skill 层的语义分析和决策（从 PR、文档识别任务）

**实现位置**: skills/vibe-task/SKILL.md

**Shell 层支持** (只提供数据，不做判断):
- `vibe flow review --json` - 提供 PR 原始数据（描述、评论、commits）
- `vibe task list --json` - 提供任务列表
- `vibe task add/update/remove` - 提供任务 CRUD 操作

**Skill 层职责** (语义分析和决策):
1. 调用 Shell 获取 PR 数据和任务列表
2. 分析 PR 描述、评论、commits 的语义
3. 检查 docs/plans、docs/prds 中的散落任务
4. 判断是否需要创建新任务或更新现有任务
5. 生成智能建议并与用户交互确认
6. 调用 Shell 执行用户确认的操作

**Success Criteria**:
- Skill 层能够从 PR 语义识别完成的任务
- Skill 层能够从文档中搜集散落的任务
- 提供清晰的用户交互和确认流程
- Shell 层保持无状态、无判断

## Open Questions

1. **是否需要支持自动同步 OpenSpec changes？**
   - 当前设计：只检测未同步，需要手动运行 `vibe task sync`
   - 可选：自动同步未注册的 changes

2. **PR 核对的触发时机？**
   - 选项 A：只在 `vibe check` 中触发
   - 选项 B：在 `vibe task audit` 中也可触发
   - 当前设计：两者都支持

3. **如何处理已归档的任务？**
   - 当前设计：不核对已归档任务
   - 可选：提供 `--include-archived` 参数

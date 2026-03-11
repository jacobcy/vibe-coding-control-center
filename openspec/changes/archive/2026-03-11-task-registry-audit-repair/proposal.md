# Task Registry Audit & Repair

## Why

当前 `vibe check` 的智能任务状态同步有一个关键假设：所有任务都已正确注册到 registry。但实际上存在以下问题：

1. **PR 完成任务未注册**：开发者可能完成了一个任务但没有通过 `vibe task` 注册
2. **一个 PR 完成多个任务**：PR 可能包含多个功能的实现，但只关联了一个任务
3. **OpenSpec 同步遗漏**：从 OpenSpec 同步过来的 changes 可能没有正确注册到 registry
4. **分支-任务绑定丢失**：worktrees.json 中的 branch 字段为 null，导致无法检测 PR 状态

这些问题会导致 `vibe check` 漏检已完成的任务，造成状态不一致。

**Why Now**: `vibe-check-smart-sync` 已实现基础的 PR 检测能力，但需要确保任务注册的完整性才能发挥最大价值。

## What Changes

### 核心变更

1. **扩展 `vibe-task` skill** - 从单纯的"查看"能力扩展为"查看 + 核对 + 修复"
2. **新增任务注册核对流程** - 检查所有可能的任务来源并对比 registry
3. **新增智能任务修复建议** - 发现未注册任务后，提供修复建议和批量注册能力
4. **新增 PR → Task 关联分析** - 分析 PR 的 commits 和描述，智能识别完成的任务

### 具体能力

- **分支任务核对**：检查所有分支是否都注册了对应的任务
- **PR Commit 分析**：解析 PR 的 commits 和描述，识别可能完成的任务
- **OpenSpec 同步核对**：对比 OpenSpec changes 和 registry，发现未注册的任务
- **批量任务注册**：一键修复所有未注册的任务
- **数据质量修复**：修复 worktrees.json 中的 null branch 字段

## Capabilities

### New Capabilities

- **`task-registry-audit`**: 核对任务注册完整性，包括分支、PR、OpenSpec 多维度检查
- **`pr-task-detection`**: 从 PR 的 commits、描述、评论中智能识别完成的任务
- **`task-registry-repair`**: 自动修复任务注册问题，包括批量注册和数据质量修复

### Modified Capabilities

- **`task-overview`**: 扩展现有的 vibe-task 查看能力，增加任务健康度指标和未注册任务提示

## Impact

### 受影响的文件

- **`skills/vibe-task/SKILL.md`** - 扩展 skill 定义，增加核对和修复流程
- **`lib/task.sh`** - 可能需要新增 Shell 层的核对和修复命令
- **`lib/check.sh`** - 可能需要在 `vibe check` 中调用任务注册核对
- **`scripts/`** - 可能需要新的辅助脚本进行 PR 分析和任务检测

### 数据影响

- **registry.json** - 会新增自动注册的任务
- **worktrees.json** - 会修复 null branch 字段

### 依赖

- 需要调用 `gh` CLI 获取 PR 信息
- 需要读取 OpenSpec changes 目录
- 可能需要调用 AI 分析 PR 内容（复用 vibe-check 的 Subagent 模式）

## Design Principles

1. **渐进式智能**：优先使用确定性规则（如分支名匹配），再使用启发式分析（PR 内容分析）
2. **用户确认**：所有修复操作都需要用户确认，不自动执行
3. **数据质量优先**：先修复数据质量问题（如 null branch），再进行任务检测
4. **与现有流程集成**：可以作为 `vibe check` 的一部分，也可以独立运行 `vibe task audit`

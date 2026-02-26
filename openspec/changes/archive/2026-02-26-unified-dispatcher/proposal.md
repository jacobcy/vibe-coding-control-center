## Why

当前 Vibe Workflow Engine 支持多种工作流框架（Superpower、OpenSpec），但用户需要显式指定框架。缺乏统一的调度层导致：
1. 用户体验不透明 - 需要了解不同框架的区别
2. 缺乏记忆能力 - 每次都要重新选择框架
3. 无法智能匹配 - 没有基于历史自动推荐的能力

## What Changes

1. **新增智能调度器** - 在 vibe-orchestrator 的 Gate 0 实现
2. **需求分析能力** - 分析复杂度、类型、范围、不确定性
3. **历史 Pattern 匹配** - 基于 task.md 的历史记录做智能推荐
4. **无感自动选择** - 高置信度场景直接进入，用户无感知
5. **扩展 task.md 格式** - 添加 `framework` 字段存储框架选择

## Capabilities

### New Capabilities
- `framework-dispatcher`: 智能框架调度能力，支持需求分析、历史匹配、无感路由

### Modified Capabilities
- 无（现有 Vibe Orchestrator 四闸机制不变，Gate 0 是新增的前置层）

## Impact

- **修改**: `.agent/context/task.md` - 添加 framework 字段
- **修改**: `skills/vibe-orchestrator/SKILL.md` - 添加 Gate 0: Intent Gate

# migrate-to-v3 Proposal

## Why

Vibe Center 2.0 的现有架构在演进过程中积累了一些技术债务，包括模块边界不清晰、职责划分模糊等问题。v3 迁移旨在通过重新设计核心架构，建立清晰的模块边界和职责分离，为未来的功能扩展和维护奠定坚实基础。

## What Changes

- **架构重构**：建立清晰的 control-plane（控制平面）架构，分离关注点
- **模块重组**：将现有 lib/ 模块按职责重新划分为核心层、服务层和工具层
- **配置分离**：将运行时配置与代码逻辑完全分离
- **能力抽象**：将分散的功能点抽象为独立的能力模块（capabilities）
- **生命周期管理**：建立统一的命令生命周期管理机制

## Capabilities

### New Capabilities

- `control-plane-core`: 控制平面核心架构，包括命令路由、生命周期管理、模块编排
- `capability-registry`: 能力注册中心，统一管理所有能力模块的注册、发现和调用
- `config-management`: 配置管理系统，提供版本化的配置管理和环境隔离
- `lifecycle-hooks`: 生命周期钩子系统，支持命令执行前后的扩展点

### Modified Capabilities

- `framework-dispatcher`: 从简单的框架选择器升级为智能路由系统，集成到 control-plane
- `skill-optimizations`: 扩展防污染机制，增加上下文预算管理和智能摘要能力

## Impact

### 代码影响
- **核心模块**：所有 lib/ 和 bin/ 下的文件需要按新架构重组
- **配置文件**：config/ 目录结构需要调整以支持环境隔离
- **技能系统**：skills/ 需要适配新的能力注册机制

### API 变更
- **BREAKING**: CLI 命令参数格式可能有调整，但保持向后兼容的别名
- **BREAKING**: 内部模块间调用接口重新设计

### 依赖影响
- 保持对外部工具的依赖不变（bats, jq, curl, gh 等）
- 可能引入新的开发依赖用于架构验证

### 系统影响
- 现有 worktree 工作流需要适配新架构
- Agent 规则体系（.agent/rules/）需要更新以反映新架构

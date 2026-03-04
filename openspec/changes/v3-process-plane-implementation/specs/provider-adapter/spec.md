# Provider Adapter Specification

## Overview

Provider Adapter 定义了 provider 接入流程平面的标准化接口和规范。所有 provider（OpenSpec、Supervisor、Kiro、Manual）必须实现该接口，才能被路由器调用。

## ADDED Requirements

### Requirement: Implement adapter interface

系统 SHALL 要求所有 provider 实现 4 个核心接口（route/start/status/complete）。

#### Scenario: Implement route interface
- **WHEN** provider adapter 实现 route(task) 接口
- **THEN** adapter SHALL 返回布尔值，表示是否接受该任务

#### Scenario: Implement start interface
- **WHEN** provider adapter 实现 start(task, context) 接口
- **THEN** adapter SHALL 启动 provider 执行
- **AND** 返回 provider_ref

#### Scenario: Implement status interface
- **WHEN** provider adapter 实现 status(provider_ref) 接口
- **THEN** adapter SHALL 返回 provider 执行状态 {state, metadata}

#### Scenario: Implement complete interface
- **WHEN** provider adapter 实现 complete(provider_ref) 接口
- **THEN** adapter SHALL 完成 provider 执行
- **AND** 返回结果 {result, artifacts}

### Requirement: Adapter registration

系统 SHALL 支持通过标准方式注册 provider adapter，无需修改核心路由逻辑。

#### Scenario: Register adapter via directory
- **WHEN** 将 adapter 文件放入 adapters/ 目录
- **THEN** 系统 SHALL 自动加载该 adapter

#### Scenario: Adapter file naming convention
- **WHEN** 创建 adapter 文件
- **THEN** 文件名 SHALL 遵循格式 <provider>-adapter.sh（如 openspec-adapter.sh）

#### Scenario: Adapter metadata
- **WHEN** 注册 adapter
- **THEN** adapter SHALL 提供元数据（名称、版本、能力描述）

### Requirement: Adapter validation

系统 SHALL 验证 adapter 实现了所有必需接口，验证失败时拒绝注册。

#### Scenario: Validate required interfaces
- **WHEN** 注册 adapter
- **THEN** 系统 SHALL 检查 adapter 实现了 route/start/status/complete 接口

#### Scenario: Reject invalid adapter
- **WHEN** adapter 缺少必需接口
- **THEN** 系统 SHALL 拒绝注册
- **AND** 记录错误原因

#### Scenario: Test adapter interfaces
- **WHEN** 注册 adapter
- **THEN** 系统 SHALL 调用每个接口进行测试
- **AND** 确保接口返回格式正确

### Requirement: Adapter isolation

系统 SHALL 确保 adapter 之间相互隔离，一个 adapter 的失败不影响其他 adapter。

#### Scenario: Isolate adapter execution
- **WHEN** adapter 执行失败
- **THEN** 系统 SHALL 捕获错误
- **AND** 不影响其他 adapter 的执行

#### Scenario: Isolate adapter state
- **WHEN** adapter 维护内部状态
- **THEN** 系统 SHALL 确保状态不与其他 adapter 共享

### Requirement: Adapter error handling

系统 SHALL 要求 adapter 实现标准错误处理，返回统一格式的错误信息。

#### Scenario: Return standard error format
- **WHEN** adapter 接口执行失败
- **THEN** adapter SHALL 返回错误格式 {error: "...", code: "...", details: {...}}

#### Scenario: Log adapter errors
- **WHEN** adapter 执行失败
- **THEN** adapter SHALL 记录错误日志
- **AND** 包含足够的上下文信息

#### Scenario: Graceful degradation on error
- **WHEN** adapter 执行失败
- **THEN** adapter SHALL 尝试优雅降级
- **AND** 不留下不一致状态

### Requirement: Adapter resource management

系统 SHALL 要求 adapter 管理自身资源，避免资源泄漏。

#### Scenario: Clean up resources on complete
- **WHEN** complete(provider_ref) 被调用
- **THEN** adapter SHALL 清理所有分配的资源

#### Scenario: Clean up resources on failure
- **WHEN** adapter 执行失败
- **THEN** adapter SHALL 释放已分配的资源

#### Scenario: Report resource usage
- **WHEN** adapter 执行
- **THEN** adapter SHALL 报告资源使用情况（可选）

### Requirement: Adapter versioning

系统 SHALL 支持 adapter 版本管理，允许同时存在多个版本。

#### Scenario: Support multiple adapter versions
- **WHEN** adapters/ 目录存在多个版本的 adapter（如 openspec-adapter-v1.sh, openspec-adapter-v2.sh）
- **THEN** 系统 SHALL 支持选择特定版本

#### Scenario: Default to latest version
- **WHEN** 未指定 adapter 版本
- **THEN** 系统 SHALL 默认使用最新版本

#### Scenario: Migrate between adapter versions
- **WHEN** 升级 adapter 版本
- **THEN** 系统 SHALL 提供迁移指南
- **AND** 保持向后兼容（如可能）

### Requirement: Adapter testing

系统 SHALL 提供 adapter 测试框架，支持验证 adapter 实现的正确性。

#### Scenario: Test adapter with mock tasks
- **WHEN** 运行 adapter 测试
- **THEN** 系统 SHALL 使用 mock 任务测试 route/start/status/complete 接口

#### Scenario: Validate adapter output format
- **WHEN** 测试 adapter
- **THEN** 系统 SHALL 验证接口返回格式符合规范

#### Scenario: Test adapter error handling
- **WHEN** 测试 adapter
- **THEN** 系统 SHALL 测试错误场景（如无效输入、资源不足）

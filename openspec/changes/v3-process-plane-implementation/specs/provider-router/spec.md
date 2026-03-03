# Provider Router Specification

## Overview

Provider Router 是流程平面的核心组件，负责 provider 的路由、启动、状态查询和完成。它提供统一的接口，支持多种 provider（OpenSpec、Supervisor、Kiro、Manual）的接入和管理。

## ADDED Requirements

### Requirement: Route task to appropriate provider

系统 SHALL 根据任务上下文和路由策略，选择合适的 provider 处理任务。

#### Scenario: Route spec-driven task to OpenSpec
- **WHEN** 任务类型为 spec-driven 且风险等级为低
- **THEN** 系统 SHALL 选择 OpenSpec provider

#### Scenario: Route high-risk task to Supervisor
- **WHEN** 任务类型为 spec-driven 且风险等级为高
- **THEN** 系统 SHALL 选择 Supervisor provider

#### Scenario: Route ad-hoc task to Kiro
- **WHEN** 任务类型为 ad-hoc 且 AI 资源充足
- **THEN** 系统 SHALL 选择 Kiro provider

#### Scenario: Fallback to Manual when no provider available
- **WHEN** 所有高级 provider 都不可用
- **THEN** 系统 SHALL 选择 Manual provider

### Requirement: Start provider execution

系统 SHALL 通过 adapter 接口启动 provider 执行，并返回 provider_ref 供后续查询。

#### Scenario: Start OpenSpec provider
- **WHEN** 调用 start(task, context) 且 provider 为 OpenSpec
- **THEN** 系统 SHALL 调用 OpenSpec adapter 的 start 方法
- **AND** 返回 provider_ref 包含 provider 名称和任务 ID

#### Scenario: Pass context to provider
- **WHEN** 调用 start(task, context)
- **THEN** 系统 SHALL 将 context（任务类型、风险等级、资源配置）传递给 provider adapter

#### Scenario: Handle provider start failure
- **WHEN** provider 启动失败
- **THEN** 系统 SHALL 返回错误信息
- **AND** 记录失败日志

### Requirement: Query provider status

系统 SHALL 支持通过 provider_ref 查询 provider 的执行状态。

#### Scenario: Query in-progress status
- **WHEN** 调用 status(provider_ref) 且 provider 正在执行
- **THEN** 系统 SHALL 返回状态 {state: "in_progress", metadata: {...}}

#### Scenario: Query completed status
- **WHEN** 调用 status(provider_ref) 且 provider 已完成
- **THEN** 系统 SHALL 返回状态 {state: "done", metadata: {...}}

#### Scenario: Handle invalid provider_ref
- **WHEN** 调用 status(provider_ref) 且 provider_ref 无效
- **THEN** 系统 SHALL 返回错误信息

### Requirement: Complete provider execution

系统 SHALL 支持 provider 执行完成后的清理和结果返回。

#### Scenario: Complete successful execution
- **WHEN** 调用 complete(provider_ref) 且 provider 执行成功
- **THEN** 系统 SHALL 返回 {result: "success", artifacts: [...]}
- **AND** 清理 provider 资源

#### Scenario: Complete failed execution
- **WHEN** 调用 complete(provider_ref) 且 provider 执行失败
- **THEN** 系统 SHALL 返回 {result: "failed", error: "..."}
- **AND** 清理 provider 资源

### Requirement: Aggregate provider status for control plane

系统 SHALL 将 provider 内部状态聚合为控制平面可识别的状态（in_progress/done），不暴露 provider 内部步骤。

#### Scenario: Aggregate Supervisor six-layer status
- **WHEN** Supervisor provider 处于 "Scoping" 阶段
- **THEN** 系统 SHALL 返回聚合状态 {state: "in_progress"}

#### Scenario: Aggregate OpenSpec status
- **WHEN** OpenSpec provider 处于 "execution" 阶段
- **THEN** 系统 SHALL 返回聚合状态 {state: "in_progress"}

#### Scenario: Do not expose internal steps
- **WHEN** 任何 provider 的内部状态
- **THEN** 系统 SHALL 不将内部步骤映射为控制平面的 "blocked" 状态

### Requirement: Support provider registration

系统 SHALL 支持动态注册新 provider adapter，无需修改核心路由逻辑。

#### Scenario: Register new provider adapter
- **WHEN** 添加新的 provider adapter 文件到 adapters/ 目录
- **THEN** 系统 SHALL 自动识别并加载该 adapter
- **AND** 该 provider 可用于路由

#### Scenario: Validate adapter interface
- **WHEN** 注册新的 provider adapter
- **THEN** 系统 SHALL 验证 adapter 实现了必需的接口（route/start/status/complete）
- **AND** 验证失败时拒绝注册

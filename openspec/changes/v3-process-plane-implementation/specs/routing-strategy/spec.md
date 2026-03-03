# Routing Strategy Specification

## Overview

Routing Strategy 负责根据任务上下文（任务类型、风险等级、资源配置）决定使用哪个 provider。它提供可配置的路由规则，支持智能路由和降级策略。

## ADDED Requirements

### Requirement: Route based on task type

系统 SHALL 根据任务类型（spec-driven/ad-hoc）选择合适的 provider。

#### Scenario: Route spec-driven task
- **WHEN** 任务类型为 spec-driven
- **THEN** 系统 SHALL 优先选择 OpenSpec 或 Supervisor provider

#### Scenario: Route ad-hoc task
- **WHEN** 任务类型为 ad-hoc
- **THEN** 系统 SHALL 优先选择 Kiro provider

### Requirement: Route based on risk level

系统 SHALL 根据任务的风险等级（低/中/高）调整 provider 选择。

#### Scenario: Low risk task
- **WHEN** 任务风险等级为低
- **THEN** 系统 SHALL 可选择轻量级 provider（OpenSpec/Kiro）

#### Scenario: High risk task
- **WHEN** 任务风险等级为高
- **THEN** 系统 SHALL 选择重量级 provider（Supervisor）
- **AND** 启用完整审核流程

### Requirement: Route based on resource availability

系统 SHALL 根据当前资源配置（AI 资源、计算资源）调整 provider 选择。

#### Scenario: AI resources available
- **WHEN** AI 资源充足
- **THEN** 系统 SHALL 可选择 Kiro provider

#### Scenario: AI resources insufficient
- **WHEN** AI 资源不足
- **THEN** 系统 SHALL 不选择 Kiro provider
- **AND** 降级到非 AI provider

### Requirement: Support custom routing rules

系统 SHALL 支持用户自定义路由规则，覆盖默认路由策略。

#### Scenario: Define custom routing rule
- **WHEN** 用户定义自定义路由规则（如 "高风险 + AI 充足 → Kiro"）
- **THEN** 系统 SHALL 应用该规则覆盖默认策略

#### Scenario: Validate routing rules
- **WHEN** 用户定义自定义路由规则
- **THEN** 系统 SHALL 验证规则格式和语义
- **AND** 验证失败时拒绝规则

### Requirement: Provide routing decision transparency

系统 SHALL 提供路由决策的透明度，说明为什么选择特定 provider。

#### Scenario: Explain routing decision
- **WHEN** 完成路由决策
- **THEN** 系统 SHALL 记录路由理由（如 "任务类型=spec-driven, 风险=低 → OpenSpec"）

#### Scenario: Dry-run routing
- **WHEN** 用户请求路由预览（dry-run 模式）
- **THEN** 系统 SHALL 返回路由决策但不执行
- **AND** 显示路由理由

### Requirement: Support provider priority

系统 SHALL 支持配置 provider 优先级，当多个 provider 都满足条件时选择优先级最高的。

#### Scenario: Multiple providers available
- **WHEN** 多个 provider 都满足路由条件
- **THEN** 系统 SHALL 选择优先级最高的 provider

#### Scenario: Configure provider priority
- **WHEN** 用户配置 provider 优先级（如 "Supervisor > OpenSpec > Kiro"）
- **THEN** 系统 SHALL 按照优先级顺序选择 provider

### Requirement: Support routing strategy testing

系统 SHALL 支持测试路由策略，验证规则是否符合预期。

#### Scenario: Test routing strategy
- **WHEN** 用户提交测试任务上下文
- **THEN** 系统 SHALL 返回路由决策和理由
- **AND** 不实际执行任务

#### Scenario: Validate routing matrix
- **WHEN** 用户请求验证路由策略矩阵
- **THEN** 系统 SHALL 检查路由规则是否覆盖所有场景
- **AND** 报告未覆盖的场景

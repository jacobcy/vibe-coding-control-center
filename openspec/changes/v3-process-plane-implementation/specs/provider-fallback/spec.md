# Provider Fallback Specification

## Overview

Provider Fallback 负责在 provider 不可用时自动降级到备用 provider，保证系统可用性。它提供降级路径、降级通知和手动恢复机制。

## ADDED Requirements

### Requirement: Automatic fallback when provider unavailable

系统 SHALL 在 provider 不可用时自动降级到备用 provider。

#### Scenario: Provider startup failure
- **WHEN** provider 启动失败
- **THEN** 系统 SHALL 自动降级到备用 provider

#### Scenario: Provider timeout
- **WHEN** provider 执行超时
- **THEN** 系统 SHALL 自动降级到备用 provider

#### Scenario: Provider resource exhausted
- **WHEN** provider 资源耗尽（如 AI 配额用尽）
- **THEN** 系统 SHALL 自动降级到非资源依赖 provider

### Requirement: Define fallback path

系统 SHALL 定义明确的降级路径，确保最终降级到 Manual provider。

#### Scenario: Supervisor fallback path
- **WHEN** Supervisor provider 不可用
- **THEN** 系统 SHALL 尝试降级到 OpenSpec provider

#### Scenario: OpenSpec fallback path
- **WHEN** OpenSpec provider 不可用
- **THEN** 系统 SHALL 尝试降级到 Kiro provider

#### Scenario: Kiro fallback path
- **WHEN** Kiro provider 不可用
- **THEN** 系统 SHALL 降级到 Manual provider

#### Scenario: Manual as final fallback
- **WHEN** 所有高级 provider 都不可用
- **THEN** 系统 SHALL 最终降级到 Manual provider
- **AND** Manual provider 永远可用

### Requirement: Notify user on fallback

系统 SHALL 在降级发生时通知用户，说明降级原因和当前使用的 provider。

#### Scenario: Notify on fallback
- **WHEN** 发生 provider 降级
- **THEN** 系统 SHALL 记录降级日志
- **AND** 通知用户（如终端输出或日志文件）

#### Scenario: Explain fallback reason
- **WHEN** 通知用户降级
- **THEN** 系统 SHALL 说明降级原因（如 "Supervisor 不可用，降级到 OpenSpec"）

### Requirement: Support manual recovery

系统 SHALL 支持用户手动从降级状态恢复到高级 provider。

#### Scenario: Manual recovery to original provider
- **WHEN** 用户请求恢复到原始 provider
- **THEN** 系统 SHALL 检查原始 provider 是否可用
- **AND** 如果可用，切换到原始 provider

#### Scenario: Recovery with state preservation
- **WHEN** 从降级 provider 恢复到高级 provider
- **THEN** 系统 SHALL 保留已完成的进度
- **AND** 在高级 provider 中继续执行

### Requirement: Track fallback history

系统 SHALL 记录降级历史，便于排查问题和优化路由策略。

#### Scenario: Record fallback event
- **WHEN** 发生 provider 降级
- **THEN** 系统 SHALL 记录事件时间、原因、降级路径

#### Scenario: Query fallback history
- **WHEN** 用户查询降级历史
- **THEN** 系统 SHALL 返回最近的降级事件列表

### Requirement: Prevent fallback loops

系统 SHALL 防止降级循环，避免在 provider 之间反复切换。

#### Scenario: Detect fallback loop
- **WHEN** 检测到降级循环（如 A → B → A）
- **THEN** 系统 SHALL 停止降级
- **AND** 最终降级到 Manual provider

#### Scenario: Limit fallback attempts
- **WHEN** 同一任务的降级尝试次数超过阈值（如 3 次）
- **THEN** 系统 SHALL 停止降级
- **AND** 报告错误

### Requirement: Fallback does not affect control plane status

系统 SHALL 确保 provider 降级不影响控制平面的核心状态（todo → in_progress → blocked → done → archived）。

#### Scenario: Maintain in_progress status on fallback
- **WHEN** 任务执行中发生 provider 降级
- **THEN** 控制平面状态 SHALL 保持 in_progress
- **AND** 不因降级而变为 blocked

#### Scenario: Report fallback in metadata
- **WHEN** provider 降级
- **THEN** 系统 SHALL 在状态 metadata 中记录降级信息
- **AND** 不改变控制平面的核心状态字段

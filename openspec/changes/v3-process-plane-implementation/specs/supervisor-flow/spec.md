# Supervisor Flow Specification

## Overview

Supervisor Flow 实现 Supervisor provider 的六层流程模型（Intake → Scoping → Design → Plan → Execution → Audit/Close），作为流程平面内部的标准流程。该流程只在流程平面内部生效，不映射为控制平面核心状态。

## ADDED Requirements

### Requirement: Implement six-layer flow

系统 SHALL 实现 Supervisor provider 的六层流程模型，每个阶段有明确的输入输出和转换规则。

#### Scenario: Intake phase
- **WHEN** 任务进入 Supervisor provider
- **THEN** 系统 SHALL 执行 Intake 阶段
- **AND** 收集任务基本信息和上下文

#### Scenario: Scoping phase
- **WHEN** Intake 阶段完成
- **THEN** 系统 SHALL 执行 Scoping 阶段
- **AND** 定义任务范围和边界

#### Scenario: Design phase
- **WHEN** Scoping 阶段完成
- **THEN** 系统 SHALL 执行 Design 阶段
- **AND** 设计技术方案和架构决策

#### Scenario: Plan phase
- **WHEN** Design 阶段完成
- **THEN** 系统 SHALL 执行 Plan 阶段
- **AND** 制定详细的实施计划

#### Scenario: Execution phase
- **WHEN** Plan 阶段完成
- **THEN** 系统 SHALL 执行 Execution 阶段
- **AND** 按照计划实施变更

#### Scenario: Audit/Close phase
- **WHEN** Execution 阶段完成
- **THEN** 系统 SHALL 执行 Audit/Close 阶段
- **AND** 审核结果并关闭任务

### Requirement: Phase transition rules

系统 SHALL 定义明确的阶段转换规则，支持顺序推进和回退。

#### Scenario: Forward transition
- **WHEN** 当前阶段完成且满足转换条件
- **THEN** 系统 SHALL 推进到下一阶段

#### Scenario: Backward transition on failure
- **WHEN** 当前阶段失败且需要回退
- **THEN** 系统 SHALL 回退到前一阶段
- **AND** 保留前一阶段的进度

#### Scenario: Skip non-critical phase
- **WHEN** 任务类型允许跳过某些阶段（如低风险任务可跳过 Scoping）
- **THEN** 系统 SHALL 支持跳过非关键阶段

### Requirement: Phase input/output contracts

系统 SHALL 定义每个阶段的输入输出契约，确保阶段间数据传递的完整性。

#### Scenario: Intake output
- **WHEN** Intake 阶段完成
- **THEN** 系统 SHALL 输出任务基本信息、上下文、初步评估

#### Scenario: Scoping output
- **WHEN** Scoping 阶段完成
- **THEN** 系统 SHALL 输出范围定义、边界约束、风险评估

#### Scenario: Design output
- **WHEN** Design 阶段完成
- **THEN** 系统 SHALL 输出技术方案、架构决策、接口设计

#### Scenario: Plan output
- **WHEN** Plan 阶段完成
- **THEN** 系统 SHALL 输出实施步骤、资源分配、时间估算

#### Scenario: Execution output
- **WHEN** Execution 阶段完成
- **THEN** 系统 SHALL 输出变更结果、测试报告、部署记录

#### Scenario: Audit output
- **WHEN** Audit 阶段完成
- **THEN** 系统 SHALL 输出审核报告、经验总结、归档材料

### Requirement: Phase status aggregation

系统 SHALL 将 Supervisor 六层状态聚合为控制平面可识别的状态（in_progress/done），不暴露内部阶段。

#### Scenario: Aggregate Intake/Scoping/Design/Plan/Execution as in_progress
- **WHEN** Supervisor 处于 Intake → Execution 任意阶段
- **THEN** 系统 SHALL 返回聚合状态 {state: "in_progress"}

#### Scenario: Aggregate Audit/Close as done
- **WHEN** Supervisor 完成 Audit/Close 阶段
- **THEN** 系统 SHALL 返回聚合状态 {state: "done"}

#### Scenario: Do not expose phase details to control plane
- **WHEN** 控制平面查询 Supervisor 状态
- **THEN** 系统 SHALL 不返回具体阶段名称（如 "Scoping"）
- **AND** 只返回聚合状态（in_progress/done）

### Requirement: Support phase-specific validation

系统 SHALL 支持每个阶段的自定义验证规则，确保阶段输出符合预期。

#### Scenario: Validate Design output
- **WHEN** Design 阶段完成
- **THEN** 系统 SHALL 验证技术方案的完整性
- **AND** 验证失败时阻止进入 Plan 阶段

#### Scenario: Validate Plan output
- **WHEN** Plan 阶段完成
- **THEN** 系统 SHALL 验证实施计划的可行性
- **AND** 验证失败时阻止进入 Execution 阶段

### Requirement: Support phase checkpoint

系统 SHALL 支持在关键阶段设置检查点，支持从检查点恢复执行。

#### Scenario: Create checkpoint after Design phase
- **WHEN** Design 阶段完成
- **THEN** 系统 SHALL 创建检查点，保存 Design 输出

#### Scenario: Resume from checkpoint
- **WHEN** Execution 阶段失败且需要重试
- **THEN** 系统 SHALL 从最近的检查点（如 Plan）恢复执行
- **AND** 不重新执行已完成的阶段

### Requirement: Phase execution logging

系统 SHALL 记录每个阶段的执行日志，便于审计和问题排查。

#### Scenario: Log phase start and completion
- **WHEN** 阶段开始和完成
- **THEN** 系统 SHALL 记录时间戳、阶段名称、执行结果

#### Scenario: Log phase failure details
- **WHEN** 阶段执行失败
- **THEN** 系统 SHALL 记录错误详情、堆栈信息、上下文

#### Scenario: Query phase execution history
- **WHEN** 用户查询任务执行历史
- **THEN** 系统 SHALL 返回所有阶段的执行日志

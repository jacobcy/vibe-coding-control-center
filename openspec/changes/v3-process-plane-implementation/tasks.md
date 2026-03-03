# Implementation Tasks: V3 Process Plane

## 1. Setup & Structure

- [x] 1.1 创建 `v3/process-plane/` 目录结构（adapters/, router.sh, strategy.sh, fallback.sh）
- [x] 1.2 创建 `v3/process-plane/adapters/` 子目录（openspec/, supervisor/, kiro/, manual/）
- [x] 1.3 定义 provider adapter 接口模板（adapter-template.sh）
- [x] 1.4 创建测试目录结构（tests/process-plane/）

## 2. Provider Router Core

- [x] 2.1 实现 `route(task)` 接口 - 根据任务上下文选择 provider
- [x] 2.2 实现 `start(task, context)` 接口 - 启动 provider 执行并返回 provider_ref
- [x] 2.3 实现 `status(provider_ref)` 接口 - 查询 provider 执行状态
- [x] 2.4 实现 `complete(provider_ref)` 接口 - 完成 provider 执行并清理资源
- [x] 2.5 实现状态聚合逻辑 - 将 provider 内部状态聚合为 in_progress/done
- [x] 2.6 实现 provider 注册机制 - 动态加载 adapters/ 目录下的 adapter
- [x] 2.7 实现 adapter 验证 - 检查 adapter 是否实现了必需接口

## 3. Routing Strategy Engine

- [x] 3.1 实现基于任务类型的路由规则（spec-driven → OpenSpec/Supervisor, ad-hoc → Kiro）
- [x] 3.2 实现基于风险等级的路由规则（低 → 轻量级, 高 → 重量级）
- [x] 3.3 实现基于资源配置的路由规则（AI 充足 → Kiro, AI 不足 → 非 AI provider）
- [x] 3.4 实现自定义路由规则支持 - 允许用户定义覆盖默认策略
- [x] 3.5 实现路由决策透明度 - 记录路由理由
- [x] 3.6 实现 provider 优先级配置 - 支持配置多个 provider 的优先级
- [x] 3.7 实现 dry-run 模式 - 预览路由决策但不执行
- [x] 3.8 实现路由策略测试框架 - 验证规则是否符合预期

## 4. Provider Fallback Mechanism

- [x] 4.1 定义降级路径（Supervisor → OpenSpec → Kiro → Manual）
- [x] 4.2 实现自动降级逻辑 - provider 不可用时自动降级
- [x] 4.3 实现降级通知机制 - 记录日志并通知用户
- [x] 4.4 实现手动恢复接口 - 支持从降级状态恢复到高级 provider
- [x] 4.5 实现降级历史记录 - 记录降级事件和原因
- [x] 4.6 实现降级循环检测 - 防止在 provider 间反复切换
- [x] 4.7 实现降级尝试次数限制 - 避免无限降级

## 5. Supervisor Flow Implementation

- [ ] 5.1 实现 Intake 阶段 - 收集任务基本信息和上下文
- [ ] 5.2 实现 Scoping 阶段 - 定义任务范围和边界
- [ ] 5.3 实现 Design 阶段 - 设计技术方案和架构决策
- [ ] 5.4 实现 Plan 阶段 - 制定详细的实施计划
- [ ] 5.5 实现 Execution 阶段 - 按照计划实施变更
- [ ] 5.6 实现 Audit/Close 阶段 - 审核结果并关闭任务
- [ ] 5.7 实现阶段转换规则 - 支持顺序推进和回退
- [ ] 5.8 实现阶段输入输出契约 - 确保阶段间数据传递完整
- [ ] 5.9 实现阶段状态聚合 - 将六层状态聚合为 in_progress/done
- [ ] 5.10 实现阶段验证规则 - 每个阶段的自定义验证
- [ ] 5.11 实现阶段检查点 - 支持从检查点恢复执行
- [ ] 5.12 实现阶段执行日志 - 记录每个阶段的执行日志

## 6. Provider Adapters

### 6.1 OpenSpec Adapter

- [x] 6.1.1 实现 OpenSpec adapter 的 route 接口 - 接受 spec-driven 任务
- [x] 6.1.2 实现 OpenSpec adapter 的 start 接口 - 调用 openspec 命令
- [x] 6.1.3 实现 OpenSpec adapter 的 status 接口 - 查询 openspec 状态
- [x] 6.1.4 实现 OpenSpec adapter 的 complete 接口 - 完成 openspec 执行

### 6.2 Supervisor Adapter

- [x] 6.2.1 实现 Supervisor adapter 的 route 接口 - 接受高风险任务
- [x] 6.2.2 实现 Supervisor adapter 的 start 接口 - 启动六层流程
- [x] 6.2.3 实现 Supervisor adapter 的 status 接口 - 查询六层状态
- [x] 6.2.4 实现 Supervisor adapter 的 complete 接口 - 完成六层流程

### 6.3 Kiro Adapter

- [x] 6.3.1 实现 Kiro adapter 的 route 接口 - 接受 ad-hoc 任务且 AI 资源充足
- [x] 6.3.2 实现 Kiro adapter 的 start 接口 - 调用 Kiro AI
- [x] 6.3.3 实现 Kiro adapter 的 status 接口 - 查询 AI 执行状态
- [x] 6.3.4 实现 Kiro adapter 的 complete 接口 - 完成 AI 执行

### 6.4 Manual Adapter

- [x] 6.4.1 实现 Manual adapter 的 route 接口 - 永远接受任务（降级兜底）
- [x] 6.4.2 实现 Manual adapter 的 start 接口 - 启动人工流程
- [x] 6.4.3 实现 Manual adapter 的 status 接口 - 查询人工状态
- [x] 6.4.4 实现 Manual adapter 的 complete 接口 - 完成人工流程

## 7. Testing

### 7.1 Unit Tests

- [ ] 7.1.1 编写 router 接口的单元测试
- [ ] 7.1.2 编写 routing strategy 的单元测试
- [ ] 7.1.3 编写 fallback mechanism 的单元测试
- [ ] 7.1.4 编写 supervisor flow 的单元测试
- [ ] 7.1.5 编写各个 adapter 的单元测试

### 7.2 Integration Tests

- [ ] 7.2.1 编写 provider router 与 adapter 的集成测试
- [ ] 7.2.2 编写 routing strategy 与 router 的集成测试
- [ ] 7.2.3 编写 fallback 与 router 的集成测试
- [x] 7.2.4 编写端到端测试（任务路由 → 执行 → 完成）

### 7.3 Scenario Tests

- [ ] 7.3.1 测试 spec-driven 低风险任务路由到 OpenSpec
- [ ] 7.3.2 测试 spec-driven 高风险任务路由到 Supervisor
- [ ] 7.3.3 测试 ad-hoc 任务路由到 Kiro
- [ ] 7.3.4 测试 provider 不可用时自动降级
- [ ] 7.3.5 测试从降级状态手动恢复
- [ ] 7.3.6 测试 Supervisor 六层流程的完整执行

## 8. Documentation

- [ ] 8.1 编写 Provider Router 接口文档（README.md）
- [ ] 8.2 编写 Routing Strategy 配置指南
- [ ] 8.3 编写 Provider Adapter 开发指南
- [ ] 8.4 编写 Provider Fallback 使用说明
- [ ] 8.5 编写 Supervisor Flow 流程说明
- [ ] 8.6 更新 v3/process-plane/SPEC.md - 添加实现细节
- [ ] 8.7 编写迁移指南 - 从 V2 迁移到 V3

## 9. Integration with Control Plane

- [ ] 9.1 定义 Control → Process 接口契约（provider, provider_ref, status）
- [ ] 9.2 定义 Process → Control 接口契约（provider_state 聚合结果）
- [ ] 9.3 实现 control plane 调用 process plane 的 route/start/status/complete
- [ ] 9.4 测试 control plane 与 process plane 的集成

## 10. Migration & Rollout

- [ ] 10.1 验证 V3 实现在独立目录，不影响 V2 代码
- [ ] 10.2 实现 V2 → V3 数据兼容（共享数据格式）
- [ ] 10.3 编写回滚计划 - 如需回滚，切换到 V2 接口
- [ ] 10.4 进行灰度测试 - 小范围验证 V3 实现
- [ ] 10.5 全量切换到 V3 实现
- [ ] 10.6 废弃 V2 相关代码（V3 稳定后）

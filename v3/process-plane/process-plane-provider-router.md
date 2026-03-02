# PRD: Process Plane — Provider Router (OpenSpec / Supervisor / Kiro)

## 1. Overview
定义流程平面：由 provider 负责 design/plan/execution。`vibe` 不实现流程，仅通过 provider router 路由任务到对应流程系统。

## 2. Problem Statement
流程框架直接嵌入内核会导致：
- 换框架需要改核心代码
- 过程模型污染任务状态机
- 组织演进受单一工具限制

## 3. Product Goals
- 支持多 provider 可替换接入
- 保持控制平面的 provider 无关性
- 允许 Supervisor 六层结构作为组织内流程标准

## 4. Non-Goals
- 不在本期实现 provider 全自动执行
- 不统一各 provider 内部 artifact 格式
- 不在控制平面暴露 provider 内部阶段

## 5. Provider Abstraction
统一接口：
- `route(task)`
- `start(task, context)`
- `status(provider_ref)`
- `complete(provider_ref)`
- `handoff(provider_ref, next_provider)`

## 6. Minimal Coupling Contract
控制平面仅存：
- `provider`
- `provider_ref`
- `status`

禁止：
- 存 provider 内部步骤
- 依赖 provider 文件路径结构

## 7. Routing Policy
路由输入信号：
- 任务类型（bugfix/feature/refactor/research）
- 风险等级
- 人工策略（强制 provider）
- 资源约束（并行额度）

## 8. Supervisor Six-Layer Model (Internal Standard)
建议六层（仅在流程平面内部生效）：
1. Intake
2. Scoping
3. Design
4. Plan
5. Execution
6. Audit/Close

说明：六层模型不外溢到控制平面状态机。

## 9. OpenClaw Integration
- OpenClaw 可作为 provider router 执行器
- 自动选择 OpenSpec / Supervisor / Kiro
- 决策结果只回写 `provider + provider_ref`

## 10. Failure & Escalation
- provider 不可用：降级 `manual`
- provider 超时：标记 `blocked` 并发出人工接管信号
- provider 结果冲突：由 Supervisor 仲裁

## 11. Success Metrics
- 切换 provider 无需修改 task schema
- 新 provider 接入仅新增 adapter 文档/实现
- 路由错误率持续下降

## 12. Rollout Plan
- P1：确定 provider 字段枚举与引用规范
- P2：定义 router 策略与优先级
- P3：先接 OpenSpec + Kiro，再接 Supervisor

## 13. References
- `docs/references/coding-with-openclaw.md`
- `docs/standards/provider-decoupling-contract.md`

## 14. Open Questions
- Supervisor 是否作为独立 provider 还是编排层？
- provider 切换时 `provider_ref` 的映射策略如何统一？

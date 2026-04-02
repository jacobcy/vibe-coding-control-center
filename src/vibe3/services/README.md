# Services

核心业务逻辑层，实现 flow/PR/task/handoff 等工作流。

## 职责

- Flow 生命周期管理（创建、状态转变、查询、投影）
- PR 全生命周期（创建、评分、merge、ready）
- Task 绑定与管理
- Handoff 记录与恢复
- Pre-push 检查
- Label/Milestone 管理
- 版本管理

## 关键组件

| 文件 | 职责 |
|------|------|
| flow_service.py | Flow CRUD + 状态转变 |
| flow_lifecycle.py | Flow 生命周期 mixin |
| flow_query_mixin.py | Flow 查询 mixin |
| flow_projection_service.py | Flow 状态投影 |
| pr_service.py | PR 主服务 |
| pr_create_usecase.py | PR 创建用例 |
| pr_ready_usecase.py | PR ready 用例 |
| pr_scoring_service.py | PR 质量评分 |
| task_service.py | Task 绑定管理 |
| task_usecase.py | Task 用例 |
| handoff_service.py | Handoff 记录服务 |
| handoff_recorder_unified.py | 统一 handoff 记录器 |
| check_service.py | Pre-push 检查 |
| label_service.py | GitHub label 管理 |
| milestone_service.py | Milestone 管理 |
| version_service.py | 版本号管理 |
| ai_service.py | AI 辅助决策 |
| signature_service.py | Flow 签名验证 |
| spec_ref_service.py | OpenSpec 集成 |

## 依赖关系

- 依赖: clients (Git/GitHub/SQLite), models, config, exceptions
- 被依赖: commands, manager, orchestra
